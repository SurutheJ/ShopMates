from django.core.cache import cache


def allow(key, limit, window_seconds=3600):
    """
    Simple fixed-window rate limit using the cache. Returns True if this call
    is within `limit` calls per window. The cache is the database cache
    (settings.CACHES), so every worker shares one count. Limit: the database
    cache's incr is read-then-write, so two requests at the same instant can
    count as one. Fine for abuse limits, not for exact billing.
    """
    cache.add(key, 0, window_seconds)
    try:
        count = cache.incr(key)
    except ValueError:  # key expired between add and incr
        cache.set(key, 1, window_seconds)
        count = 1
    return count <= limit
