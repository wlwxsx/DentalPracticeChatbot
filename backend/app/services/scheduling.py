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