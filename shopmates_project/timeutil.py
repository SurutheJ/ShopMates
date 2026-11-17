from django.utils import timezone


def local_iso(moment):
    """ISO 8601 text in the project's TIME_ZONE with its offset, so exports and the API match what the pages show."""
    return timezone.localtime(moment).isoformat()
