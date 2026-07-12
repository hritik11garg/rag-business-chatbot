# Runtime image for the API and the Celery worker (same image, two
# commands — see docker-compose.yml). Built on slim Python with
# CPU-only torch: the default PyPI wheel drags in ~2.5 GB of CUDA
# libraries that are useless in a container without a GPU.

FROM python:3.11-slim

# HF_HUB_DISABLE_XET: the xet transfer backend hangs in some container
# networks; plain HTTPS download of MiniLM (~90MB) is reliable.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HUB_DISABLE_XET=1

WORKDIR /app

# Dependencies first, code second — code edits don't bust the pip layer.
COPY requirements/base.txt requirements/base.txt
RUN pip install --timeout 120 --retries 5 torch==2.9.1 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --timeout 120 --retries 5 -r requirements/base.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# The .cache dir must exist owned by appuser BEFORE it becomes a named
# volume mount point — an empty volume copies ownership from the image;
# without this Docker creates it root-owned and HuggingFace can't write.
RUN useradd --create-home appuser \
    && mkdir -p /app/uploads /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser/.cache
USER appuser

EXPOSE 8000

# --no-access-log: the app's structured request log (request_id,
# method, path, status, duration_ms) supersedes uvicorn's access line.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
