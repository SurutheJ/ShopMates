from django.core.cache import cache


def allow(key, limit, window_seconds=3600):
    """
    Simple fixed-window rate limit using the cache. Returns True if this call
    is within `limit` calls per window. Per-process on the default local-memory
    cache, which is enough to stop a casual loop on a single small server.
    """
    cache.add(key, 0, window_seconds)
    try:
        count = cache.incr(key)
    except ValueError:  # key expired between add and incr
        cache.set(key, 1, window_seconds)
        count = 1
    return count <= limit
