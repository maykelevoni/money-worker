# Money Worker — production image (stateless: DB on Neon, media on R2)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: ffmpeg for video rendering, then cleaned up.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build static files into the image (served by WhiteNoise).
# DEBUG=False so the production (hashed/compressed) static backend is used.
RUN DEBUG=False SECRET_KEY=build-only python manage.py collectstatic --noinput

# Run as a non-root user.
RUN chmod +x entrypoint.sh \
    && useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Migrates the DB, then starts gunicorn. Coolify/Caddy puts HTTPS in front of it.
CMD ["./entrypoint.sh"]
