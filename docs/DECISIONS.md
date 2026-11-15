# Decisions, open questions, and risks

This is the project's memory. A new collaborator (or a new AI chat) should read this first. Keep it current: when a decision changes, edit it here and note the date.

## Decided

| # | Decision | Why |
|---|---|---|
| 1 | Idea: Shopmates, a deal desk for neighboring shops | Reachable pilot users (shops near campus), no sensitive data, runs on free hosting, real two-sided workflow |
| 2 | One Django monolith with a hosted LLM API | Free hosting can't run a local model or multiple services |
| 3 | Apps: `accounts`, `deals`, `ai` | Clear boundaries; only `ai/client.py` talks to the LLM |
| 4 | LLM drafts text and explains numbers; it never calculates | Keeps results trustworthy and testable |
| 5 | A human approves anything before it is sent to another shop | Avoids sending bad AI output to a real business |
| 6 | Main owner screen is an action inbox, not a dashboard | The value is people acting on each other's requests |
| 7 | No payments, no customer accounts, no automatic matching | Scope and risk |
| 8 | Secrets live in `.env`, never in git, chat, or the admin panel | Security, and Google keys must be env-based |
| 9 | Never commit to `main`; feature branches and reviewed PRs | Team convention |

## Implemented choices (made while building; change them if you disagree)

| # | Choice | Note |
|---|---|---|
| I1 | One set of terms applies both ways; each shop has its own redemption cap | Simplest fair model. Separate terms per direction would be a bigger change |
| I2 | A shop's QR code gives customers a voucher for the partner shop. A redemption at shop B counts as "A sent a customer" | Each deal has two secret UUID tokens |
| I3 | Counter-offers always create a new version and flip whose turn it is; there is no separate "re-propose" state | Statuses: draft, proposed, countered, accepted, active, completed, declined, expired, withdrawn |
| I4 | Time-based transitions run lazily when a deal is read or redeemed, plus a management command | No background scheduler |
| I5 | One shop per user; staff are added by an owner using the username or email of an existing account | Multi-location and email invites are later |
| I6 | New shops are auto-approved in development, admin-approved in production | Setting `SHOPS_AUTO_APPROVE` |
| I7 | A pair of shops can have only one live deal at a time | Avoids ambiguous QR codes and double counting |
| I8 | Estimated discount cost = redemptions honored x discount x the shop's typical spend; "lopsided" means at least 4 redemptions and a gap of 40% or more | Thresholds are guesses and should be tuned with real data |
| I9 | The AI fallback is a fixed rule-based draft (10%, cap 50, 30 days) | Shown with the reason the AI was not used |
| I10 | Shops enter latitude and longitude by hand; no geocoding API yet | Reachability of a free service from the host is unverified |

## Proposed, needs confirmation

| # | Proposal | Alternative |
|---|---|---|
| P1 | Customer opens the QR link and gets a one-time code valid 24 hours; staff confirm it | Self-confirm by customer (easier to cheat) |
| P2 | A counter-offer is a new version of the terms; one open version at a time | Free-form editing of one record |
| P3 | Fairness = customers sent vs received + estimated discount cost from each shop's typical order value | Counts only |
| P4 | In-app inbox first, email later | Email from day one |
| P5 | Public stats API hides any group with fewer than 5 shops | No minimum (risks identifying shops) |

## Open (answer before building the affected part)

1. **Shop signup:** admin-approved (recommended) or open?
2. **Redemption proof:** staff confirm only (recommended) or customers can also self-confirm?
3. **Pilot area:** which street or neighborhood?
4. **LLM provider:** Gemini was assumed. Free-tier limits not checked.
5. **Team name and team number.**
6. **Assignment deliverables list** for this project (see [REQUIREMENTS.md](REQUIREMENTS.md)).
7. **Is an idea outside the instructor's list allowed?** Shopmates is not on it. The closest listed row is "Neighborhood campaign foot-traffic lift estimator". Not confirmed with the instructor.

## Competitors found (quick search, not deep research)

- Minng!: QR cross-promotion between nearby businesses, with commission tokens
- Ohana, Friendly Brands Co-Promotion: cross-promotion between Shopify stores
- Block's Neighborhoods: links Cash App users to Square sellers
- Walkbuy: local deals app (Australia)

**Our wedge:** negotiated two-party agreements between walk-in shops, with explicit terms, caps, expiry, and a fairness check. This claim has not been validated with real shop owners.

## Risks

- **Cold start:** a deal needs two shops. Recruit pilot shops in pairs.
- **Cheating:** redemptions must be staff-confirmed, capped, and one-time.
- **LLM errors:** mitigated by validation, human approval, and a fallback.
- **Hosting limits:** free tier CPU, disk, and outbound-request limits (see DEPLOYMENT.md).
- **Name:** no exact "Shopmates" product found, but Shopmatey (a social shopping app) is close. Domain and trademark not checked.

## Not verified yet (do not state as fact)

- Google sign-in end to end (the button and settings are built; no real keys were used)
- The live LLM call: the request shape follows Gemini's REST API from memory and was only tested against mocks
- That a phone camera scans the QR codes (the codes are generated and render; none was scanned)
- A real deployment, including PythonAnywhere's outbound allowlist and resource limits
- HSTS is deliberately not enabled; `check --deploy` warns about it

- The LLM API host is reachable from PythonAnywhere's free tier
- The chosen provider's free-tier limits
- A free geocoding service works from the deployed site
- Any shop owner is willing to pilot
- Competitor feature details beyond search summaries

## Change log

- 2026-11-15: First working build: models, rules engine, views, APIs, AI drafting with fallback, 94 tests. Docs updated to match.
- 2026-11-14: Initial planning docs written from the ideation conversation.
