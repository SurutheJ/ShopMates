# ShopMates

Neighboring shops promote each other.

ShopMates is a Django web app for independent shops that want to cross-promote with the shop next door. One shop proposes a deal ("10% off a coffee with a bookstore receipt"), the neighbor accepts, counters or declines, and once it is active customers redeem it with a QR code that staff confirm on a phone. Both shops can see how many customers each one sent the other, and the app points out when a deal is lopsided.

Team 22: Suruthe Jayachandran and Sahithi Madabhushi, equal contributors on the whole project.

## What's built

**Product and user experience**
- Shop setup, an inbox of waiting actions, Discover, a four-step proposal form, deal pages with history and chat
- Owner and staff roles with a navigation that changes to match
- Clear feedback on every form, plus a QR card shops can download as PNG, SVG or PDF

**Django application**
- Models for shops, memberships, deals, deal versions, messages, events, vouchers and redemptions, with migrations
- Negotiation: accept, counter or decline, with a version history
- Redemption by QR code and staff confirmation, with cap, date and duplicate checks
- Google sign-in, login and logout, protected pages and per-shop access checks
- Search and filters on Discover, a deal summary with charts, CSV and JSON export, a public stats API and two private APIs

**AI**
- Partner match score and Deal Radar (a map of nearby shops, ranked)
- Fairness calculator on the proposal form
- AI deal draft, deal coach and playbook Q&A, each checked in Python and each with a built-in fallback

**Evaluation and testing**
- 516 automated tests and a GitHub Actions workflow
- `evaluate_ai` report with retrieval and guardrail results, failure analysis and measured improvements
- Query counts and a load test

**Production readiness**
- Separate dev and prod settings, secrets in `.env`, rate limits, a security policy for browsers, logging, a health check and a database backup command
- Cost comparison and scaling notes in `docs/PRODUCTION.md`

**Documentation**
- This README, `README_AI.md` and the files in `docs/`

Still to come: hosting, a negotiation copilot, a terms checker and notifications. See [docs/ROADMAP.md](docs/ROADMAP.md).

## Why it is different

QR cross-promotion tools exist. ShopMates focuses on the agreement between two shops:

1. Negotiated terms with caps, dates and an audit trail, not a one-way coupon.
2. A redemption can only be confirmed once. This is enforced by a database constraint, not just the page.
3. Fairness is measured in dollars. Equal customer counts can still be unfair when one shop's average sale is $24 and the other's is $6.
4. Every number shown comes from Python. The language model only words things, and its output is checked.

## Install and run

You need Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then set SECRET_KEY (see below)
python manage.py migrate
python manage.py createcachetable
python manage.py seed_showcase    # demo shops, deals and redemptions (resets the dev database)
python manage.py runserver        # http://localhost:8000
```

Generate a secret key for `.env`:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Use `localhost`, not `127.0.0.1`, especially for Google sign-in.

Demo logins (password `shopmates-demo-1`): `demo_cafe` (owner), `demo_books`, `demo_bakery`, `demo_flowers`, `demo_fit`, `demo_coffee2`, `demo_salon`, `demo_resto`, and `demo_staff` (staff at the bookstore).

## Environment variables

Set these in `.env`. Never commit it. `.env.example` lists them all.

| Variable | What it does |
|---|---|
| `SECRET_KEY` | Django signing key. Required. |
| `DEBUG` | `True` for local work only. |
| `ALLOWED_HOSTS` | Comma-separated host names. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google sign-in. Leave empty to hide the button. |
| `AI_API_KEY` | Gemini key. Leave empty and every AI feature uses its built-in fallback. |
| `AI_API_MODEL`, `AI_API_BASE_URL` | Model and endpoint. Defaults are in `.env.example`. |
| `RADAR_OSM_ENABLED` | `False` stops Deal Radar from looking up nearby places on OpenStreetMap. |

## Using the AI features

Sign in as `demo_cafe` after seeding.

| Feature | Where |
|---|---|
| Partner match score | Discover |
| Deal Radar (map of nearby shops, ranked) | Radar |
| Fairness calculator | Propose a deal, step 4 ("Is it balanced?") |
| Draft with AI | Propose a deal |
| Explain this deal (coach) | Deal page, summary |
| Playbook Q&A | Playbook |

Without `AI_API_KEY` these still work and say they are using the built-in version. Details: [README_AI.md](README_AI.md).

## Tests

```bash
python manage.py check
python manage.py test
python manage.py evaluate_ai     # reproduces the numbers in docs/EVALUATION.md
```

## Project layout

```
shopmates_project/   settings (base, dev, prod), urls
accounts/            users, shops, staff, discover, radar page
deals/               deals, versions, vouchers, redemptions, fairness, APIs, exports
ai/                  client.py (the only code that calls the model), prompts, services, radar, matching
templates/, static/  pages and styles
designv2/            design mockups the UI was built from
scripts/             layout and tap-target checks, load test
docs/                product, architecture, evaluation, deployment
```

## Docs

| File | Contents |
|---|---|
| [docs/UPDATED_PRODUCT_SCOPE.md](docs/UPDATED_PRODUCT_SCOPE.md) | Product scope update since the proposal |
| [README_AI.md](README_AI.md) | AI models, workflow, limits |
| [docs/INITIAL_AI_IMPLEMENTATION.md](docs/INITIAL_AI_IMPLEMENTATION.md) | What the AI work covers so far |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Status and remaining tasks to Dec 8 |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | First-draft checklist with evidence |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Users, screens, deal lifecycle, rules |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Data model, APIs, security |
| [docs/EVALUATION.md](docs/EVALUATION.md) | Tests, failures, improvements |
| [docs/PRODUCTION.md](docs/PRODUCTION.md) | Resources, cost, scaling, security |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Settings and PythonAnywhere steps |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Setup details and known limits |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decisions, open questions, unverified items |
| [docs/STAGE3-REPORT.md](docs/STAGE3-REPORT.md), [docs/STAGE4-REPORT.md](docs/STAGE4-REPORT.md) | Restyle reports: files changed and results per stage |
| [docs/BRANCHING.md](docs/BRANCHING.md) | Git workflow |
