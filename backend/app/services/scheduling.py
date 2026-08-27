from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Appointment, Availability


def find_available_slots(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    appointment_type: str = "general",
) -> list[Availability]:
    return (
        db.query(Availability)
        .filter(
            Availability.start_time >= start_date,
            Availability.start_time <= end_date,
            Availability.appointment_type == appointment_type,
            Availability.status == "available",
        )
        .order_by(Availability.start_time)
        .all()
    )


def book_appointment(
    db: Session,
    patient_id: int,
    slot_id: int,
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
        appointment_type=slot.appointment_type,
        status="scheduled",
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

    if new_slot.appointment_type != appointment.appointment_type:
        raise ValueError(
            "The new slot does not support this appointment type."
        )

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