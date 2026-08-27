from datetime import date

from sqlalchemy.orm import Session

from app.models import EmergencyEscalation
from app.tools.dental_tools import run_escalate_emergency
from app.tools.dental_tools import run_book_appointment
from app.services.emergencies import (
    create_emergency_escalation,
    extract_phone_number,
    is_life_threatening,
    is_non_life_threatening_emergency,
    is_potential_emergency,
    notify_staff,
)


def test_is_potential_emergency_detects_urgent_phrases():
    assert is_potential_emergency("I have severe facial swelling") is True
    assert is_potential_emergency("My tooth feels a little sensitive") is False


def test_emergency_classification_separates_life_threatening_and_urgent():
    assert is_life_threatening("I cannot breathe") is True
    assert is_non_life_threatening_emergency("I have severe tooth pain") is True
    assert is_life_threatening("I have severe tooth pain") is False


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


def test_notify_staff_is_noop_when_email_is_not_configured(monkeypatch):
    monkeypatch.delenv("STAFF_EMAIL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)

    assert notify_staff("Severe tooth pain") is False


def test_notify_staff_sends_patient_context(monkeypatch, patient):
    sent_messages = []

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def starttls(self):
            pass

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("STAFF_EMAIL", "staff@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setattr("app.services.emergencies.smtplib.SMTP", FakeSMTP)

    assert notify_staff("Severe tooth pain", patient=patient) is True
    assert len(sent_messages) == 1
    body = sent_messages[0].get_content()
    assert "Alex Morgan" in body
    assert "4165550123" in body
    assert "Severe tooth pain" in body

    assert "No appointment was booked automatically" in body


def test_chat_uses_local_response_for_non_life_threatening_emergency(
    db: Session,
    monkeypatch,
):
    from app.services import chat

    monkeypatch.setattr(chat, "notify_staff", lambda *args: True)

    response, interaction_id = chat.generate_chat_response(
        db,
        "I have severe tooth pain. My phone is 416-555-0199.",
    )

    assert "not life-threatening" in response
    assert "dental office promptly" in response
    assert interaction_id is None


def test_chat_books_earliest_slot_for_known_patient(
    db: Session,
    patient,
    slots,
    monkeypatch,
):
    from app.services import chat

    notifications = []
    monkeypatch.setattr(chat, "find_available_slots", lambda *args, **kwargs: slots[2:3])
    monkeypatch.setattr(chat, "notify_staff", lambda *args: notifications.append(args))

    response, _ = chat.generate_chat_response(
        db,
        "I have severe tooth pain. My phone is 416-555-0123.",
    )

    assert "Booked the earliest available appointment" in response
    assert len(notifications) == 1
    assert len(patient.appointments) == 1
    assert patient.appointments[0].slot_id == slots[2].id
    assert patient.appointments[0].appointment_type == "emergency"
    assert patient.appointments[0].emergency_summary == (
        "I have severe tooth pain. My phone is 416-555-0123."
    )


def test_emergency_tool_books_emergency_appointment_and_escalates(
    db: Session,
    patient,
    slots,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.tools.dental_tools.notify_staff",
        lambda **kwargs: True,
    )

    result = run_escalate_emergency(
        db,
        {
            "summary": "My teeth are hurting badly.",
            "contact_phone": "416-555-0123",
        },
    )

    assert result["appointment_booked"] is True
    assert result["appointment_type"] == "emergency"
    assert len(patient.appointments) == 1
    assert patient.appointments[0].emergency_summary == "My teeth are hurting badly."
    assert db.query(EmergencyEscalation).count() == 1


def test_emergency_tool_emails_unknown_patient_details(
    db: Session,
    monkeypatch,
):
    sent_messages = []

    def fake_notify_staff(**kwargs):
        sent_messages.append(kwargs)
        return True

    monkeypatch.setattr("app.tools.dental_tools.notify_staff", fake_notify_staff)

    result = run_escalate_emergency(
        db,
        {
            "summary": "My tooth is broken and painful.",
            "contact_phone": "234-234-2345",
        },
    )

    assert result["notification_sent"] is True
    assert result["appointment_booked"] is False
    assert sent_messages[0]["contact_phone"] == "234-234-2345"
    assert sent_messages[0]["patient"] is None
    assert db.query(EmergencyEscalation).count() == 1


def test_emergency_booking_notifies_staff_and_stores_notes(
    db: Session,
    patient,
    slots,
    monkeypatch,
):
    notifications = []
    monkeypatch.setattr(
        "app.tools.dental_tools.notify_staff",
        lambda **kwargs: notifications.append(kwargs) or True,
    )
    create_emergency_escalation(
        db,
        summary="My teeth have been hurting and I need an emergency appointment.",
        patient_id=patient.id,
        contact_phone=patient.phone,
    )

    result = run_book_appointment(
        db,
        {
            "patient_id": patient.id,
            "slot_id": slots[2].id,
            "appointment_type": "emergency",
        },
        "Yes, please book it.",
    )

    assert result["appointment_type"] == "emergency"
    assert result["emergency_summary"] == (
        "My teeth have been hurting and I need an emergency appointment."
    )
    assert len(notifications) == 1
    assert notifications[0]["patient"] is patient
