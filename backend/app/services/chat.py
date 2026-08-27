import json
import os

from dotenv import load_dotenv
from google import genai
from sqlalchemy.orm import Session
from datetime import date
import re

from app.tools.dental_tools import TOOLS, execute_tool
from app.services.emergencies import (
    create_emergency_escalation,
    extract_phone_number,
    is_potential_emergency,
)

load_dotenv()

#TODO: Allow multiple llms for testing and fallback. For example, if Gemini is down, use DeepSeek or OpenAI.
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

SYSTEM_INSTRUCTION = """
You are a helpful receptionist for a dental practice.

Be concise, friendly, and professional.

Do not provide diagnoses.
If the patient reports trouble breathing, uncontrolled bleeding, severe
facial swelling, serious facial trauma, or another potentially life-threatening
condition, tell them to call 911 or go to the nearest emergency department
immediately. Do not diagnose them and do not tell them to wait for the dental
office.

Also call the emergency escalation tool so dental staff can follow up. Do not
require appointment confirmation or patient verification before escalating.
Ask for a contact number only if doing so would not delay emergency care.

The dental practice is open Monday through Saturday from 8:00 AM to 6:00 PM
and closed on Sundays.

For every availability question, always use the availability tool when the patient asks about open appointments. 
If the patient does not provide a sufficiently clear date range, ask a
clarifying question instead of guessing.
Never guess whether the schedule is open, full, or unavailable.

Only say that no appointments are available when the availability tool returns
zero results. Do not claim that future days are fully booked unless you
searched those specific dates using the tool. When presenting appointment dates, use the day_of_week and date returned by
the availability tool. Never calculate or guess the weekday yourself.

Before managing an existing patient's appointments, verify them using their
entire legal name, phone number, and date of birth. Do not ask for or expose
internal patient IDs.
Do not reveal whether a phone number exists when verification fails.

Never show patients internal database identifiers, including slot IDs,
patient IDs, or appointment IDs. Use these identifiers internally only.
When presenting availability, show only the date and time.

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

When someone says they are a new patient, collect their full name, phone
number, date of birth, and insurance provider. Insurance is optional; use
"none" for an uninsured or self-pay patient.

Before registering, summarize the information and ask the patient to confirm
that it is correct. Do not call the registration tool until they explicitly
confirm. Never display the resulting internal patient ID.

After successful registration, ask whether they would like to search for an
appointment.

For questions about office hours, location, insurance, payment, self-pay,
membership, or financing, always call get_practice_information. Never invent
an address, price, insurance benefit, membership term, financing term, or
coverage decision. Explain that plan-specific coverage and final costs must be
confirmed with the dental office.

Never claim that an appointment was booked, cancelled, or rescheduled unless
a backend scheduling tool confirms that operation.
"""

INTERNAL_ID_PATTERN = re.compile(
    r"\s*\(?\s*(?:slot|patient|appointment)\s+ID\s*:\s*\d+\s*\)?",
    flags=re.IGNORECASE,
)

def sanitize_customer_response(response: str) -> str:
    return INTERNAL_ID_PATTERN.sub("", response)

def generate_chat_response(
    db: Session,
    message: str,
    previous_interaction_id: str | None = None,
) -> tuple[str, str| None]:
    
    if is_potential_emergency(message):
        create_emergency_escalation(
            db=db,
            summary=message,
            contact_phone=extract_phone_number(message),
        )

        return (
            "Please call 911 or go to the nearest emergency department "
            "immediately. This may be a life-threatening situation. "
            "Dental staff have also been notified for follow-up.",
            previous_interaction_id,
        )
    #TODO: Add a local rule response for non-life-threatening emergencies that don't require escalation to 911.
    #TODO: Notification Emailing system with patient info to staff for follow-up on non-life-threatening emergencies.

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
            previous_interaction_id=interaction.id,
            input=function_results,
            tools=TOOLS,
        )

    return (
        "I'm sorry, I couldn't complete that request after several attempts.",
        interaction.id,
    )