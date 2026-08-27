from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from datetime import datetime

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.services.scheduling import find_available_slots
from app import models

from app.services.scheduling import (
    book_appointment,
    cancel_appointment,
    find_available_slots,
    reschedule_appointment,
)

class BookingRequest(BaseModel):
    patient_id: int
    slot_id: int


class RescheduleRequest(BaseModel):
    new_slot_id: int
    
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