from django.conf import settings


def absolute_url(request, path):
    """A full link for QR codes and API replies.

    Uses settings.SITE_URL when it is set. Without it Django builds the link
    from the request's Host header, which is wrong behind some proxies.
    """
    if settings.SITE_URL:
        return settings.SITE_URL.rstrip('/') + path
    return request.build_absolute_uri(path)
