from celery import Celery

from app.core.config import settings

celery = Celery(
    "ragbot",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Task modules Celery must import to register the tasks.
celery.conf.imports = (
    "app.tasks.faq_tasks",
    "app.tasks.summary_tasks",
)

celery.conf.task_routes = {
    "app.tasks.*": {"queue": "rag-queue"},
}

# Pin serialization to JSON explicitly rather than relying on the library
# default: a queue that accepts pickle turns "attacker can write to Redis"
# into remote code execution in the worker. JSON cannot carry code.
celery.conf.task_serializer = "json"
celery.conf.result_serializer = "json"
celery.conf.accept_content = ["json"]

# Without time limits a hung LLM/HTTP call pins a worker forever, and a
# handful of stuck tasks silently takes out all background processing.
# Soft limit raises an exception the task can clean up from; the hard
# limit kills the worker process if it ignores that.
celery.conf.task_soft_time_limit = 120
celery.conf.task_time_limit = 180
