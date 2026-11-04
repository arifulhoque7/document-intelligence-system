"""Celery app and tasks. Long OCR / LLM work runs here, never in the API process."""

import uuid

from celery import Celery

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.llm import LLMError
from app.services.pipeline import mark_failed, process_document

cfg = get_settings()
celery_app = Celery("docintel", broker=cfg.redis_url, backend=None)
celery_app.conf.update(
    task_acks_late=True,  # a crashed worker's job goes back to the queue
    worker_prefetch_multiplier=1,  # OCR jobs are long: one at a time per process
    task_reject_on_worker_lost=True,
    task_always_eager=cfg.celery_eager,
    task_time_limit=3 * 60 * 60,
    broker_connection_retry_on_startup=True,
)
MAX_RETRIES = 3


@celery_app.task(bind=True, name="process_document", max_retries=MAX_RETRIES)
def process_document_task(self, doc_id: str) -> None:
    with SessionLocal() as db:
        try:
            process_document(db, uuid.UUID(doc_id))
        except LLMError as e:  # only transient errors reach here
            if self.request.retries >= MAX_RETRIES or cfg.celery_eager:
                mark_failed(db, uuid.UUID(doc_id), f"{e} (gave up after {self.request.retries + 1} attempts)")
                return
            raise self.retry(countdown=15 * 2**self.request.retries) from e


@celery_app.task(name="reembed_all")
def reembed_all_task() -> None:
    """Re-embed every invoice after the embedding provider or model changes."""
    from sqlalchemy import select

    from app.models import Invoice
    from app.services.pipeline import embed_invoices

    with SessionLocal() as db:
        invoices = db.scalars(select(Invoice)).all()
        for i in range(0, len(invoices), 64):
            embed_invoices(db, invoices[i : i + 64])
            db.commit()


def enqueue(doc_id: uuid.UUID) -> None:
    process_document_task.delay(str(doc_id))
