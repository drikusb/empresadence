FROM python:3.15-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# An unprivileged user for the production stage below. uid/gid 1000 is the first
# regular user on most Linux hosts. The chown runs after COPY so that
# /app/staticfiles and /app/mediafiles are owned by this user in the image: the
# named volumes in docker-compose.prod.yml copy that ownership when first created.
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home-dir /app --shell /usr/sbin/nologin app \
    && mkdir -p /app/staticfiles /app/mediafiles \
    && chown -R app:app /app \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

# Development: docker-compose.yml bind-mounts the checkout over /app, whose files
# are owned by whoever cloned it, so this stage keeps running as root and works
# on a fresh clone regardless of host uid.
FROM base AS development

# Production (the default stage): runs as the unprivileged user.
FROM base AS production
USER app
