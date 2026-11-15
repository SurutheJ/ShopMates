# Product: users, screens, lifecycle, rules

Status: the MVP below is built and tested. Items marked (P) were proposals; the implemented choice is noted in DECISIONS.md.

## Users and permissions

| Role | Can | Cannot |
|---|---|---|
| Owner | Edit own shop, create/send/answer proposals, view own deals and redemptions, invite staff, export own data | See another shop's private data |
| Staff | Open the redeem page for their shop's active deals and confirm redemptions | View deal terms history, stats, or export |
| Customer (no account) | Open a voucher link, view the offer, receive a one-time code | Anything else |
| Admin | Approve or suspend shops, moderate, view everything via Django admin | n/a |

A shop only ever sees deals it is a party to.

## Screens (MVP)

| # | Screen | Who | Contents |
|---|---|---|---|
| 1 | Landing and sign-in | Anyone | What it is, Google sign-in |
| 2 | Shop setup | Owner | Name, category, address, hours, typical order value |
| 3 | Home inbox | Owner | Actions waiting on you first (proposals to answer, counters, deals ending soon), then active deals |
| 4 | Discover | Owner | Search nearby shops by category and distance; shop detail page with "Propose a deal" |
| 5 | Proposal builder | Owner | Offer text, dates, redemption cap, terms, "Draft with AI" |
| 6 | Deal room | Owner | Current terms, version history, messages, Accept / Counter / Decline |
| 7 | Active deal | Owner | Redemptions so far, sent vs received, printable QR |
| 8 | Deal summary | Owner | Fairness view, renewal suggestion, CSV and JSON export |
| 9 | Redeem | Staff | Enter or scan a code; shows valid or the reason it isn't; Confirm |
| 10 | Voucher | Customer | Offer, shop, validity, one-time code |
| 11 | Public stats | Anyone | Anonymized aggregates (see API section in ARCHITECTURE.md) |

The home inbox is the primary screen. If a screen is only charts, it is secondary.

## Deal lifecycle

Statuses: draft, proposed, countered, accepted, active, completed, declined, expired, withdrawn.
While a deal is being negotiated, `turn` says which shop must answer next.

| From | Action | To | Who |
|---|---|---|---|
| draft | send | proposed (turn: recipient) | proposer owner |
| proposed or countered | accept | accepted | owner of the shop whose turn it is |
| proposed or countered | counter | countered (new version, turn flips) | owner of the shop whose turn it is |
| proposed or countered | decline | declined | owner of the shop whose turn it is |
| draft, proposed or countered | withdraw | withdrawn | proposer owner |
| proposed or countered | response deadline passes | expired | system |
| accepted | start date reached | active | system |
| accepted or active | end date passes, or both shops hit their cap | completed | system |

Rules:
- Only one version of the terms is open at a time. Accepting always accepts the latest version.
- An accepted deal's terms can't be edited. A change means a new deal.
- Accepting terms whose end date has passed is refused ("counter with new dates").
- Two shops can have only one live deal (draft through active) at a time.
- Every transition is recorded (who, what, when).
- Time-based transitions run lazily whenever a deal is read or redeemed, and via `manage.py update_deal_statuses`. There is no background scheduler.

## Redemption rules

1. A customer opens a shop's QR link and receives a one-time code valid 24 hours (P1), good at the *partner* shop. The same terms apply in both directions; each shop has its own cap.
2. Staff of the *partner* shop open the redeem page, enter or scan the code, and confirm.
3. The system rejects a redemption if: the deal isn't active, the date is outside the window, the cap is reached, the code is expired, or the code was already used.
4. A confirmed redemption stores the code, time, shop and staff user. It stores no customer information.
5. Confirmation must be idempotent: confirming the same code twice does not count twice.

## Fairness view (P3)

For each shop in a deal:
- Customers sent (redemptions made at the partner using this shop's referral)
- Customers received
- Estimated discount cost = redemptions at this shop x discount x typical order value

The summary shows the balance and, if it is lopsided beyond a threshold, suggests a renewal with adjusted terms. All numbers are computed in Python; the AI only explains them (see AI.md).

## Phases

- **MVP:** everything above, plus public stats API and AI drafting.
- **Later:** email notifications, multi-location shops, bundled "passport" deals.
- **Out of scope:** payments, customer accounts, automatic shop matching.

## Pilot plan (not yet done)

Visit 3 to 5 shops near campus and ask: "Would you try a deal with the shop next door?" Record answers verbatim. Do not claim shop interest in any document until this is done.
