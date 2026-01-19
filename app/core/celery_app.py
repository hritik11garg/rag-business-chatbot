from celery import Celery

celery = Celery(
    "ragbot",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

# Force Celery to import your task module
celery.conf.imports = (
    "app.tasks.faq_tasks",
)

celery.conf.task_routes = {
    "app.tasks.*": {"queue": "rag-queue"},
}
