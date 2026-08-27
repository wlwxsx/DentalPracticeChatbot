from datetime import date

from sqlalchemy.orm import Session

from app.models import Patient


def normalize_phone(phone: str) -> str:
    return "".join(character for character in phone if character.isdigit())


def create_patient(
    db: Session,
    full_name: str,
    phone: str,
    date_of_birth: date,
    insurance_name: str | None = None,
) -> Patient:
    normalized_phone = normalize_phone(phone)

    if len(normalized_phone) < 10:
        raise ValueError("Please provide a valid phone number.")

    existing_patient = (
        db.query(Patient)
        .filter(Patient.phone == normalized_phone)
        .first()
    )

    if existing_patient is not None:
        raise ValueError("A patient with this phone number already exists.")

    patient = Patient(
        full_name=full_name.strip(),
        phone=normalized_phone,
        date_of_birth=date_of_birth,
        insurance_name=insurance_name,
    )

    db.add(patient)

    try:
        db.commit()
        db.refresh(patient)
        return patient
    except Exception:
        db.rollback()
        raise


def verify_patient(
    db: Session,
    phone: str,
    date_of_birth: date,
) -> Patient:
    normalized_phone = normalize_phone(phone)

    patient = (
        db.query(Patient)
        .filter(
            Patient.phone == normalized_phone,
            Patient.date_of_birth == date_of_birth,
        )
        .first()
    )

    if patient is None:
        raise ValueError(
            "We could not verify a patient with those details."
        )

    return patient