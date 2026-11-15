"""Local development settings (the default; see manage.py)."""

import os

from .base import *  # noqa: F401,F403
from .base import env_bool

DEBUG = True

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

# Make demos painless: new shops are approved automatically in development.
SHOPS_AUTO_APPROVE = env_bool('SHOPS_AUTO_APPROVE', True)
