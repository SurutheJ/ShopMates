# Deployment and environment

Notes from an earlier Django project deployed on PythonAnywhere with Google OAuth. Each item was a real problem there. ShopMates has not been deployed yet, so re-check each one.

## Settings

Split settings into `base.py`, `dev.py`, `prod.py`. `manage.py` defaults to dev. Production is selected in the host's WSGI file.

Production must:
- Set `DEBUG = False` and require `ALLOWED_HOSTS` from the environment (fail loudly if missing)
- Set secure cookies, `SECURE_SSL_REDIRECT`, and `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` when behind PythonAnywhere's proxy
- Use hashed static files through the `STORAGES` setting:

```python
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"},
}
```

The old `STATICFILES_STORAGE` name is silently ignored on newer Django. Run `collectstatic` **with prod settings** or every page fails with "Missing staticfiles manifest entry".

## Environment variables

See `.env.example`. Never commit `.env`.

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django signing key; different on every machine |
| `DEBUG` | `True` locally only |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth; leave empty to hide the button |
| `AI_API_KEY`, `AI_API_MODEL`, `AI_API_BASE_URL` | LLM provider key, model and OpenAI-style base URL (defaults: `gemini-3.1-flash-lite`, Google's `v1beta/openai/`) |

## Google sign-in (django-allauth)

- Install `django-allauth[socialaccount]`, not plain `django-allauth`. Without the extra, PyJWT is missing on a clean install and the callback fails.
- Keep the client ID and secret in `.env` and register the app in settings. Do not also add a Google "Social application" in the admin panel; allauth will find two apps and error.
- In Google Cloud Console, create a "Web application" OAuth client and add **both** redirect URIs, exactly, with the trailing slash:
  - `http://localhost:8000/accounts/google/login/callback/`
  - `https://<username>.pythonanywhere.com/accounts/google/login/callback/`
- Use `localhost`, not `127.0.0.1`, when testing.
- While the consent screen is in Testing mode, only listed test users can sign in. Add teammates and testers.
- The button should be a POST form with a CSRF token.

## PythonAnywhere free tier

- **Disk quota 512 MB.** Large packages fill it. Delete pip's cache (`rm -rf ~/.cache/pip`) and install with `--no-cache-dir`. Keep heavy ML packages out of this project entirely.
- **100 CPU-seconds per day.** Don't run heavy work on request. Precompute or avoid it.
- **Outbound requests are restricted to an allowlist.** Verify the LLM host and geocoding host are reachable *from the deployed site* before depending on them.
- **Set the virtualenv path** on the Web tab (`/home/<user>/.virtualenvs/<env>`). Without it the site runs on the system Python and fails on missing packages.
- Static files mapping: URL `/static/` to `<project>/staticfiles`.
- The WSGI file must set `DJANGO_SETTINGS_MODULE` to the prod settings and add the project to `sys.path`.
- `db.sqlite3` is gitignored. Back it up before any `git pull` on the server.
- Python version: use 3.13, or 3.11 at minimum.
- Each team member who must deploy needs their own PythonAnywhere account and site.

## WSGI file on PythonAnywhere

```python
import os, sys
path = '/home/<username>/shopmates'
if path not in sys.path:
    sys.path.append(path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'shopmates_project.settings.prod'
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

QR codes and voucher links are built from the address the page is opened on. In production behind PythonAnywhere's proxy they come out as `https://<username>.pythonanywhere.com/...` because of `SECURE_PROXY_SSL_HEADER`. Check this after the first deploy by opening a deal page and reading the URL under the QR code.

## Deploy checklist

1. `git pull`, `pip install -r requirements.txt`
2. Update the server `.env` (secret key, allowed hosts, Google keys, LLM key)
3. `python manage.py migrate`
4. `DJANGO_SETTINGS_MODULE=<project>.settings.prod python manage.py collectstatic --noinput`
5. Reload the web app from the Web tab
6. Test: home page, login, Google login, a public API, a protected API (expect 401 when logged out), a redemption end to end
7. Read the Error log if anything fails

## Hosting alternatives

If PythonAnywhere's limits block a needed outbound call, consider another free host. That changes this file; update it.
