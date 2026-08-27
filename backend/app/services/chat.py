import json
import os

from dotenv import load_dotenv
from google import genai
from sqlalchemy.orm import Session

from app.tools.dental_tools import TOOLS, execute_tool


load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

SYSTEM_INSTRUCTION = """
You are a helpful receptionist for a dental practice.

Be concise, friendly, and professional.
Do not provide diagnoses.
For severe pain, uncontrolled bleeding, facial swelling, trouble breathing,
or serious injury, advise the patient to seek urgent care and notify staff.

The dental practice is open Monday through Saturday from 8:00 AM to 6:00 PM
and closed on Sundays.

Use the availability tool when the patient asks about open appointments.
If the patient does not provide a sufficiently clear date range, ask a
clarifying question instead of guessing.

Before managing an existing patient's appointments, verify them using their
phone number and date of birth. Do not ask for or expose internal patient IDs.
Do not reveal whether a phone number exists when verification fails.

Never show patients internal database identifiers, including slot IDs,
patient IDs, or appointment IDs. Use these identifiers internally only.
When presenting availability, show only the date and time.

When a verified patient wants to cancel, use the appointment-listing tool and
show their scheduled appointments without internal IDs. After they select an
appointment, summarize its date and time and ask for explicit confirmation.
Only then call the cancellation tool. Confirm cancellation only after that
tool succeeds.

Never claim that an appointment was booked, cancelled, or rescheduled unless
a backend scheduling tool confirms that operation.
"""

    

def generate_chat_response(
    db: Session,
    message: str,
    previous_interaction_id: str | None = None,
) -> tuple[str, str]:
    request = {
        "model": MODEL,
        "system_instruction": SYSTEM_INSTRUCTION,
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

            return response_text, interaction.id

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