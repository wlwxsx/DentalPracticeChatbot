from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    date_of_birth: Mapped[date] = mapped_column(Date)
    insurance_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="patient",
    )


class Availability(Base):
    __tablename__ = "availability"

    id: Mapped[int] = mapped_column(primary_key=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="available")

    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="slot",
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    slot_id: Mapped[int] = mapped_column(
        ForeignKey("availability.id"),
    )
    appointment_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")
    emergency_summary: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    patient: Mapped["Patient"] = relationship(back_populates="appointments")
    slot: Mapped["Availability"] = relationship(back_populates="appointments")
    
class EmergencyEscalation(Base):
    __tablename__ = "emergency_escalations"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id"),
        nullable=True,
    )
    contact_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    summary: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )