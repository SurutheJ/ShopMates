# Development guide

Every command below was run on macOS with Python 3.14 during the first build. The target host uses Python 3.13; re-check there.

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
.venv/bin/python manage.py seed_demo
```

## Run

```bash
.venv/bin/python manage.py runserver
```

Open http://localhost:8000/. `seed_demo` creates six shops, owners named `demo_cafe`, `demo_books`, `demo_bakery`, `demo_flowers`, `demo_fit`, `demo_coffee2`, and a staff user `demo_staff` (works at the bookstore). They share a development-only password, the `DEMO_PASSWORD` constant in `deals/management/commands/seed_demo.py`. The command refuses to run unless `DEBUG` is on.

The demo data includes: an active cafe and bookstore deal with four redemptions, a proposal from the bakery waiting on the cafe, and an unsent draft from the flower shop.

## Test

```bash
.venv/bin/python manage.py test
```

Covers the negotiation rules, redemption rules (double use, caps, expiry, wrong shop), cross-shop access, the APIs and exports, the AI service with a fake client, and shop setup. Run `manage.py makemigrations --check` before committing to confirm the migrations match the models.

## Useful commands

| Command | What it does |
|---|---|
| `manage.py seed_demo` | Demo shops, users and deals (DEBUG only) |
| `manage.py update_deal_statuses` | Applies time-based transitions to all open deals |
| `manage.py createsuperuser` | An admin for `/admin/` (approve shops there when `SHOPS_AUTO_APPROVE` is off) |

## Project layout

```
shopmates_project/   settings/{base,dev,prod}.py, urls.py
accounts/            User, Shop, ShopMembership, access.py (decorators), discover and shop setup
deals/               models, services.py (the rules), forms, views, api.py, stats.py, throttle.py
ai/                  client.py (only file that calls the LLM), prompts.py, services.py
templates/           base.html, partials/, account/ (login, signup, logout), accounts/, deals/
static/css/base.css  the stylesheet
```

## Switches in `.env`

| Variable | Default | Meaning |
|---|---|---|
| `SHOPS_AUTO_APPROVE` | on in dev, off in prod | New shops approved automatically |
| `STATS_MIN_GROUP` | 5 | Public stats hide a category with fewer shops |
| `DEAL_RESPONSE_DAYS` | 7 | Time to answer a proposal before it expires |
| `DISCOUNT_MAX_PERCENT` | 50 | Largest allowed discount |
| `VOUCHER_TTL_HOURS` | 24 | How long a customer code stays valid |
| `LLM_API_KEY`, `LLM_MODEL` | empty | AI drafting; empty uses the rule-based fallback |

## Known limits

- **QR codes use the address the page was opened on.** On a laptop at `localhost` the QR points to `localhost`, which a phone can't reach. To test with a phone, run `runserver 0.0.0.0:8000`, open the app by your computer's LAN address, and add that address to `ALLOWED_HOSTS`.
- **Rate limits use the local-memory cache**, which is per process and resets on restart. Fine for one small server.
- **Behind a proxy**, `REMOTE_ADDR` is the proxy's address, so the per-IP voucher limit becomes a shared limit. Revisit if it matters.
- **One shop per user.** Multi-location is a later phase.
