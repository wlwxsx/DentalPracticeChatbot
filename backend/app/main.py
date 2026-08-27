from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from datetime import date, datetime

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models

from app.services.scheduling import (
    book_appointment,
    cancel_appointment,
    find_available_slots,
    get_patient_appointments,
    reschedule_appointment,
)
from app.services.patients import create_patient, verify_patient

from app.services.chat import generate_chat_response


class BookingRequest(BaseModel):
    patient_id: int
    slot_id: int

class RescheduleRequest(BaseModel):
    new_slot_id: int

class PatientRegistrationRequest(BaseModel):
    full_name: str
    phone: str
    date_of_birth: date
    insurance_name: str | None = None


class PatientVerificationRequest(BaseModel):
    phone: str
    date_of_birth: date

class ChatRequest(BaseModel):
    message: str
    previous_interaction_id: str | None = None
    
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Dental Practice Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/slots")
def get_available_slots(
    start_date: datetime,
    end_date: datetime,
    appointment_type: str = "general",
    db: Session = Depends(get_db),
):
    slots = find_available_slots(
        db=db,
        start_date=start_date,
        end_date=end_date,
        appointment_type=appointment_type,
    )

    return [
        {
            "id": slot.id,
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "appointment_type": slot.appointment_type,
        }
        for slot in slots
    ]
    
@app.post(
    "/appointments",
    status_code=201,
    responses={
        400: {
            "description": "Appointment slot is no longer available",
        }
    },
)
def create_appointment(
    request: BookingRequest,
    db: Session = Depends(get_db),
):
    try:
        appointment = book_appointment(
            db=db,
            patient_id=request.patient_id,
            slot_id=request.slot_id,
        )

        return {
            "id": appointment.id,
            "patient_id": appointment.patient_id,
            "slot_id": appointment.slot_id,
            "appointment_type": appointment.appointment_type,
            "status": appointment.status,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

@app.patch(
    "/appointments/{appointment_id}/cancel",
    responses={
        400: {"description": "Appointment cannot be cancelled"},
    },
)
def cancel_existing_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
):
    try:
        appointment = cancel_appointment(
            db=db,
            appointment_id=appointment_id,
        )

        return {
            "id": appointment.id,
            "patient_id": appointment.patient_id,
            "slot_id": appointment.slot_id,
            "status": appointment.status,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

@app.patch(
    "/appointments/{appointment_id}/reschedule",
    responses={
        400: {"description": "Appointment cannot be rescheduled"},
    },
)
def reschedule_existing_appointment(
    appointment_id: int,
    request: RescheduleRequest,
    db: Session = Depends(get_db),
):
    try:
        appointment = reschedule_appointment(
            db=db,
            appointment_id=appointment_id,
            new_slot_id=request.new_slot_id,
        )

        return {
            "id": appointment.id,
            "patient_id": appointment.patient_id,
            "slot_id": appointment.slot_id,
            "appointment_type": appointment.appointment_type,
            "status": appointment.status,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

@app.post(
    "/patients",
    status_code=201,
    responses={
        400: {"description": "Invalid or duplicate patient details"},
    },
)
def register_patient(
    request: PatientRegistrationRequest,
    db: Session = Depends(get_db),
):
    try:
        patient = create_patient(
            db=db,
            full_name=request.full_name,
            phone=request.phone,
            date_of_birth=request.date_of_birth,
            insurance_name=request.insurance_name,
        )

        return {
            "id": patient.id,
            "full_name": patient.full_name,
            "phone": patient.phone,
            "date_of_birth": patient.date_of_birth,
            "insurance_name": patient.insurance_name,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
        
@app.post(
    "/patients/verify",
    responses={
        400: {"description": "Patient verification failed"},
    },
)
def verify_existing_patient(
    request: PatientVerificationRequest,
    db: Session = Depends(get_db),
):
    try:
        patient = verify_patient(
            db=db,
            phone=request.phone,
            date_of_birth=request.date_of_birth,
        )

        return {
            "verified": True,
            "patient_id": patient.id,
            "full_name": patient.full_name,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

@app.get("/patients/{patient_id}/appointments")
def list_patient_appointments(
    patient_id: int,
    db: Session = Depends(get_db),
):
    appointments = get_patient_appointments(
        db=db,
        patient_id=patient_id,
    )

    return [
        {
            "id": appointment.id,
            "appointment_type": appointment.appointment_type,
            "status": appointment.status,
            "slot": {
                "id": appointment.slot.id,
                "start_time": appointment.slot.start_time,
                "end_time": appointment.slot.end_time,
            },
        }
        for appointment in appointments
    ]
    
@app.post(
    "/chat",
    responses={
        429: {"description": "LLM rate limit exceeded"},
        502: {"description": "LLM API request failed"},
    },
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    try:
        message, interaction_id = generate_chat_response(
            db=db,
            message=request.message,
            previous_interaction_id=request.previous_interaction_id,
        )

        return {
            "message": message,
            "interaction_id": interaction_id,
        }

    except Exception as error:
        print(f"LLM error: {type(error).__name__}: {error}")

        raise HTTPException(
            status_code=502,
            detail="The assistant is temporarily unavailable.",
        ) from error