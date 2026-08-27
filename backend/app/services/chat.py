import json
import os
from datetime import date, datetime, timedelta

from dotenv import load_dotenv
from google import genai
from sqlalchemy.orm import Session
from datetime import date
import re

from app.tools.dental_tools import TOOLS, execute_tool
from app.models import Patient
from app.services.emergencies import (
    create_emergency_escalation,
    extract_phone_number,
    is_life_threatening,
    is_non_life_threatening_emergency,
    notify_staff,
)
from app.services.scheduling import book_appointment, find_available_slots

load_dotenv()

#TODO: Allow multiple llms for testing and fallback. For example, if Gemini is down, use DeepSeek or OpenAI.
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

BASE_PROMPT = """
You are a helpful receptionist for a dental practice.

Be concise, friendly, and professional.

Never claim that an appointment was booked, cancelled, or rescheduled unless
a backend scheduling tool confirms that operation.
"""

SAFETY_PROMPT = """
Do not provide diagnoses.
If the patient reports trouble breathing, uncontrolled bleeding, severe
facial swelling, serious facial trauma, or another potentially life-threatening
condition, tell them to call 911 or go to the nearest emergency department
immediately. Do not diagnose them and do not tell them to wait for the dental
office.

For urgent but non-life-threatening dental concerns such as severe tooth pain,
a broken or knocked-out tooth, or a possible dental infection, acknowledge the
urgency, try to book the earliest available appointment for the matched
patient, and escalate the report to staff. Do not tell the patient to call 911
unless life-threatening symptoms are present.

The emergency escalation tool may also book the earliest available emergency
appointment. Only say that an emergency appointment is confirmed when the tool
result explicitly reports that an appointment was booked. If no patient record
can be matched, explain that staff were notified and the patient must contact
the office to complete booking.

Also call the emergency escalation tool so dental staff can follow up. Do not
require appointment confirmation or patient verification before escalating.
Ask for a contact number only if doing so would not delay emergency care.
"""

PRACTICE_PROMPT = """
The dental practice is open Monday through Saturday from 8:00 AM to 6:00 PM
and closed on Sundays.

For questions about office hours, location, insurance, payment, self-pay,
membership, or financing, always call get_practice_information. Never invent
an address, price, insurance benefit, membership term, financing term, or
coverage decision. Explain that plan-specific coverage and final costs must be
confirmed with the dental office.
"""

AVAILABILITY_PROMPT = """
For every availability question, always use the availability tool when the
patient asks about open appointments.
If the patient does not provide a sufficiently clear date range, ask a
clarifying question instead of guessing.
Never guess whether the schedule is open, full, or unavailable.

Only say that no appointments are available when the availability tool returns
zero results. Do not claim that future days are fully booked unless you
searched those specific dates using the tool. When presenting appointment
dates, use the day_of_week and date returned by the availability tool. Never
calculate or guess the weekday yourself.
"""

IDENTITY_PROMPT = """
Before managing an existing patient's appointments, verify them using their
entire legal name, phone number, and date of birth. Do not ask for or expose
internal patient IDs.
Do not reveal whether a phone number exists when verification fails.

Never show patients internal database identifiers, including slot IDs,
patient IDs, or appointment IDs. Use these identifiers internally only.
When presenting availability, show only the date and time.
"""

REGISTRATION_PROMPT = """
When someone says they are a new patient, collect their full name, phone
number, date of birth, and insurance provider. Insurance is optional; use
"none" for an uninsured or self-pay patient.

Before registering, summarize the information and ask the patient to confirm
that it is correct. Do not call the registration tool until they explicitly
confirm. Never display the resulting internal patient ID.

After successful registration, ask whether they would like to search for an
appointment.
"""

APPOINTMENT_PROMPT = """
When a verified patient wants to cancel, use the appointment-listing tool and
show their scheduled appointments without internal IDs. After they select an
appointment, summarize its date and time and ask for explicit confirmation.
Only then call the cancellation tool. Confirm cancellation only after that
tool succeeds.

When a verified patient wants to reschedule, list their scheduled appointments
and let them identify which one to move. Then search for new availability.
After they select a new time, summarize both the existing appointment and the
new time and ask for explicit confirmation. Only after confirmation may you
call the rescheduling tool. Confirm success only after the tool succeeds.
"""

FAMILY_PROMPT = """
For family scheduling, collect each family member's verified patient record,
find consecutive back-to-back slots for the requested members, and summarize
the complete block before asking for explicit confirmation. Only call the
family booking tool after confirmation, and never create a partial family
booking.
"""

APPOINTMENT_TYPE_PROMPT = """
Before booking an appointment, ask which appointment type the patient needs,
such as a general visit, cleaning, or emergency visit. Use the
selected type to inform staff and store it on the appointment record; it does
not describe the availability slot.
"""

SYSTEM_INSTRUCTION = "\n\n".join(
    section.strip()
    for section in (
        BASE_PROMPT,
        SAFETY_PROMPT,
        PRACTICE_PROMPT,
        AVAILABILITY_PROMPT,
        IDENTITY_PROMPT,
        REGISTRATION_PROMPT,
        APPOINTMENT_PROMPT,
        FAMILY_PROMPT,
        APPOINTMENT_TYPE_PROMPT,
    )
)


INTERNAL_ID_PATTERN = re.compile(
    r"\s*\(?\s*(?:slot|patient|appointment)\s+ID\s*:\s*\d+\s*\)?",
    flags=re.IGNORECASE,
)

def sanitize_customer_response(response: str) -> str:
    return INTERNAL_ID_PATTERN.sub("", response)


def book_earliest_urgent_appointment(
    db: Session,
    patient: Patient | None,
    emergency_summary: str,
) -> tuple[object | None, str]:
    if patient is None:
        return (
            None,
            "The patient could not be matched to an existing record. "
            "Please contact the dental office promptly to arrange care.",
        )

    slots = find_available_slots(
        db=db,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=180),
        appointment_type="emergency",
    )
    if not slots:
        return None, "No appointment slot was available for automatic booking."

    try:
        appointment = book_appointment(
            db,
            patient.id,
            slots[0].id,
            appointment_type="emergency",
            emergency_summary=emergency_summary,
        )
    except ValueError as error:
        return None, f"Automatic booking could not be completed: {error}"

    appointment_time = appointment.slot.start_time.strftime("%A, %B %d at %I:%M %p")
    return appointment, f"Booked the earliest available appointment for {appointment_time}."

def generate_chat_response(
    db: Session,
    message: str,
    previous_interaction_id: str | None = None,
) -> tuple[str, str| None]:
    
    if is_life_threatening(message) or is_non_life_threatening_emergency(message):
        contact_phone = extract_phone_number(message)
        escalation = create_emergency_escalation(
            db=db,
            summary=message,
            contact_phone=contact_phone,
        )
        patient = None
        if contact_phone:
            patient = db.query(Patient).filter(Patient.phone == contact_phone).first()

        if is_non_life_threatening_emergency(message):
            _, appointment_details = book_earliest_urgent_appointment(
                db,
                patient,
                message,
            )
            notification_sent = notify_staff(
                message,
                contact_phone,
                patient,
                appointment_details,
            )
            notification_details = (
                "Staff email sent."
                if notification_sent
                else "Staff escalation was recorded, but the staff email could not be sent."
            )
            return (
                f"This sounds urgent but not life-threatening. {appointment_details} "
                f"{notification_details}",
                previous_interaction_id,
            )

        notification_sent = notify_staff(message, contact_phone, patient)
        notification_details = (
            "Staff email sent."
            if notification_sent
            else "Staff escalation was recorded, but the staff email could not be sent."
        )
        return (
            "Please call 911 or go to the nearest emergency department "
            "immediately. This may be a life-threatening situation. "
            f"{notification_details}",
            previous_interaction_id,
        )
    today = date.today().isoformat()

    runtime_instruction = (
        f"{SYSTEM_INSTRUCTION}\n\n"
        f"The current local date is {today}. "
        "Interpret relative dates such as today, tomorrow, and next week "
        "using this date."
    )
    
    request = {
        "model": MODEL,
        "system_instruction": runtime_instruction,
        "input": message,
        "tools": TOOLS,
    }
    
    if previous_interaction_id:
        request["previous_interaction_id"] = previous_interaction_id

    interaction = client.interactions.create(**request)

    # Allow Gemini to make several sequential tool calls.
    for _ in range(4):
        function_calls = [
            step
            for step in interaction.steps
            if step.type == "function_call"
        ]

        if not function_calls:
            response_text = (
                interaction.output_text
                or "I'm sorry, I couldn't complete that request."
            )

            return  sanitize_customer_response(response_text),interaction.id

        function_results = []

        for function_call in function_calls:
            result = execute_tool(
                db=db,
                tool_name=function_call.name,
                arguments=function_call.arguments,
                user_message=message,
            )

            function_results.append(
                {
                    "type": "function_result",
                    "name": function_call.name,
                    "call_id": function_call.id,
                    "result": [
                        {
                            "type": "text",
                            "text": json.dumps(result),
                        }
                    ],
                }
            )

        interaction = client.interactions.create(
            model=MODEL,
            system_instruction=runtime_instruction,
            previous_interaction_id=interaction.id,
            input=function_results,
            tools=TOOLS,
        )

    return (
        "I'm sorry, I couldn't complete that request after several attempts.",
        interaction.id,
    )