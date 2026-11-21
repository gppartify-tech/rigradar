"""Celery tasks.

Only one scrape may run at a time (they share the product-matching tables), which
is enforced with a Redis lock. Price-alert e-mails go through their own task so a
slow SMTP server never blocks scraping.
"""
from __future__ import annotations

import logging

import redis

from app.celery_app import celery_app
from app.config import settings
from app.database import session_scope
from app.scraping.registry import SCRAPERS
from app.scraping.runner import run_scrape
from app.services.email import send_notification_email

log = logging.getLogger(__name__)
LOCK_NAME = "partify:scrape-lock"


def _queue_emails(notification_ids: list[int]) -> None:
    for note_id in notification_ids:
        send_notification_email_task.delay(note_id)


def _with_lock(fn):
    client = redis.Redis.from_url(settings.redis_url)
    lock = client.lock(LOCK_NAME, timeout=3 * 60 * 60, blocking=False)
    if not lock.acquire():
        log.warning("Another scrape is already running - skipping.")
        return {"status": "skipped", "reason": "another scrape is running"}
    try:
        return fn()
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass


@celery_app.task(name="app.tasks.scrape_store")
def scrape_store(store_slug: str, trigger: str = "manual") -> dict:
    return _with_lock(lambda: run_scrape(store_slug, trigger=trigger, on_notifications=_queue_emails))


@celery_app.task(name="app.tasks.scrape_all_stores")
def scrape_all_stores(trigger: str = "schedule") -> list[dict] | dict:
    def run_all():
        return [run_scrape(slug, trigger=trigger, on_notifications=_queue_emails) for slug in SCRAPERS]

    return _with_lock(run_all)


@celery_app.task(name="app.tasks.send_notification_email", autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def send_notification_email_task(notification_id: int) -> bool:
    with session_scope() as db:
        return send_notification_email(db, notification_id)
