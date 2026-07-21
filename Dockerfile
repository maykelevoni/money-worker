# Money Worker — production image (stateless: DB on Neon, media on R2)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# TikTok video search (Research) drives a headless Chromium via TikTokApi.
# Install the browser + its OS libraries into a shared path (set above) so the
# non-root appuser can launch it at runtime. Adds ~450MB to the image.
RUN python -m playwright install --with-deps chromium \
    && chmod -R a+rx /ms-playwright

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
