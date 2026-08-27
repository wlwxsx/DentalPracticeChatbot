from datetime import datetime, timedelta

from app.database import SessionLocal
from app.services.scheduling import find_available_slots


db = SessionLocal()

try:
    slots = find_available_slots(
        db=db,
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=14),
    )

    print(f"Found {len(slots)} available slots.")

    for slot in slots[:5]:
        print(
            f"ID: {slot.id} | "
            f"{slot.start_time:%A, %B %d at %I:%M %p}"
        )
finally:
    db.close()