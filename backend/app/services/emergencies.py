import re

from sqlalchemy.orm import Session

from app.models import EmergencyEscalation


EMERGENCY_PHRASES = (
    "trouble breathing",
    "difficulty breathing",
    "can't breathe",
    "cannot breathe",
    "uncontrolled bleeding",
    "bleeding won't stop",
    "severe facial swelling",
    "face is badly swollen",
    "serious facial injury",
    "severe dental pain",
)


def is_potential_emergency(message: str) -> bool:
    normalized_message = message.lower()

    return any(
        phrase in normalized_message
        for phrase in EMERGENCY_PHRASES
    )


def extract_phone_number(message: str) -> str | None:
    match = re.search(
        r"(?:\+?1[-.\s]?)?"
        r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        message,
    )

    if match is None:
        return None

    return "".join(
        character
        for character in match.group()
        if character.isdigit()
    )[-10:]


def create_emergency_escalation(
    db: Session,
    summary: str,
    patient_id: int | None = None,
    contact_phone: str | None = None,
) -> EmergencyEscalation:
    escalation = EmergencyEscalation(
        patient_id=patient_id,
        contact_phone=contact_phone,
        summary=summary,
        status="pending",
    )

    db.add(escalation)

    try:
        db.commit()
        db.refresh(escalation)
        return escalation
    except Exception:
        db.rollback()
        raise