import logging

from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger('django.request')


def healthz(request):
    """For an uptime monitor: 200 if the database answers, 503 if not. Never says why."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        logger.exception('healthz: database check failed')
        return JsonResponse({'status': 'error'}, status=503)
    return JsonResponse({'status': 'ok'})
