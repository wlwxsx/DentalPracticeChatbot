from datetime import date, datetime

from sqlalchemy.orm import Session

from app.services.patients import create_patient, verify_patient
from app.services.scheduling import (
    book_appointment,
    cancel_appointment,
    find_available_slots,
    get_patient_appointments,
    reschedule_appointment,
)
from app.services.emergencies import create_emergency_escalation

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

LIST_APPOINTMENTS_TOOL = {
    "type": "function",
    "name": "list_patient_appointments",
    "description": (
        "List a verified patient's scheduled dental appointments."
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
        },
        "required": ["patient_id"],
    },
}

CANCEL_APPOINTMENT_TOOL = {
    "type": "function",
    "name": "cancel_appointment",
    "description": (
        "Cancel a selected appointment belonging to a verified patient. "
        "Only call after the patient explicitly confirms cancellation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {
                "type": "integer",
            },
            "appointment_id": {
                "type": "integer",
            },
        },
        "required": ["patient_id", "appointment_id"],
    },
}

RESCHEDULE_APPOINTMENT_TOOL = {
    "type": "function",
    "name": "reschedule_appointment",
    "description": (
        "Move a verified patient's scheduled appointment to a new available "
        "slot. Only call after the patient explicitly confirms the change."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {
                "type": "integer",
                "description": "Internal verified patient ID.",
            },
            "appointment_id": {
                "type": "integer",
                "description": "Internal appointment ID.",
            },
            "new_slot_id": {
                "type": "integer",
                "description": "Internal ID of the newly selected slot.",
            },
        },
        "required": [
            "patient_id",
            "appointment_id",
            "new_slot_id",
        ],
    },
}

REGISTER_PATIENT_TOOL = {
    "type": "function",
    "name": "register_patient",
    "description": (
        "Register a new dental patient after collecting their name, phone "
        "number, date of birth, and optional insurance information. "
        "Only call after the patient explicitly confirms their details."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "full_name": {
                "type": "string",
                "description": "The patient's full legal name.",
            },
            "phone": {
                "type": "string",
                "description": "The patient's phone number.",
            },
            "date_of_birth": {
                "type": "string",
                "description": "Date of birth in YYYY-MM-DD format.",
            },
            "insurance_name": {
                "type": "string",
                "description": (
                    "Insurance provider name, or 'none' if uninsured."
                ),
            },
        },
        "required": [
            "full_name",
            "phone",
            "date_of_birth",
            "insurance_name",
        ],
    },
}

ESCALATE_EMERGENCY_TOOL = {
    "type": "function",
    "name": "escalate_emergency",
    "description": (
        "Notify dental staff about a potentially urgent dental situation. "
        "Call immediately for uncontrolled bleeding, severe swelling, "
        "trouble breathing, serious facial injury, or severe pain."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Concise summary of the urgent symptoms.",
            },
            "contact_phone": {
                "type": "string",
                "description": (
                    "Patient contact number, or 'unknown' if unavailable."
                ),
            },
        },
        "required": ["summary", "contact_phone"],
    },
}

TOOLS = [
    FIND_AVAILABLE_SLOTS_TOOL,
    VERIFY_PATIENT_TOOL,
    REGISTER_PATIENT_TOOL,
    BOOK_APPOINTMENT_TOOL,
    LIST_APPOINTMENTS_TOOL,
    CANCEL_APPOINTMENT_TOOL,
    RESCHEDULE_APPOINTMENT_TOOL,
    ESCALATE_EMERGENCY_TOOL,
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
   
def run_list_patient_appointments(
    db: Session,
    arguments: dict,
) -> dict:
    appointments = get_patient_appointments(
        db=db,
        patient_id=arguments["patient_id"],
    )

    scheduled = [
        appointment
        for appointment in appointments
        if appointment.status == "scheduled"
    ]

    return {
        "appointments": [
            {
                "appointment_id": appointment.id,
                "appointment_type": appointment.appointment_type,
                "start_time": appointment.slot.start_time.isoformat(),
                "end_time": appointment.slot.end_time.isoformat(),
            }
            for appointment in scheduled
        ]
    }

def run_cancel_appointment(
    db: Session,
    arguments: dict,
    user_message: str,
) -> dict:
    normalized_message = user_message.lower()

    explicitly_confirmed = any(
        phrase in normalized_message
        for phrase in (
            "yes",
            "confirm",
            "cancel it",
            "go ahead",
            "yes please",
        )
    )

    if not explicitly_confirmed:
        raise ValueError(
            "The appointment has not been cancelled. "
            "Ask the patient to explicitly confirm the cancellation."
        )

    patient_appointments = get_patient_appointments(
        db=db,
        patient_id=arguments["patient_id"],
    )

    appointment = next(
        (
            item
            for item in patient_appointments
            if item.id == arguments["appointment_id"]
            and item.status == "scheduled"
        ),
        None,
    )

    if appointment is None:
        raise ValueError(
            "That scheduled appointment does not belong to this patient."
        )

    cancelled = cancel_appointment(
        db=db,
        appointment_id=appointment.id,
    )

    return {
        "success": True,
        "status": cancelled.status,
        "start_time": cancelled.slot.start_time.isoformat(),
        "end_time": cancelled.slot.end_time.isoformat(),
    }
    
def run_reschedule_appointment(
    db: Session,
    arguments: dict,
    user_message: str,
) -> dict:
    normalized_message = user_message.lower()

    explicitly_confirmed = any(
        phrase in normalized_message
        for phrase in (
            "yes",
            "confirm",
            "reschedule it",
            "go ahead",
            "yes please",
        )
    )

    if not explicitly_confirmed:
        raise ValueError(
            "The appointment has not been rescheduled. "
            "Ask the patient to explicitly confirm the new date and time."
        )

    patient_appointments = get_patient_appointments(
        db=db,
        patient_id=arguments["patient_id"],
    )

    appointment = next(
        (
            item
            for item in patient_appointments
            if item.id == arguments["appointment_id"]
            and item.status == "scheduled"
        ),
        None,
    )

    if appointment is None:
        raise ValueError(
            "That scheduled appointment does not belong to this patient."
        )

    old_start_time = appointment.slot.start_time
    old_end_time = appointment.slot.end_time

    updated = reschedule_appointment(
        db=db,
        appointment_id=appointment.id,
        new_slot_id=arguments["new_slot_id"],
    )

    return {
        "success": True,
        "status": updated.status,
        "old_start_time": old_start_time.isoformat(),
        "old_end_time": old_end_time.isoformat(),
        "new_start_time": updated.slot.start_time.isoformat(),
        "new_end_time": updated.slot.end_time.isoformat(),
    }
    
def run_register_patient(
    db: Session,
    arguments: dict,
    user_message: str,
) -> dict:
    normalized_message = user_message.lower()

    explicitly_confirmed = any(
        phrase in normalized_message
        for phrase in (
            "yes",
            "confirm",
            "looks correct",
            "that's correct",
            "go ahead",
        )
    )

    if not explicitly_confirmed:
        raise ValueError(
            "The patient has not been registered. "
            "Summarize their details and ask for explicit confirmation."
        )

    insurance_name = arguments["insurance_name"].strip()

    if insurance_name.lower() in {
        "none",
        "no insurance",
        "uninsured",
        "self-pay",
        "self pay",
    }:
        insurance_name = None

    patient = create_patient(
        db=db,
        full_name=arguments["full_name"],
        phone=arguments["phone"],
        date_of_birth=date.fromisoformat(
            arguments["date_of_birth"]
        ),
        insurance_name=insurance_name,
    )

    return {
        "success": True,
        "patient_id": patient.id,
        "full_name": patient.full_name,
    }
    
def run_escalate_emergency(
    db: Session,
    arguments: dict,
) -> dict:
    contact_phone = arguments["contact_phone"]

    if contact_phone.lower() == "unknown":
        contact_phone = None

    escalation = create_emergency_escalation(
        db=db,
        summary=arguments["summary"],
        contact_phone=contact_phone,
    )

    return {
        "success": True,
        "status": escalation.status,
        "message": "Dental staff have been notified.",
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
            
        if tool_name == "list_patient_appointments":
            return run_list_patient_appointments(
                db=db,
                arguments=arguments,
            )

        if tool_name == "cancel_appointment":
            return run_cancel_appointment(
                db=db,
                arguments=arguments,
                user_message=user_message,
            )
            
        if tool_name == "reschedule_appointment":
            return run_reschedule_appointment(
                db=db,
                arguments=arguments,
                user_message=user_message,
            )

        if tool_name == "register_patient":
            return run_register_patient(
                db=db,
                arguments=arguments,
                user_message=user_message,
            )
            
        if tool_name == "escalate_emergency":
            return run_escalate_emergency(
                db=db,
                arguments=arguments,
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