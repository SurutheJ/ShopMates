# Development guide

The commands below were run on macOS with Python 3.14. The GitHub Actions workflow uses Python 3.12. The host's Python version still needs checking.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set `SECRET_KEY` to a value you generate yourself:

```bash
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Then create the database and (optionally) load demo data:

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py seed_showcase
```

## Run

```bash
.venv/bin/python manage.py runserver
```

Open http://localhost:8000/. `seed_showcase` wipes the development database and creates eight shops, owners named `demo_cafe`, `demo_books`, `demo_bakery`, `demo_flowers`, `demo_fit`, `demo_coffee2`, `demo_salon`, `demo_resto`, and a staff user `demo_staff` (works at the bookstore). They share the development-only password `shopmates-demo-1`. The command refuses to run unless `DEBUG` is on. A smaller set is available with `seed_demo`.

The demo data includes an active cafe and bookstore deal with two weeks of redemptions, a proposal from the bakery waiting on the cafe, and an unsent draft from the flower shop.

## Test

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

516 tests passed on 16 Nov. For pages there are two browser checks (they need Playwright: `pip install playwright && playwright install chromium`). Run them against a running copy of the app on its own port with a scratch copy of the database, not your real data:

```bash
python designv2/check_layout.py http://127.0.0.1:8002 demo_cafe shopmates-demo-1 /inbox/ /discover/   # the page itself must not scroll
python scripts/check_targets.py http://127.0.0.1:8002 demo_cafe shopmates-demo-1 /inbox/ /redeem/       # tap targets 44px, text 16px
```

`check_targets.py` signs in through the login page's Log in button (`button[form=login-form]`). The Google button comes first on that page, so a script that clicks the first submit button would click Google instead.

Covers the negotiation rules, redemption rules (double use, caps, expiry, wrong shop), cross-shop access, the APIs and exports, the AI service with a fake client, and shop setup. Run `manage.py makemigrations --check` before committing to confirm the migrations match the models.

## Useful commands

| Command | What it does |
|---|---|
| `manage.py seed_showcase` | Full demo neighborhood; resets the database (DEBUG only) |
| `manage.py seed_demo` | Smaller demo set (DEBUG only) |
| `manage.py evaluate_ai` | AI evaluation report (add `--live` with a key to include a live call) |
| `manage.py backup_db` | Dated copy of the SQLite database into `backups/` |
| `manage.py update_deal_statuses` | Applies time-based transitions to all open deals |
| `manage.py createsuperuser` | An admin for `/admin/` (approve shops there when `SHOPS_AUTO_APPROVE` is off) |

## Project layout

```
shopmates_project/   settings/{base,dev,prod}.py, urls.py
accounts/            User, Shop, ShopMembership, access.py (decorators), discover and shop setup
deals/               models, services.py (the rules), forms, views, api.py, stats.py, throttle.py
ai/                  client.py (only file that calls the model), prompts.py, services.py, radar.py, matching.py
templates/           base.html, partials/, account/ (login, signup, logout), accounts/, deals/
static/              css, js, img, vendor/leaflet
designv2/            design mockups
scripts/             check_targets.py (tap targets), load_test.py
```

## Switches in `.env`

| Variable | Default | Meaning |
|---|---|---|
| `SHOPS_AUTO_APPROVE` | on in dev, off in prod | New shops approved automatically |
| `STATS_MIN_GROUP` | 5 | Public stats hide a category with fewer shops |
| `DEAL_RESPONSE_DAYS` | 7 | Time to answer a proposal before it expires |
| `DISCOUNT_MAX_PERCENT` | 50 | Largest allowed discount |
| `VOUCHER_TTL_HOURS` | 24 | How long a customer code stays valid |
| `AI_API_KEY`, `AI_API_MODEL`, `AI_API_BASE_URL` | empty, `gemini-3.1-flash-lite`, Google's `v1beta/openai/` address | Live model; empty uses the built-in fallback |
| `RADAR_OSM_ENABLED` | on | Radar looks up nearby places on OpenStreetMap; off shows ShopMates shops only |

## Known limits

- **QR codes use the address the page was opened on.** On a laptop at `localhost` the QR points to `localhost`, which a phone can't reach. To test with a phone, run `runserver 0.0.0.0:8000`, open the app by your computer's LAN address, and add that address to `ALLOWED_HOSTS`.
- **Rate limits use the local-memory cache**, which is per process and resets on restart. Fine for one small server.
- **Behind a proxy**, `REMOTE_ADDR` is the proxy's address, so the per-IP voucher limit becomes a shared limit. Revisit if it matters.
- **One shop per user.** Multi-location is a later phase.
