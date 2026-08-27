import re
import os
import smtplib
import logging
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.models import EmergencyEscalation, Patient

logger = logging.getLogger(__name__)


LIFE_THREATENING_PHRASES = (
    "trouble breathing",
    "difficulty breathing",
    "can't breathe",
    "cannot breathe",
    "uncontrolled bleeding",
    "bleeding won't stop",
    "severe facial swelling",
    "face is badly swollen",
    "serious facial injury",
)

URGENT_DENTAL_PHRASES = (
    "severe dental pain",
    "severe tooth pain",
    "knocked out tooth",
    "broken tooth",
    "dental abscess",
    "tooth infection",
)


def _contains_phrase(message: str, phrases: tuple[str, ...]) -> bool:
    normalized_message = message.lower()
    return any(phrase in normalized_message for phrase in phrases)


def is_life_threatening(message: str) -> bool:
    return _contains_phrase(message, LIFE_THREATENING_PHRASES)


def is_non_life_threatening_emergency(message: str) -> bool:
    return (
        not is_life_threatening(message)
        and _contains_phrase(message, URGENT_DENTAL_PHRASES)
    )


def is_potential_emergency(message: str) -> bool:
    return is_life_threatening(message) or is_non_life_threatening_emergency(message)


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


def notify_staff(
    summary: str,
    contact_phone: str | None = None,
    patient: Patient | None = None,
    appointment_details: str | None = None,
) -> bool:
    """Send an optional staff email; return False when email is not configured."""
    recipient = os.getenv("STAFF_EMAIL")
    smtp_host = os.getenv("SMTP_HOST")
    if not recipient or not smtp_host:
        return False

    patient_details = "No matching patient record was found."
    if patient is not None:
        patient_details = (
            f"Name: {patient.full_name}\n"
            f"Phone: {patient.phone}\n"
            f"Date of birth: {patient.date_of_birth.isoformat()}\n"
            f"Insurance: {patient.insurance_name or 'None'}"
        )
    elif contact_phone:
        patient_details = f"Contact phone: {contact_phone}"

    message = EmailMessage()
    message["Subject"] = "Dental practice emergency follow-up"
    message["From"] = os.getenv("SMTP_FROM", recipient)
    message["To"] = recipient
    message.set_content(
        "A patient reported an urgent dental concern. Please follow up.\n\n"
        f"Patient information:\n{patient_details}\n\n"
        f"Reported concern:\n{summary}\n\n"
        f"Appointment follow-up:\n{appointment_details or 'No appointment was booked automatically.'}"
    )

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        logger.warning("Staff emergency email was not sent: invalid SMTP_PORT")
        return False
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    try:
        with smtplib.SMTP(smtp_host, port, timeout=10) as smtp:
            if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException, ValueError):
        logger.exception("Staff emergency email could not be sent")
        return False