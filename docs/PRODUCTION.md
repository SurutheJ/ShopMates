# Deployment, cost, scale and security

**Status: not deployed.** The app runs locally. This is the plan plus what we measured on a laptop. Prices are rough planning numbers, not quotes; check current pricing before relying on them.

## Deployment plan

Target is PythonAnywhere's free tier (steps and settings in [DEPLOYMENT.md](DEPLOYMENT.md)). Render or Railway are the fallback. Before relying on the host we need to confirm: the Gemini host is reachable (free PythonAnywhere uses an outbound allowlist), OpenStreetMap hosts are too, `collectstatic` works with prod settings, QR links use the public host name, and Google sign-in works with the host's redirect URI.

## Resources

| Resource | Need | Why |
|---|---|---|
| CPU | Under one shared vCPU | Plain Django views and SQLite queries. Retrieval takes microseconds. The model runs elsewhere |
| GPU | None | No local model |
| RAM | About 256 MB | Django and an in-memory TF-IDF index of 14 passages |
| Storage | Under 100 MB plus about 4 MB of images and Leaflet | Code, dependencies, SQLite file. No uploads |
| Database | SQLite for the demo, PostgreSQL for real use | SQLite allows one writer at a time |
| AI inference | Hosted API | One short call per click |

## Cost comparison

| Factor | Hosted API (what we use) | Self-hosted small model |
|---|---|---|
| Hardware | None | A GPU or a large-RAM machine; does not fit a free host |
| Monthly cost | Free tier for a demo; cents to a few dollars at small scale (about a thousand tokens a call) | Tens to hundreds of dollars for an always-on GPU or large VM (estimate) |
| Latency | Network plus about a second (measured 1.1 s median locally) | Low on a good GPU, slow on CPU |
| Maintenance | Watch quota and model deprecations | Updates, drivers, scaling |
| Scalability | Provider scales; rate limits apply (we hit HTTP 429 on the free tier) | We add machines |
| Privacy | Shop name, hours and spend leave our server; no customer data exists | Data stays with us |

The data is business information, not personal, so the hosted API wins. We would revisit if shops uploaded sensitive data.

## Scaling to 10,000 daily active users

Assumptions: users are owners and staff, 10 page views each, one AI call per user per day; voucher pages are the busiest public traffic.

1. **Infrastructure:** a small managed host with 2 to 4 workers, PostgreSQL, Redis for shared cache, WhiteNoise or a CDN for static files.
2. **First bottleneck:** SQLite's single writer, hit by many staff confirming redemptions at lunch. After that, synchronous model calls holding workers for seconds.
3. **AI cost:** about 10,000 calls a day, a few dollars a day at small-model pricing (estimate). It grows linearly with calls; the fallback and caching cap it.
4. **Performance:** move to PostgreSQL, cache the public stats, run AI calls in a background worker with polling. Most foreign keys are indexed already.
5. **Architecture:** shared rate-limit store, task queue for AI calls, a scheduled `update_deal_statuses` (today statuses update when a page is read), email notifications, error tracking.

## Security and reliability

| Topic | Status |
|---|---|
| Environment variables | `.env` is gitignored; `SECRET_KEY` is required at startup; `.env.example` has no secrets |
| Input validation | One form class validates typed and AI-suggested terms |
| Authentication and permissions | Owner, staff and customer roles. A shop that is not a party to a deal gets 404; staff get 403. APIs return 401 JSON when logged out |
| API key protection | Server side only, never in a template or response |
| Error handling | AI failures fall back with a visible reason. 404, 403 and 500 pages show a sentence and no traceback |
| Rate limiting | Per-user AI drafts and redeem attempts, per-IP voucher start, through the database cache (run `createcachetable`). Known gap: the counter reads then writes, so two simultaneous requests can count as one |
| Logging | Console and a rotating file (`logs/shopmates.log`, 1 MB, 3 files). AI fallback reasons are logged, never prompts, questions or shop names. No alerting yet |
| Health check | `/healthz/` returns 200 or 503 without detail |
| Backups | `python manage.py backup_db` makes a dated copy of the database. Restoring from one has not been tried |
| User privacy | No customer data. A redemption is a code, a time, a shop and a staff user |
| AI risks | Prompt injection is limited (data framing, validation, escaping) but not eliminated. A human reviews every draft |
| Transport | Prod settings use secure cookies and SSL redirect; HSTS is 3600 s so a mistake is cheap to undo |
| Browser headers | Enforced Content-Security-Policy (scripts from this site only; styles allow inline for the 500 page), referrer policy |
| Dependencies | `pip-audit` on 16 Nov 2026 found no known vulnerabilities in the five pinned packages. Their own dependencies are not pinned |

## Notes for the host

Setup order: `migrate`, `createcachetable` (the rate limit lives in a table and pages with a limit return 500 without it), `collectstatic` with prod settings (prod uses a static manifest, so run it again after every CSS or JS change), then `check --deploy`. Expect warnings W005 and W021; we left HSTS subdomains and preload off on purpose.

Variables added during development, all in `.env.example`: `SITE_URL` (public address for QR links), `LOG_DIR`, `REDEEM_LIMIT_PER_HOUR` (default 60), `SECURE_HSTS_SECONDS`.

Things we found while testing locally:

- **CSP and Google sign-in.** The first policy had `form-action 'self'`, which silently blocked the Google button because the site redirects to `accounts.google.com`. It now allows that one host, and a test (`shopmates_project/test_security.py`) keeps it. If a host page is blank, look for "Refused to" in the browser console.
- **Time zone.** One zone, `America/Chicago` with `USE_TZ`. Exports, the redemptions API and `generated_at` print Chicago time with its offset. Not checked on PythonAnywhere, whose clock is probably UTC.
- **No scheduler.** Nothing depends on one. Expired proposals are skipped by the inbox badge and statuses update when a page is read.
- **AI settings.** Variables are `AI_API_KEY`, `AI_API_MODEL`, `AI_API_BASE_URL`. A `.env` that still uses the old `LLM_*` names runs on the fallback without a warning.
- **Google sign-in** works locally on `http://localhost:8000`. On the host we may also need `ACCOUNT_DEFAULT_HTTP_PROTOCOL = 'https'` and `CSRF_TRUSTED_ORIGINS`; not tested. If Google answers `redirect_uri_mismatch`, look there first.

To check on the host: whether the voucher start limit sees the proxy's address instead of the customer's, and whether the outbound allowlist lets the app reach Gemini and OpenStreetMap.
