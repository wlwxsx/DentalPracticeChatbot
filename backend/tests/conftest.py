from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Availability, Patient


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def patient(db: Session) -> Patient:
    record = Patient(
        full_name="Alex Morgan",
        phone="4165550123",
        date_of_birth=date(1995, 6, 15),
        insurance_name="Sun Life",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.fixture
def slots(db: Session) -> list[Availability]:
    start = datetime(2026, 8, 28, 9, 0)
    records = [
        Availability(
            start_time=start,
            end_time=start + timedelta(hours=1),
            appointment_type="general",
            status="available",
        ),
        Availability(
            start_time=start + timedelta(hours=1),
            end_time=start + timedelta(hours=2),
            appointment_type="general",
            status="available",
        ),
        Availability(
            start_time=start + timedelta(hours=2),
            end_time=start + timedelta(hours=3),
            appointment_type="emergency",
            status="available",
        ),
        Availability(
            start_time=start + timedelta(hours=3),
            end_time=start + timedelta(hours=4),
            appointment_type="general",
            status="booked",
        ),
    ]
    db.add_all(records)
    db.commit()
    for record in records:
        db.refresh(record)
    return records
