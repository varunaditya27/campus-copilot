from celery import Celery
from celery.schedules import crontab

from app.core.clock import CAMPUS_TIMEZONE
from app.core.config import REDIS_URL
from app.services import scheduled_notices

# Two processes run this: `celery -A app.worker:celery_app worker` does the jobs, and
# `celery -A app.worker:celery_app beat` starts them on time. Run exactly one beat, or every job runs twice.
celery_app = Celery("campus_copilot", broker=REDIS_URL or "memory://")
celery_app.conf.timezone = CAMPUS_TIMEZONE.key
celery_app.conf.beat_schedule = {
    "event-reminders": {"task": "app.worker.send_event_reminders", "schedule": crontab(hour=8, minute=0)},
    "attendance-warnings": {
        "task": "app.worker.warn_low_attendance",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    },
}


@celery_app.task(name="app.worker.send_event_reminders")
def send_event_reminders() -> int:
    return scheduled_notices.send_event_reminders()


@celery_app.task(name="app.worker.warn_low_attendance")
def warn_low_attendance() -> int:
    return scheduled_notices.warn_low_attendance()
