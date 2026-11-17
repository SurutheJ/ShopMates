"""
Production settings.

Select with DJANGO_SETTINGS_MODULE=shopmates_project.settings.prod (set in the
host's WSGI file, not in .env). ALLOWED_HOSTS and SECRET_KEY must come from the
environment.
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

# No default on purpose: a deploy with no ALLOWED_HOSTS should fail loudly.
_allowed_hosts = os.environ.get('ALLOWED_HOSTS', '')
ALLOWED_HOSTS = [h.strip() for h in _allowed_hosts.split(',') if h.strip()]
if not ALLOWED_HOSTS:
    raise RuntimeError(
        "ALLOWED_HOSTS must be set via the environment when running with "
        "settings.prod (e.g. ALLOWED_HOSTS=<username>.pythonanywhere.com)."
    )

# PythonAnywhere terminates HTTPS at its proxy and passes X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Google only accepts https:// redirect URIs for a real domain.
ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
# HSTS tells browsers to use https only. Start at one hour: a wrong setting is
# remembered by every browser that saw it for this long. Raise it once the live
# site has worked over https for a while. No preload, no subdomains.
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Content-hashed static filenames (cache busting). Uses STORAGES, not the legacy
# STATICFILES_STORAGE name, which newer Django ignores. Run collectstatic with
# these prod settings or pages fail with "Missing staticfiles manifest entry".
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage',
    },
}
