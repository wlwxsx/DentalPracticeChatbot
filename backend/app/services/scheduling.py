from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Appointment, Availability, Patient


def find_available_slots(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[Availability]:
    return (
        db.query(Availability)
        .filter(
            Availability.start_time >= start_date,
            Availability.start_time <= end_date,
            Availability.status == "available",
        )
        .order_by(Availability.start_time)
        .all()
    )


def book_appointment(
    db: Session,
    patient_id: int,
    slot_id: int,
    appointment_type: str | None = None,
    emergency_summary: str | None = None,
) -> Appointment:
    slot = db.query(Availability).filter(
        Availability.id == slot_id
    ).first()

    if slot is None:
        raise ValueError("Appointment slot does not exist.")

    if slot.status != "available":
        raise ValueError("Appointment slot is no longer available.")

    appointment = Appointment(
        patient_id=patient_id,
        slot_id=slot.id,
        appointment_type=appointment_type or "general",
        status="scheduled",
        emergency_summary=emergency_summary,
    )

    slot.status = "booked"
    db.add(appointment)

    try:
        db.commit()
        db.refresh(appointment)
        return appointment
    except Exception:
        db.rollback()
        raise


def book_family_appointments(
    db: Session,
    bookings: list[dict[str, int | str]],
) -> list[Appointment]:
    """Book consecutive appointments for multiple family members atomically."""
    if len(bookings) < 2:
        raise ValueError("Family scheduling requires at least two appointments.")

    slot_ids = [booking["slot_id"] for booking in bookings]
    patient_ids = [booking["patient_id"] for booking in bookings]
    if len(slot_ids) != len(set(slot_ids)):
        raise ValueError("Each family member must have a different appointment slot.")
    if len(patient_ids) != len(set(patient_ids)):
        raise ValueError("Each family appointment must belong to a different family member.")

    slots = (
        db.query(Availability)
        .filter(Availability.id.in_(slot_ids))
        .all()
    )
    slots_by_id = {slot.id: slot for slot in slots}
    if len(slots_by_id) != len(slot_ids):
        raise ValueError("One or more family appointment slots do not exist.")

    ordered_slots = [slots_by_id[slot_id] for slot_id in slot_ids]
    for slot in ordered_slots:
        if slot.status != "available":
            raise ValueError("All family appointment slots must be available.")

    for previous, current in zip(ordered_slots, ordered_slots[1:]):
        if previous.end_time != current.start_time:
            raise ValueError("Family appointment slots must be back-to-back with no gaps.")

    patients = {
        patient_id
        for (patient_id,) in db.query(Patient.id)
        .filter(Patient.id.in_(patient_ids))
        .all()
    }
    if patients != set(patient_ids):
        raise ValueError("One or more family members do not exist.")

    appointments = [
        Appointment(
            patient_id=booking["patient_id"],
            slot_id=booking["slot_id"],
            appointment_type=booking.get("appointment_type", "general"),
            status="scheduled",
        )
        for booking, slot in zip(bookings, ordered_slots)
    ]
    for slot in ordered_slots:
        slot.status = "booked"
    db.add_all(appointments)

    try:
        db.commit()
        for appointment in appointments:
            db.refresh(appointment)
        return appointments
    except Exception:
        db.rollback()
        raise
    
def cancel_appointment(
    db: Session,
    appointment_id: int,
) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise ValueError("Appointment does not exist.")

    if appointment.status == "cancelled":
        raise ValueError("Appointment is already cancelled.")

    slot = (
        db.query(Availability)
        .filter(Availability.id == appointment.slot_id)
        .first()
    )

    appointment.status = "cancelled"

    if slot is not None:
        slot.status = "available"

    try:
        db.commit()
        db.refresh(appointment)
        return appointment
    except Exception:
        db.rollback()
        raise
    
def reschedule_appointment(
    db: Session,
    appointment_id: int,
    new_slot_id: int,
) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id)
        .first()
    )

    if appointment is None:
        raise ValueError("Appointment does not exist.")

    if appointment.status != "scheduled":
        raise ValueError("Only scheduled appointments can be rescheduled.")

    if appointment.slot_id == new_slot_id:
        raise ValueError("Please select a different appointment slot.")

    new_slot = (
        db.query(Availability)
        .filter(Availability.id == new_slot_id)
        .first()
    )

    if new_slot is None:
        raise ValueError("The new appointment slot does not exist.")

    if new_slot.status != "available":
        raise ValueError("The new appointment slot is no longer available.")

    old_slot = (
        db.query(Availability)
        .filter(Availability.id == appointment.slot_id)
        .first()
    )

    if old_slot is not None:
        old_slot.status = "available"

    new_slot.status = "booked"
    appointment.slot_id = new_slot.id

    try:
        db.commit()
        db.refresh(appointment)
        return appointment
    except Exception:
        db.rollback()
        raise
    
def get_patient_appointments(
    db: Session,
    patient_id: int,
) -> list[Appointment]:
    return (
        db.query(Appointment)
        .filter(Appointment.patient_id == patient_id)
        .order_by(Appointment.id.desc())
        .all()
    )