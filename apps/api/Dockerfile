# Production image for apps/api. One image, two entrypoints — the FastAPI
# process (default CMD) and the Celery worker (override CMD at run time,
# e.g. `docker run <image> celery -A app.workers.celery_app worker
# --loglevel=info`) — same dependencies, same code, no second Dockerfile.
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
