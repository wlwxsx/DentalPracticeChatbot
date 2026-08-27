from datetime import date

from sqlalchemy.orm import Session

from app.models import EmergencyEscalation
from app.services.emergencies import (
    create_emergency_escalation,
    extract_phone_number,
    is_potential_emergency,
)


def test_is_potential_emergency_detects_urgent_phrases():
    assert is_potential_emergency("I have severe facial swelling") is True
    assert is_potential_emergency("My tooth feels a little sensitive") is False


def test_extract_phone_number_supports_common_formats():
    assert extract_phone_number("Call me at (416) 555-0123") == "4165550123"
    assert extract_phone_number("No phone number here") is None


def test_create_emergency_escalation_persists_pending_record(db: Session, patient):
    escalation = create_emergency_escalation(
        db,
        summary="Uncontrolled bleeding after extraction",
        patient_id=patient.id,
        contact_phone="4165550123",
    )

    stored = db.get(EmergencyEscalation, escalation.id)
    assert stored is not None
    assert stored.patient_id == patient.id
    assert stored.contact_phone == "4165550123"
    assert stored.summary == "Uncontrolled bleeding after extraction"
    assert stored.status == "pending"
