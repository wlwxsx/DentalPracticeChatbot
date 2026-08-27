from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models import Patient
from app.services.patients import create_patient, normalize_phone, verify_patient


def test_normalize_phone_keeps_digits_only():
    assert normalize_phone("+1 (416) 555-0123") == "4165550123"


def test_create_patient_normalizes_phone_and_persists_record(db: Session):
    patient = create_patient(
        db,
        full_name="  Jamie Lee  ",
        phone="(416) 555-0199",
        date_of_birth=date(1990, 2, 3),
        insurance_name="Green Shield",
    )

    assert patient.full_name == "Jamie Lee"
    assert patient.phone == "4165550199"
    assert db.query(Patient).count() == 1


def test_create_patient_rejects_short_phone(db: Session):
    with pytest.raises(ValueError, match="valid phone"):
        create_patient(db, "Jamie Lee", "12345", date(1990, 2, 3))


def test_create_patient_rejects_duplicate_normalized_phone(db: Session, patient):
    with pytest.raises(ValueError, match="already exists"):
        create_patient(
            db,
            "Another Patient",
            "+1 (416) 555-0123",
            date(1988, 8, 8),
        )


def test_verify_patient_requires_matching_phone_and_date_of_birth(db: Session, patient):
    verified = verify_patient(
        db,
        "  alex   morgan ",
        "(416) 555-0123",
        date(1995, 6, 15),
    )

    assert verified.id == patient.id

    with pytest.raises(ValueError, match="could not verify"):
        verify_patient(db, "Alex Morgan", "416-555-0123", date(1995, 6, 16))

    with pytest.raises(ValueError, match="could not verify"):
        verify_patient(db, "Alex Smith", "416-555-0123", date(1995, 6, 15))
