"""Lightweight per-IP rate limiting for public / auth endpoints.

Uses Django's cache framework — no extra dependency. With the default in-memory
cache this is per-process (fine for dev / a single worker); in production point
CACHES at a shared backend (Redis/Memcached) so the limit holds across workers.
Throttling must never break a request, so any cache error fails open.
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def too_many(request, bucket, limit, window_seconds):
    """True if this IP has exceeded `limit` hits for `bucket` in the window."""
    key = f"throttle:{bucket}:{_client_ip(request)}"
    try:
        # cache.add is atomic-ish: it only sets when the key is absent, so the
        # first hit starts the window; later hits increment without resetting TTL.
        if cache.add(key, 1, window_seconds):
            return False
        try:
            count = cache.incr(key)
        except ValueError:  # key expired between add() and incr()
            cache.add(key, 1, window_seconds)
            return False
        return count > limit
    except Exception:
        return False  # fail open — never let throttling take down the endpoint


def rate_limit(bucket, limit, window_seconds, methods=("POST",)):
    """Decorator: return 429 when an IP exceeds `limit` `methods` requests/window."""
    def deco(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            if request.method in methods and too_many(request, bucket, limit, window_seconds):
                return HttpResponse(
                    "Too many requests. Please wait a moment and try again.",
                    status=429,
                )
            return view(request, *args, **kwargs)
        return _wrapped
    return deco
