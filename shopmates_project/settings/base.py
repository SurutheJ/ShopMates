"""
Base settings shared by every environment.

Anything that differs between local development and production (DEBUG,
ALLOWED_HOSTS, security headers, static file storage) lives in dev.py or
prod.py. Secrets are read from environment variables, loaded from a local
.env file by python-dotenv. See .env.example.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# load_dotenv() never overrides a variable that is already set in the real
# environment, so a host's own variables win over .env.
load_dotenv(BASE_DIR / '.env')


def get_env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


def env_bool(name, default=False):
    return str(os.environ.get(name, default)).strip().lower() in ('1', 'true', 'yes')


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


SECRET_KEY = get_env('SECRET_KEY', required=True)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # required by django-allauth
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    # Shopmates apps
    'accounts',
    'deals',
    'ai',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'shopmates_project.middleware.ContentSecurityPolicyMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'shopmates_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.current_shop',
            ],
        },
    },
]

WSGI_APPLICATION = 'shopmates_project.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

# ---------------------------------------------------------------------------
# Cache. The rate limiter (deals/throttle.py) counts in this cache. The default
# local-memory cache is per process, so with several workers each would count
# separately and a restart would reset every count. The database cache is
# shared by all workers. Create its table once per database:
#     python manage.py createcachetable
# ---------------------------------------------------------------------------
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}

# ---------------------------------------------------------------------------
# Authentication (django-allauth)
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1
# Public address of the site, e.g. https://<user>.pythonanywhere.com . Used for QR links.
# Empty means: build links from the request's own host.
SITE_URL = get_env('SITE_URL', default='')

LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'home'

ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = 'none'   # no mail server yet
ACCOUNT_LOGOUT_ON_GET = False         # logging out needs a POST with CSRF
ACCOUNT_SESSION_REMEMBER = None

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------------------------------------------------------------------
# Google OAuth. Keys live in .env, never in the admin panel and never in git.
# Do NOT also add a Google "Social application" in /admin/: allauth would then
# find two Google apps and raise MultipleObjectsReturned.
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = get_env('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = get_env('GOOGLE_CLIENT_SECRET', default='')
GOOGLE_LOGIN_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
        **({
            'APP': {
                'client_id': GOOGLE_CLIENT_ID,
                'secret': GOOGLE_CLIENT_SECRET,
                'key': '',
            },
        } if GOOGLE_LOGIN_ENABLED else {}),
    },
}
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_AUTO_SIGNUP = True

# ---------------------------------------------------------------------------
# Shopmates business rules (see docs/PRODUCT.md)
# ---------------------------------------------------------------------------
SHOPS_AUTO_APPROVE = env_bool('SHOPS_AUTO_APPROVE', False)  # dev.py turns this on
DEAL_RESPONSE_DAYS = env_int('DEAL_RESPONSE_DAYS', 7)       # time to answer a proposal
DISCOUNT_MAX_PERCENT = env_int('DISCOUNT_MAX_PERCENT', 50)
REDEMPTION_CAP_MAX = env_int('REDEMPTION_CAP_MAX', 1000)
DEAL_MAX_DAYS = env_int('DEAL_MAX_DAYS', 365)
VOUCHER_TTL_HOURS = env_int('VOUCHER_TTL_HOURS', 24)
VOUCHER_ISSUE_LIMIT_PER_HOUR = env_int('VOUCHER_ISSUE_LIMIT_PER_HOUR', 10)  # per IP
REDEEM_LIMIT_PER_HOUR = env_int('REDEEM_LIMIT_PER_HOUR', 60)  # confirm attempts per user
STATS_MIN_GROUP = env_int('STATS_MIN_GROUP', 5)  # hide stats groups with fewer shops

# ---------------------------------------------------------------------------
# AI assistant (hosted LLM, called server-side only). Optional: with no key the
# app uses a rule-based fallback. Provider and model are unverified defaults.
# ---------------------------------------------------------------------------
AI_API_KEY = get_env('AI_API_KEY', default='')
AI_API_MODEL = get_env('AI_API_MODEL', default='gemini-3.1-flash-lite')
AI_API_BASE_URL = get_env('AI_API_BASE_URL', default='https://generativelanguage.googleapis.com/v1beta/openai/')
AI_TIMEOUT_SECONDS = env_int('AI_TIMEOUT_SECONDS', 15)
AI_DRAFT_LIMIT_PER_HOUR = env_int('AI_DRAFT_LIMIT_PER_HOUR', 10)  # per user

# Deal Radar: also list nearby shops from OpenStreetMap (one cached Overpass request).
# False means the radar page makes no outside call and shows ShopMates shops only.
RADAR_OSM_ENABLED = env_bool('RADAR_OSM_ENABLED', True)

# ---------------------------------------------------------------------------
# Logging. Console for the dev server and the host's log viewer, plus a rotating
# file so errors do not vanish. The 'ai' logger records why a feature used its
# fallback (the reason text only, never prompts, questions or shop data).
# ---------------------------------------------------------------------------
LOG_DIR = Path(get_env('LOG_DIR', default=str(BASE_DIR / 'logs')))
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '{asctime} {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(LOG_DIR / 'shopmates.log'),
            'maxBytes': 1_000_000,
            'backupCount': 3,
            'formatter': 'plain',
        },
    },
    'loggers': {
        'ai': {'handlers': ['console', 'file'], 'level': 'INFO', 'propagate': False},
        # Unhandled server errors (500s). Warnings such as 404s stay out of the file.
        'django': {'handlers': ['console', 'file'], 'level': 'ERROR'},
    },
}
