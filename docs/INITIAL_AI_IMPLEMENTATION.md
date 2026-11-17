# Initial AI implementation

This covers only what we have built and run. What is left is in ROADMAP.md.

## What it does

We want to help an owner pick a good partner and write a fair deal without the AI deciding any number. Four parts work today:

- **Deal Radar and the match score** rank nearby shops by category fit, walking time and opening hours. It is a formula, with no model.
- **The fairness calculator** takes each shop's average sale, margin, discount and cap, and estimates profit for both. It is plain arithmetic and suggests a discount that would even things out.
- **Draft with AI** writes the offer and a message to the neighbor. It fills the normal proposal form, and the owner edits it before sending.
- **The deal coach and playbook Q&A** explain a deal's numbers in a few sentences and answer questions from a short written guide, citing the passages they used.

## Models

Gemini (`gemini-3.1-flash-lite`) writes the text for the draft, coach and playbook answers, and we only call it from `ai/client.py`. We chose a small hosted model because the app is meant for a free host that can't run one locally, and the jobs are short.

For retrieval over the 14 playbook passages we wrote TF-IDF in plain Python. Embeddings would add a download for very little gain.

We used no model for ranking or fairness. We have no past deals to learn from, and a stated formula is easier to defend.

## In and out

| Part | Goes in | Comes out |
|---|---|---|
| Radar | The owner's shop and shops within 300 to 1000 m | A score from 0 to 100, a tier and a one-line reason, on a list and a map |
| Fairness | Average sale, margin, discount and cap for both shops, and months | Profit for each shop, how far apart they are, a suggested discount |
| Draft | Both shops' profiles and the playbook passages we retrieve | Offer text, discount, cap, duration and a message |
| Coach | Numbers our code computed for a deal | A few sentences and renewal terms |
| Playbook | A typed question and the passages we retrieve | An answer with the passages it cites |

## In Django

Each AI feature is a view. It reads the shops from our database, calls a function in our `ai` app and returns JSON or a page. We check every model reply before anyone sees it. A draft goes through the same form that checks typed terms, and any number in the coach text has to be one our code computed. If a check fails, we show a built-in version and say why.

## What we have seen so far

- Our `evaluate_ai` script handled 9 of 9 simulated bad or good model replies correctly. Playbook retrieval put the right passage first on 14 of 14 development questions and 4 of 6 held-out questions.
- In the fairness example, a cafe with a $6 average sale and a bookstore with $24 come out at $132 and $240 over two months, 45% apart. The calculator suggests 17% for the bookstore. This is a unit test.
- Live Gemini drafts took about 1.1 seconds. In a run of 15 quick calls, 7 hit the free-tier limit (HTTP 429) and fell back to the built-in draft, and 8 worked. One draft in the browser timed out at our 15 second limit and we couldn't repeat it.
- All 479 tests pass, and none of them call the network.

## What worries us

- Gemini's free quota is small. We keep live demos to a few calls, and the fallback covers us when we hit the limit.
- We check the fields and numbers in the model's text, not its meaning, so a live draft can still say something that disagrees with them.
- The Radar map loads from OpenStreetMap on our laptops, but our tests fake the nearby-places lookup, and we haven't tried either from a hosted site, where an outbound allowlist could block them.
