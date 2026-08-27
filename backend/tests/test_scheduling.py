from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import Appointment
from app.services.scheduling import (
    book_appointment,
    book_family_appointments,
    cancel_appointment,
    find_available_slots,
    get_patient_appointments,
    reschedule_appointment,
)


def test_find_available_slots_filters_type_status_and_date(db: Session, slots):
    start = datetime(2026, 8, 28, 8, 0)
    end = start + timedelta(hours=5)

    results = find_available_slots(db, start, end, appointment_type="general")

    assert [slot.id for slot in results] == [slots[0].id, slots[1].id]


def test_book_appointment_marks_slot_booked_and_prevents_double_booking(
    db: Session,
    patient,
    slots,
):
    appointment = book_appointment(db, patient.id, slots[0].id)

    assert appointment.patient_id == patient.id
    assert appointment.slot_id == slots[0].id
    assert appointment.status == "scheduled"
    assert db.get(type(slots[0]), slots[0].id).status == "booked"

    with pytest.raises(ValueError, match="no longer available"):
        book_appointment(db, patient.id, slots[0].id)


def test_book_appointment_rejects_missing_slot(db: Session, patient):
    with pytest.raises(ValueError, match="does not exist"):
        book_appointment(db, patient.id, 999)


def test_book_family_appointments_books_consecutive_slots_atomically(
    db: Session,
    patient,
    slots,
):
    second_patient = type(patient)(
        full_name="Taylor Morgan",
        phone="4165550124",
        date_of_birth=patient.date_of_birth,
    )
    db.add(second_patient)
    db.commit()
    db.refresh(second_patient)

    appointments = book_family_appointments(
        db,
        [
            {"patient_id": patient.id, "slot_id": slots[0].id},
            {"patient_id": second_patient.id, "slot_id": slots[1].id},
        ],
    )

    assert [appointment.slot_id for appointment in appointments] == [
        slots[0].id,
        slots[1].id,
    ]
    assert all(appointment.status == "scheduled" for appointment in appointments)


def test_book_family_appointments_does_not_partially_book_when_not_consecutive(
    db: Session,
    patient,
    slots,
):
    second_patient = type(patient)(
        full_name="Taylor Morgan",
        phone="4165550124",
        date_of_birth=patient.date_of_birth,
    )
    db.add(second_patient)
    db.commit()
    db.refresh(second_patient)

    with pytest.raises(ValueError, match="back-to-back"):
        book_family_appointments(
            db,
            [
                {"patient_id": patient.id, "slot_id": slots[0].id},
                {"patient_id": second_patient.id, "slot_id": slots[2].id},
            ],
        )

    assert db.query(Appointment).count() == 0
    assert db.get(type(slots[0]), slots[0].id).status == "available"


def test_cancel_appointment_releases_slot(db: Session, patient, slots):
    appointment = book_appointment(db, patient.id, slots[0].id)

    cancelled = cancel_appointment(db, appointment.id)

    assert cancelled.status == "cancelled"
    assert db.get(type(slots[0]), slots[0].id).status == "available"
    with pytest.raises(ValueError, match="already cancelled"):
        cancel_appointment(db, appointment.id)


def test_reschedule_appointment_moves_booking_and_releases_old_slot(
    db: Session,
    patient,
    slots,
):
    appointment = book_appointment(db, patient.id, slots[0].id)

    rescheduled = reschedule_appointment(db, appointment.id, slots[1].id)

    assert rescheduled.slot_id == slots[1].id
    assert db.get(type(slots[0]), slots[0].id).status == "available"
    assert db.get(type(slots[1]), slots[1].id).status == "booked"


def test_reschedule_rejects_incompatible_or_booked_slot(db: Session, patient, slots):
    appointment = book_appointment(db, patient.id, slots[0].id)

    with pytest.raises(ValueError, match="does not support"):
        reschedule_appointment(db, appointment.id, slots[2].id)

    with pytest.raises(ValueError, match="no longer available"):
        reschedule_appointment(db, appointment.id, slots[3].id)


def test_get_patient_appointments_returns_patient_records(db: Session, patient, slots):
    appointment = book_appointment(db, patient.id, slots[0].id)

    appointments = get_patient_appointments(db, patient.id)

    assert len(appointments) == 1
    assert appointments[0].id == appointment.id
    assert isinstance(appointments[0], Appointment)
