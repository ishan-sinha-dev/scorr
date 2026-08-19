from celery import Celery

from app.core.config import settings

# No result backend: task outcomes are written straight to Postgres (e.g.
# documents.extraction_status), which is already the source of truth the
# API polls — a second status-tracking system in Celery's own backend
# would be redundant. No Flower, no queue routing, no beat schedule: none
# of that has a demonstrated need yet.
celery_app = Celery("socrr", broker=settings.redis_url)

# Each task module registers its tasks via the @celery_app.task decorator
# as an import side effect. In the FastAPI process that happens for free
# (main.py -> routers -> services -> these modules), but a standalone
# `celery -A app.workers.celery_app worker` process only ever imports this
# file, so without these imports its task registry stays empty and every
# queued task fails with "Received unregistered task of type ...".
from app.workers import ai_extraction, extraction, mapping  # noqa: E402,F401
