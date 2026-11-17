# ShopMates: updated product scope

Team 22: Suruthe Jayachandran and Sahithi Madabhushi (equal contributors). Compared against our P2-A2 proposal and wireframes.

## Idea

ShopMates helps independent shops near each other turn informal cross-promotions into agreed, trackable deals. A shop proposes terms to a neighbor, they negotiate, customers redeem with a QR code that staff confirm, and both shops see whether the deal is fair. The idea is the same as in P2-A2. The scope below is what we are building and what moved.

## Problem

Neighboring shops share foot traffic but have no ad budget. Their arrangements live in conversation and paper coupons, so (1) nobody has a record of the terms, (2) redemptions can't be checked without trusting the other shop's count, and (3) nobody can tell if the deal is fair, so it quietly lapses.

## Users

- **Shop owner:** sets up the shop, proposes and negotiates deals, reads results.
- **Staff:** confirms redemptions on a phone. Can see their shop's pending deals but cannot act on them.
- **Customer:** opens a QR link and shows a one-time code. No account.
- **Admin:** approves new shops through Django admin.

Pilot area: shops near the UIUC campus. We have not yet asked any shop owner, so this is not evidence of demand.

## Three core features

1. **Negotiated deals.** Proposal, accept, counter or decline, version history, one live deal per pair of shops.
2. **Staff-confirmed QR redemption.** Caps, dates, expiry, and a redemption that can only count once.
3. **Fairness and AI help.** Sent vs received, estimated profit for each side in dollars, a suggested renewal, Deal Radar to find good partners, and an AI draft and coach whose numbers the app checks.

## Major changes from P2-A2

- **Finding partners.** We planned a nearby search backed by a geocoding service. We built Deal Radar instead, which ranks nearby shops on a map using OpenStreetMap data. Address lookup is still open, so owners type coordinates for now.
- **The AI helper.** We planned one helper that drafts proposals and suggests terms. It is now three pieces: a draft, a fairness calculator that is plain arithmetic, and a coach that explains the numbers. The model never produces a number the app relies on.
- **Fairness in dollars.** It is measured by estimated profit for each shop, and an owner can check it before sending a deal, not only after it ends.
- **Notifications are on hold.** The inbox is the only place waiting actions show up.

Still out of scope: payments, customer accounts, automatic shop matching.

## Differences from existing tools

Minng! and similar tools hand out coupons. ShopMates keeps a negotiated agreement between two shops and shows who is paying for it.
