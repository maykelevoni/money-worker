# Money Worker — production image (stateless: DB on Neon, media on R2)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Build static files into the image (served by WhiteNoise).
# DEBUG=False so the production (hashed/compressed) static backend is used.
# SECRET_KEY/ALLOWED_HOSTS are throwaway build-time values just to satisfy the
# prod config guard — collectstatic serves no requests, so they're never used.
RUN DEBUG=False SECRET_KEY=build-only ALLOWED_HOSTS=localhost python manage.py collectstatic --noinput

# Run as a non-root user. Pre-create the mount points (media, static-site
# builds) so a bind/named volume mounted there inherits appuser ownership and
# stays writable.
RUN chmod +x entrypoint.sh \
    && mkdir -p /app/media /app/builds \
    && useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Migrates the DB, then starts gunicorn. Coolify/Caddy puts HTTPS in front of it.
CMD ["./entrypoint.sh"]
