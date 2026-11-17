# Initial AI implementation

Only what is built and run is described here. Planned work is in ROADMAP.md.

## The AI feature

Help an owner choose a good partner and write a fair deal, without the AI ever deciding a number. Four parts are working:

1. **Deal Radar and match score** rank nearby shops (rule-based).
2. **Fairness calculator** estimates each shop's profit from the terms (plain arithmetic).
3. **Draft with AI** writes the offer and a message to the neighbor.
4. **Deal coach and playbook Q&A** explain a deal and answer questions with cited sources.

## Models and techniques

- Gemini `gemini-3.1-flash-lite` for the three text tasks, called only from `ai/client.py`. It is a small, fast hosted model, which suits short JSON and short explanations and fits a free host that cannot run a local model.
- TF-IDF with cosine similarity for retrieval, written in plain Python. The playbook is 14 passages, so embeddings would add a download for little gain.
- No model for ranking or fairness. We have no past deals to learn from, so a stated formula is more honest than a trained one.

## Input and output

| Part | In | Out |
|---|---|---|
| Radar | The owner's shop, shops within 300 to 1000 m, optional OpenStreetMap places | Score 0 to 100, tier, one-line reason, map |
| Fairness | Ticket size, margin, discount, cap for both shops, months | Profit for each shop, imbalance, a suggested discount, one sentence |
| Draft | Two shops' profiles, retrieved playbook passages | `offer_text`, `discount_percent`, `redemption_cap`, duration, message (JSON, then checked) |
| Coach | Numbers the app computed for a deal | Two to four sentences and renewal terms |
| Playbook | A typed question, retrieved passages | An answer with cited passages |

## How it works with Django

A view reads the shops from the database, calls a function in `ai/` and returns JSON or a rendered page. The draft fills the normal proposal form, so the owner edits it and presses Send; nothing goes to another shop on its own. The draft is checked with `DealTermsForm`, the same form that validates typed terms. Any failure returns a built-in draft and a short reason.

## Evidence it works

- `python manage.py evaluate_ai`: 9 of 9 simulated bad or good model replies handled correctly (discount 90%, text instead of a number, missing keys, 9999 days, empty offer, a list instead of an object, API error); playbook Hit@1 14/14 on the development set and 4/6 on the held-out set.
- Fairness worked example (cafe ticket $6, margin 65%; bookstore $24, margin 35%; both 10%, cap 50, 2 months): cafe $132.00, bookstore $240.00, 45% apart, "lopsided", suggestion 17% for the bookstore. This is a unit test.
- Live Gemini on a laptop: about 1.1 to 1.3 s per draft. Of 15 back-to-back calls, 7 returned HTTP 429 and fell back, and 8 succeeded (0.9 to 5.3 s, median 1.1 s). One browser draft timed out at our 15 s limit and was not reproduced.
- 479 automated tests pass, none of which make network calls.

## Feasibility and open risks

- The free Gemini quota is tight. The fallback covers it, but a live demo should not make many calls in a row.
- Live text can disagree with the checked numbers. We check fields and numbers, not meaning.
- Radar's OpenStreetMap request has not been made for real yet. Tests patch it.
- A hosted deployment may block the outbound call; we need to check the allowlist on PythonAnywhere.
