from app.core.celery_app import celery


@celery.task(name="app.tasks.generate_faqs_task")
def generate_faqs_task(chunks, document_id, organization_id):
    from app.services.faq_generator import generate_and_store_faqs
    generate_and_store_faqs(chunks, document_id, organization_id)
