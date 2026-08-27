from datetime import date, datetime

from sqlalchemy.orm import Session

from app.services.patients import verify_patient
from app.services.scheduling import (
    book_appointment,
    find_available_slots,
)


FIND_AVAILABLE_SLOTS_TOOL = {
    "type": "function",
    "name": "find_available_slots",
    "description": (
        "Find available dental appointment slots within a date and time range."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "start_date": {
                "type": "string",
                "description": (
                    "Beginning of the search range in ISO 8601 format, "
                    "for example 2026-08-28T00:00:00."
                ),
            },
            "end_date": {
                "type": "string",
                "description": (
                    "End of the search range in ISO 8601 format, "
                    "for example 2026-08-31T23:59:59."
                ),
            },
            "appointment_type": {
                "type": "string",
                "description": "Appointment type, currently general.",
            },
        },
        "required": [
            "start_date",
            "end_date",
            "appointment_type",
        ],
    },
}

VERIFY_PATIENT_TOOL = {
    "type": "function",
    "name": "verify_patient",
    "description": (
        "Verify a returning patient using their phone number and date of birth."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "The patient's phone number.",
            },
            "date_of_birth": {
                "type": "string",
                "description": (
                    "The patient's date of birth in YYYY-MM-DD format."
                ),
            },
        },
        "required": ["phone", "date_of_birth"],
    },
}

BOOK_APPOINTMENT_TOOL = {
    "type": "function",
    "name": "book_appointment",
    "description": (
        "Book a confirmed available appointment for a verified patient. "
        "Only call this after showing the selected date and time and "
        "receiving explicit confirmation from the patient."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {
                "type": "integer",
                "description": (
                    "Internal ID returned by successful patient verification."
                ),
            },
            "slot_id": {
                "type": "integer",
                "description": (
                    "Internal ID returned by the availability search."
                ),
            },

        },
        "required": [
            "patient_id",
            "slot_id"
        ],
    },
}

TOOLS = [
    FIND_AVAILABLE_SLOTS_TOOL,
    VERIFY_PATIENT_TOOL,
    BOOK_APPOINTMENT_TOOL,
]


def run_find_available_slots(
    db: Session,
    arguments: dict,
) -> dict:
    slots = find_available_slots(
        db=db,
        start_date=datetime.fromisoformat(arguments["start_date"]),
        end_date=datetime.fromisoformat(arguments["end_date"]),
        appointment_type=arguments["appointment_type"],
    )

    return {
        "total_count": len(slots),
        "slots": [
            {
                "id": slot.id,
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
                "appointment_type": slot.appointment_type,
            }
            for slot in slots[:6]
        ],
    }

def run_verify_patient(
    db: Session,
    arguments: dict,
) -> dict:
    patient = verify_patient(
        db=db,
        phone=arguments["phone"],
        date_of_birth=date.fromisoformat(arguments["date_of_birth"]),
    )

    return {
        "verified": True,
        "patient_id": patient.id,
        "full_name": patient.full_name,
    }
    
def run_book_appointment(
    db: Session,
    arguments: dict,
    user_message: str,
) -> dict:
    normalized_message = user_message.lower().strip()

    confirmation_phrases = (
        "yes",
        "confirm",
        "book it",
        "go ahead",
        "yes please",
    )

    explicitly_confirmed = any(
        phrase in normalized_message
        for phrase in confirmation_phrases
    )

    if not explicitly_confirmed:
        raise ValueError(
            "The appointment has not been booked. "
            "Ask the patient to explicitly confirm the selected date and time."
        )

    appointment = book_appointment(
        db=db,
        patient_id=arguments["patient_id"],
        slot_id=arguments["slot_id"],
    )

    return {
        "success": True,
        "appointment_id": appointment.id,
        "status": appointment.status,
        "appointment_type": appointment.appointment_type,
        "start_time": appointment.slot.start_time.isoformat(),
        "end_time": appointment.slot.end_time.isoformat(),
    }
    
def execute_tool(
    db: Session,
    tool_name: str,
    arguments: dict,
    user_message: str,
) -> dict:
    try:
        if tool_name == "find_available_slots":
            return run_find_available_slots(
                db=db,
                arguments=arguments,
            )

        if tool_name == "verify_patient":
            return run_verify_patient(
                db=db,
                arguments=arguments,
            )

        if tool_name == "book_appointment":
            return run_book_appointment(
                db=db,
                arguments=arguments,
                user_message=user_message,
        )

        return {
            "success": False,
            "error": "Unknown tool requested.",
        }

    except ValueError as error:
        return {
            "success": False,
            "error": str(error),
        }