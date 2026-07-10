from celery import Celery

from app.core.config import settings

celery = Celery(
    "ragbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Force Celery to import your task module
celery.conf.imports = (
    "app.tasks.faq_tasks",
    "app.tasks.summary_tasks",
)

celery.conf.task_routes = {
    "app.tasks.*": {"queue": "rag-queue"},
}
