from datetime import date, datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.models import Availability, Patient


Base.metadata.create_all(bind=engine)

BOOKING_WINDOW_DAYS = 180

def seed_database():
    db = SessionLocal()

    try:
        if db.query(Patient).count() == 0:
            db.add(
                Patient(
                    full_name="Alex Morgan",
                    phone="4165550123",
                    date_of_birth=date(1995, 6, 15),
                    insurance_name="Sun Life",
                )
            )

        if db.query(Availability).count() == 0:
            today = datetime.now().date()

            for day_offset in range(1, BOOKING_WINDOW_DAYS + 1): # four month for now
                slot_date = today + timedelta(days=day_offset)

                # Skip weekends.
                if slot_date.weekday() == 6:
                    continue

                for hour in range(8, 18):
                    start_time = datetime.combine(
                        slot_date,
                        datetime.min.time(),
                    ).replace(hour=hour)

                    db.add(
                        Availability(
                            start_time=start_time,
                            end_time=start_time + timedelta(hours=1),
                            appointment_type="general",
                            status="available",
                        )
                    )

        db.commit()
        print("Database seeded successfully.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()