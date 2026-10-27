# One codebase, two images:
#   docker build --target api    → FastAPI app + Alembic migrations
#   docker build --target worker → Celery ingestion worker (OCR, ffmpeg, loaders)

FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS api
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS worker
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-bul \
    tesseract-ocr-eng \
    poppler-utils \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-worker.txt .
RUN pip install -r requirements-worker.txt
COPY app/ ./app/
CMD ["celery", "-A", "app.worker", "worker", "--loglevel=info", "--concurrency=2", "-Q", "ingestion"]
