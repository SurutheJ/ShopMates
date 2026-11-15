# Shopmates

**Neighboring shops promote each other.**

Shopmates is a Django web app that helps independent shops near each other turn informal cross-promotions into agreed, trackable deals.

A shop proposes a deal to a neighbor, for example "10% off a coffee with a bookstore receipt". The neighbor accepts, counters or declines. Once the deal is active, customers redeem it with a QR code that staff confirm on a phone. Both shops see how many customers each one sent the other, and the app suggests a fair renewal when the exchange is lopsided.

> **Status: working MVP, not deployed.** The core app is built and covered by 94 automated tests: shops and approval, discovery, negotiation, QR vouchers, staff redemption, summary and exports, APIs, and AI drafting with a fallback. It has been run locally in a browser. It has **not** been deployed, and Google sign-in, the live LLM call and phone QR scanning have **not** been tested yet. See [docs/DECISIONS.md](docs/DECISIONS.md) for the list.

## Why this exists

Small shops share foot traffic with the shops next door but have no ad budget. Neighbors already cooperate informally (a flyer at the counter, "show their receipt, get a discount"), and these arrangements break down because:

1. There is no shared record of the agreed terms.
2. Redemptions can't be verified without trusting the other shop's count.
3. Nobody can tell whether the deal is fair, so resentful deals quietly lapse.

Shopmates makes the agreement explicit, the redemptions verifiable, and the fairness visible.

## Who uses it

| User | What they do | Account |
|---|---|---|
| Shop owner | Sets up the shop, proposes and negotiates deals, reads results | Google sign-in |
| Staff member | Confirms redemptions on a phone, nothing else | Invited by an owner |
| Customer | Opens a QR link and shows a one-time code | None |
| Admin | Approves new shops, moderates | Django admin |

## Core flow

```
draft -> proposed -> accepted -> active -> completed
            |  ^
            v  |
         countered          (any open deal can end as declined or expired)
```

The home screen for an owner is an **inbox of actions waiting on them** (proposals to answer, counters, deals ending soon), not a dashboard. Charts exist, but as a secondary view.

## Features

**Built (MVP)**
- Google sign-in, shop profile, admin approval of new shops
- Discover shops by category and name, nearest first when both shops have coordinates entered
- Deal proposals with offer text, dates, a redemption cap and terms
- Negotiation: accept, counter-offer (new version of the terms) or decline, with history
- QR vouchers and a staff redeem page with cap, date and duplicate checks
- Deal summary: customers sent vs received, fairness view, renewal suggestion, CSV and JSON export
- Public API of anonymized aggregate statistics, protected APIs for each shop's private data
- AI assistant: drafts proposal wording, suggests balanced counters, explains fairness in plain English

**Not built yet**
- Automatic address lookup (geocoding), email notifications, multi-location shops, bundled "passport" deals

**Deliberately out of scope**
- Payments, customer accounts, automatic shop matching

## Tech stack

- Django (monolith), SQLite for the prototype
- django-allauth with Google OAuth
- A hosted LLM API called only from server-side Django code (Gemini request shape written but unverified; no key means a rule-based fallback)
- Hosting: PythonAnywhere free tier (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md))

## Documentation

| File | What's in it |
|---|---|
| [docs/DECISIONS.md](docs/DECISIONS.md) | Decisions made, open decisions, risks, unverified claims |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Users, screens, deal lifecycle, rules, phases |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Monolith layout, data model draft, APIs, security |
| [docs/AI.md](docs/AI.md) | How the LLM is used, guardrails, validation, fallback |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Setup, run, test, demo data, project layout, known limits |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Settings split, `.env`, PythonAnywhere, Google OAuth |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Assignment deliverables checklist (to fill in) |
| [docs/BRANCHING.md](docs/BRANCHING.md) | Git workflow and commit rules |
| [CLAUDE.md](CLAUDE.md) | Instructions for AI coding sessions working in this repo |

## Team

Suruthe Jayachandran, Sahithi Madabhushi. All team members are considered equal contributors.
Team name and number: **TODO**.

## Getting started

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then set SECRET_KEY in .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
.venv/bin/python manage.py test
```

Full details, demo accounts and known limits are in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

Never commit `.env`. Copy `.env.example` to `.env` and fill in your own values.
