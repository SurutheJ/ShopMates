# Decisions, open questions and risks

Keep this current. When a decision changes, edit it here with the date.

## Decided

| # | Decision | Why |
|---|---|---|
| 1 | Idea: ShopMates, a deal desk for neighboring shops | Reachable pilot users, no sensitive data, runs on free hosting, real two-sided workflow |
| 2 | One Django monolith with a hosted model | A free host can't run a local model or several services |
| 3 | Apps: `accounts`, `deals`, `ai`. Only `ai/client.py` talks to the model | Clear boundaries, one place to swap provider |
| 4 | The model drafts text and explains numbers; it never calculates | Results stay trustworthy and testable |
| 5 | A human approves anything before it goes to another shop | Bad AI output never reaches a real business |
| 6 | The owner's main screen is an inbox of actions, not a dashboard | The value is people acting on each other's requests |
| 7 | No payments, no customer accounts, no automatic matching | Scope and risk |
| 8 | Secrets live in `.env`, never in git | Security |
| 9 | Never commit to `main`; feature branches and reviewed PRs | Team convention |
| 10 | Only owners approve, counter or decline. Staff see their shop's pending deals but can't act | Staff only need to confirm redemptions |
| 11 | One time zone, America/Chicago | Our pilot area; dates and exports match what the page shows |

## Implemented choices

| # | Choice | Note |
|---|---|---|
| I1 | One set of terms applies both ways; each shop has its own redemption cap | Simplest fair model |
| I2 | A shop's QR gives customers a voucher for the partner. A redemption at shop B counts as "A sent a customer" | Each deal has two secret UUID tokens |
| I3 | A counter-offer is a new version and flips whose turn it is | Statuses: draft, proposed, countered, accepted, active, completed, declined, expired, withdrawn |
| I4 | Time-based transitions run when a deal is read or redeemed, plus a management command | No background scheduler |
| I5 | One shop per user; staff are added by an owner using an existing username or email | Multi-location is later |
| I6 | New shops are auto-approved in development, admin-approved in production | `SHOPS_AUTO_APPROVE` |
| I7 | A pair of shops can have one live deal at a time | Avoids ambiguous QR codes and double counting |
| I8 | Two fairness views. The deal summary compares estimated discount cost (redemptions x discount x typical spend) and calls a deal lopsided at 4 or more redemptions and a gap of 40% or more. The proposal calculator estimates profit per shop (redemptions x (margin x ticket - discount)) and calls it lopsided at 25% apart | Thresholds are our guesses. Margin defaults to 50% and is marked "assumed" |
| I9 | The draft fallback is a rule-based draft with a cap scaled by the spend gap | Shown with the reason AI was not used |
| I10 | Coordinates are entered by hand; Radar uses OpenStreetMap for nearby places | Address lookup not built |
| I11 | The public stats API hides any category with fewer than 5 shops | Avoids identifying a shop |

## Open

1. Pilot area: which street or neighborhood.
2. Whether notifications are email or in-app only.
3. Whether an idea outside the instructor's list was acceptable. ShopMates is not on it; we have not heard otherwise.
4. Terms of use and privacy pages: wording, and whether we offer export and delete of account data.

## Competitors (quick search, not deep research)

- Minng!: QR cross-promotion between nearby businesses, with commission tokens
- Ohana, Friendly Brands Co-Promotion: cross-promotion between Shopify stores
- Block's Neighborhoods: links Cash App users to Square sellers
- Walkbuy: local deals app (Australia)

Our angle is a negotiated agreement between two walk-in shops, with caps, expiry and a fairness check. We haven't validated that with shop owners.

## Risks

- **Cold start:** a deal needs two shops, so pilot shops must join in pairs.
- **Cheating:** redemptions are staff-confirmed, capped and one-time.
- **Model errors:** validation, human review and a fallback.
- **Hosting limits:** free-tier CPU, disk and outbound allowlist.
- **Name:** no exact "ShopMates" product found, but "Shopmatey" is close. Domain and trademark not checked.

## Not verified yet

- A deployed site, including PythonAnywhere's allowlist and resource limits
- Google sign-in on the host (works locally)
- Phone camera scanning of the QR codes
- A real Overpass request from Radar
- Safari and Firefox, and the app on a real phone
- Any shop owner's willingness to pilot
- HSTS is short on purpose; `check --deploy` still warns about subdomains and preload
