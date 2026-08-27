import os

from dotenv import load_dotenv
from google import genai


load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

SYSTEM_INSTRUCTION = """
You are a helpful receptionist for a dental practice.

Be concise, friendly, and professional.
Do not provide diagnoses.
For severe pain, uncontrolled bleeding, facial swelling, trouble breathing,
or serious injury, advise the patient to seek urgent care and notify staff.
Never claim that an appointment was booked, cancelled, or rescheduled unless
a backend scheduling function confirms that operation.
"""


def generate_chat_response(
    message: str,
    previous_interaction_id: str | None = None,
) -> tuple[str, str]:
    request = {
        "model": MODEL,
        "system_instruction": SYSTEM_INSTRUCTION,
        "input": message,
    }

    if previous_interaction_id:
        request["previous_interaction_id"] = previous_interaction_id

    interaction = client.interactions.create(**request)

    response_text = (
        interaction.output_text
        or "I'm sorry, I couldn't generate a response."
    )

    return response_text, interaction.id