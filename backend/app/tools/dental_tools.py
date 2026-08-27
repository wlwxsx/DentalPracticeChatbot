from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.services.patients import create_patient, normalize_phone, verify_patient
from app.services.scheduling import (
    book_appointment,
    book_family_appointments,
    cancel_appointment,
    find_available_slots,
    get_patient_appointments,
    reschedule_appointment,
)
from app.models import EmergencyEscalation, Patient
from app.services.emergencies import create_emergency_escalation, notify_staff

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
        },
        "required": ["start_date", "end_date"],
    },
}

VERIFY_PATIENT_TOOL = {
    "type": "function",
    "name": "verify_patient",
    "description": (
        "Verify a returning patient using their entire legal name, phone number, "
        "and date of birth."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "full_name": {
                "type": "string",
                "description": "The patient's entire legal name.",
            },
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
        "required": ["full_name", "phone", "date_of_birth"],
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
            "appointment_type": {
                "type": "string",
                "enum": ["general", "cleaning", "emergency"],
                "description": "Appointment type requested by the patient.",
            },
            "emergency_summary": {
                "type": "string",
                "description": "Emergency situation to store in the appointment notes, when applicable.",
            },

        },
        "required": [
            "patient_id",
            "slot_id",
            "appointment_type",
        ],
    },
}

BOOK_FAMILY_APPOINTMENTS_TOOL = {
    "type": "function",
    "name": "book_family_appointments",
    "description": (
        "Book multiple confirmed family appointments in consecutive, back-to-back "
        "available slots. The operation is atomic: book none if the full block "
        "cannot be scheduled."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "bookings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "patient_id": {"type": "integer"},
                        "slot_id": {"type": "integer"},
                        "appointment_type": {
                            "type": "string",
                            "enum": ["general", "cleaning", "emergency"],
                        },
                    },
                    "required": ["patient_id", "slot_id", "appointment_type"],
                },
                "minItems": 2,
            },
        },
        "required": ["bookings"],
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

GET_PRACTICE_INFORMATION_TOOL = {
    "type": "function",
    "name": "get_practice_information",
    "description": (
        "Returns verified information about office hours, location, insurance, "
        "payment, self-pay, membership, and financing."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "enum": [
                    "hours",
                    "location",
                    "insurance",
                    "payment",
                    "self_pay",
                    "membership",
                    "financing",
                ],
                "description": "The practice-information topic requested.",
            }
        },
        "required": ["topic"],
    },
}

PRACTICE_INFORMATION = {
    "hours": {
        "message": (
            "The dental practice is open Monday through Saturday from "
            "8:00 AM to 6:00 PM and is closed on Sunday."
        ),
    },
    "location": {
        "message": (
            "A street address was not provided. Please contact the front desk "
            "for the practice location."
        ),
    },
    "insurance": {
        "message": (
            "The practice accepts all major dental insurance plans. "
            "Coverage depends on the patient's individual plan and should "
            "be confirmed with the dental office."
        ),
    },
    "payment": {
        "message": (
            "Insurance and self-pay options are available. Exact prices and "
            "payment arrangements should be confirmed with the front desk."
        ),
    },
    "self_pay": {
        "message": (
            "Self-pay options are available for patients without insurance."
        ),
    },
    "membership": {
        "message": (
            "Membership options may be available for patients without "
            "insurance. Please contact the front desk for current details."
        ),
    },
    "financing": {
        "message": (
            "Financing options may be available for patients without "
            "insurance. Please contact the front desk for eligibility and terms."
        ),
    },
}



TOOLS = [
    FIND_AVAILABLE_SLOTS_TOOL,
    VERIFY_PATIENT_TOOL,
    REGISTER_PATIENT_TOOL,
    BOOK_APPOINTMENT_TOOL,
    BOOK_FAMILY_APPOINTMENTS_TOOL,
    LIST_APPOINTMENTS_TOOL,
    CANCEL_APPOINTMENT_TOOL,
    RESCHEDULE_APPOINTMENT_TOOL,
    ESCALATE_EMERGENCY_TOOL,
    GET_PRACTICE_INFORMATION_TOOL
]


def run_find_available_slots(
    db: Session,
    arguments: dict,
) -> dict:
    slots = find_available_slots(
        db=db,
        start_date=datetime.fromisoformat(arguments["start_date"]),
        end_date=datetime.fromisoformat(arguments["end_date"]),
    )

    return {
        "total_count": len(slots),
        "slots": [
            {
                "id": slot.id,
                "day_of_week": slot.start_time.strftime("%A"),
                "date": slot.start_time.date().isoformat(),
                "start_time": slot.start_time.isoformat(),
                "end_time": slot.end_time.isoformat(),
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
        full_name=arguments["full_name"],
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
        appointment_type=arguments.get("appointment_type", "general"),
        emergency_summary=arguments.get("emergency_summary"),
    )

    if appointment.appointment_type == "emergency":
        emergency_summary = (
            arguments.get("emergency_summary")
            or db.query(EmergencyEscalation.summary)
            .filter(EmergencyEscalation.patient_id == appointment.patient_id)
            .order_by(EmergencyEscalation.id.desc())
            .scalar()
            or user_message
        )
        appointment.emergency_summary = emergency_summary
        db.commit()
        db.refresh(appointment)
        notify_staff(
            summary=emergency_summary,
            contact_phone=appointment.patient.phone,
            patient=appointment.patient,
            appointment_details=(
                "Emergency appointment booked for "
                f"{appointment.slot.start_time.isoformat()}."
            ),
        )

    return {
        "success": True,
        "appointment_id": appointment.id,
        "status": appointment.status,
        "appointment_type": appointment.appointment_type,
        "emergency_summary": appointment.emergency_summary,
        "start_time": appointment.slot.start_time.isoformat(),
        "end_time": appointment.slot.end_time.isoformat(),
    } 


def run_book_family_appointments(
    db: Session,
    arguments: dict,
    user_message: str,
) -> dict:
    if not any(
        phrase in user_message.lower().strip()
        for phrase in ("yes", "confirm", "book it", "go ahead", "yes please")
    ):
        raise ValueError(
            "The family appointments have not been booked. Ask for explicit confirmation."
        )

    appointments = book_family_appointments(db=db, bookings=arguments["bookings"])
    return {
        "success": True,
        "appointments": [
            {
                "appointment_id": appointment.id,
                "patient_id": appointment.patient_id,
                "slot_id": appointment.slot_id,
                "start_time": appointment.slot.start_time.isoformat(),
                "end_time": appointment.slot.end_time.isoformat(),
            }
            for appointment in appointments
        ],
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

    patient = None
    if contact_phone:
        normalized_phone = normalize_phone(contact_phone)
        patient = (
            db.query(Patient)
            .filter(Patient.phone == normalized_phone)
            .first()
        )

    escalation = create_emergency_escalation(
        db=db,
        summary=arguments["summary"],
        patient_id=patient.id if patient else None,
        contact_phone=contact_phone,
    )

    appointment = None
    appointment_message = "No appointment was booked automatically."
    if patient is not None:
        slots = find_available_slots(
            db=db,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=180),
        )
        if slots:
            appointment = book_appointment(
                db=db,
                patient_id=patient.id,
                slot_id=slots[0].id,
                appointment_type="emergency",
                emergency_summary=arguments["summary"],
            )
            appointment_message = (
                "Booked the earliest available emergency appointment for "
                f"{appointment.slot.start_time.isoformat()}."
            )

    notification_sent = notify_staff(
        summary=arguments["summary"],
        contact_phone=contact_phone,
        patient=patient,
        appointment_details=appointment_message,
    )

    return {
        "success": True,
        "status": escalation.status,
        "message": (
            f"Emergency escalation recorded. "
            f"{'Staff email sent.' if notification_sent else 'Staff email could not be sent.'} "
            f"{appointment_message}"
        ),
        "notification_sent": notification_sent,
        "appointment_booked": appointment is not None,
        "appointment_type": appointment.appointment_type if appointment else None,
        "appointment_id": appointment.id if appointment else None,
    }
    
def get_practice_information(topic: str) -> dict:
    normalized_topic = topic.strip().lower()
    information = PRACTICE_INFORMATION.get(normalized_topic)

    if information is None:
        return {
            "success": False,
            "message": "That practice-information topic is not available.",
        }

    return {
        "success": True,
        "topic": normalized_topic,
        **information,
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

        if tool_name == "book_family_appointments":
            return run_book_family_appointments(
                db=db,
                arguments=arguments,
                user_message=user_message,
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
        if tool_name == "get_practice_information":
            return get_practice_information(
                topic=arguments["topic"],
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