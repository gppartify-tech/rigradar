"""Celery: background jobs + the periodic schedule (Celery beat).

Start a worker:  celery -A app.celery_app worker -Q scraping,default -c 2 -l info
Start beat:      celery -A app.celery_app beat -l info
"""
from datetime import timedelta

from celery import Celery

from app.config import settings

celery_app = Celery("rigradar", broker=settings.redis_url, backend=settings.redis_url, include=["app.tasks"])

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Amman",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=60 * 60 * 24,
    task_default_queue="default",
    # Scraping jobs get their own queue so a long scrape never delays an e-mail.
    task_routes={
        "app.tasks.scrape_store": {"queue": "scraping"},
        "app.tasks.scrape_all_stores": {"queue": "scraping"},
    },
    beat_schedule={
        "scrape-all-stores": {
            "task": "app.tasks.scrape_all_stores",
            "schedule": timedelta(hours=settings.scrape_interval_hours),
            "kwargs": {"trigger": "schedule"},
        },
    },
)
