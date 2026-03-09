# Production Dockerfile for Clariona Backend
# Used for API, streaming pipeline, and cycle-runner services
FROM python:3.11-slim

WORKDIR /app

# System deps: build-essential for compiling packages, libpq for PostgreSQL, curl for healthchecks and cycle-runner
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p logs/collectors data/raw data/processed

ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# Default: run API (overridden in docker-compose per service)
EXPOSE 8000
CMD ["uvicorn", "src.api.service:app", "--host", "0.0.0.0", "--port", "8000"]
