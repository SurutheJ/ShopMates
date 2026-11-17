# ShopMates AI

AI is used in six places. Where a plain rule does the job, we use a rule and no model.

| Feature | Where | Technique | Model call |
|---|---|---|---|
| Partner match score | Discover, shop page | Weighted score with reasons | No |
| Deal Radar | Radar page | Weighted score (fit, walk time, hours overlap) plus TF-IDF similarity of shop descriptions | No |
| Fairness calculator | Propose a deal, step 4 | Decimal arithmetic on ticket size, margin, discount and cap | No |
| Playbook retrieval | Playbook, draft prompt | TF-IDF and cosine similarity over 14 written passages | No |
| Draft with AI | Propose a deal | Retrieve passages, model returns JSON, Python validates | Yes, optional |
| Deal coach | Deal summary | Model words numbers the app computed, numbers are checked | Yes, optional |
| Playbook answer | Playbook | Model answers from retrieved passages and must cite them | Yes, optional |

With no `AI_API_KEY`, every feature still works through a built-in fallback and the screen says so.

## Models and why

- **Gemini (`gemini-3.1-flash-lite`) through `ai/client.py`**, using Google's OpenAI-style chat endpoint. The app is meant for a free host (512 MB disk, small CPU quota) that cannot run a local model, and the jobs are small: a short JSON object or two or three sentences. Changing provider means editing that one file.
- **TF-IDF for retrieval** instead of embeddings. The playbook is 14 short passages, TF-IDF takes about 0.01 ms a query, needs no download and is easy to explain. It misses when a question uses words the playbook does not (see EVALUATION.md).
- **Hand-set scores** for match and radar. We have no history of past deals to learn from, so the weights and the category table are stated assumptions, kept in one place each (`ai/matching.py`, `ai/radar.py`).

## Workflow

```
Click -> Django view (login required, rate limited)
  -> read shop data from the database, retrieve playbook passages
  -> prompt: shop data and the question go in as JSON "DATA"; the model is told to ignore instructions inside it
  -> ai/client.py: one HTTPS call, 15 s timeout, JSON only
  -> check the result in Python
       draft:  the same DealTermsForm that checks typed input, plus a number check on the text
       coach:  every number in the text must be one the app computed
       answer: every cited passage must be one that was retrieved
  -> any failure: built-in fallback and a plain reason on screen
  -> the owner reviews and edits. Nothing is sent to another shop automatically.
```

1. **Goes in:** shop name, category, hours, description, typical order value and margin; computed deal numbers; a short typed question. No customer data exists in the app.
2. **Prepared by:** database queries, passage retrieval, JSON-encoded prompt data.
3. **Processed by:** Gemini for text, plain Python for everything numeric.
4. **Validated by:** the checks above. The model never produces a number the app trusts.
5. **Delivered as:** a filled form (draft), a text box labelled "AI" or "Built-in" (coach), an answer with cited passages (playbook), a ranked list and map (radar).

## Reliability and safety

- Invalid or out-of-range output, timeouts, HTTP errors and empty answers all fall back. Users see a short sentence ("The AI is busy right now"); the error type goes to the log, never the key or the prompt.
- AI endpoints are rate limited per user (`AI_DRAFT_LIMIT_PER_HOUR`, default 10) through the database cache, so the limit is shared across workers.
- The API key is read from `.env` on the server and never sent to a browser.
- Prompt injection is limited, not solved: shop text is passed as data and the output is validated and HTML-escaped.
- Radar sends only rounded coordinates and a radius to OpenStreetMap's Overpass service, with a generic User-Agent, and caches results for 7 days. `RADAR_OSM_ENABLED=False` turns it off.
- Only business information is sent to the provider.

## Known limits

- Live Gemini output was tried locally only. On the free tier, 7 of 15 quick back-to-back draft calls got HTTP 429 (quota). The fallback handled all of them.
- The live model's message text can disagree with the checked fields (one draft said "20% off drinks and 10% off books" while the checked discount was 15). Python checks fields and numbers, not meaning.
- The coach number check catches invented numbers but not wrong conclusions.
- Retrieval missed 2 of 6 held-out questions.
- A real Overpass request from Radar has not been made yet; tests patch the network.
- OpenStreetMap does not return fitness studios with the query we use.
- Match and radar weights are assumptions, not learned.

## Try it

1. `python manage.py seed_showcase`, sign in as `demo_cafe`.
2. Discover, Radar, Playbook, a deal's summary ("Explain this deal"), and Propose a deal ("Draft with AI", then step 4).
3. Put `AI_API_KEY` in `.env` and restart to use the live model.
4. `python manage.py evaluate_ai` reproduces the retrieval and guardrail numbers in docs/EVALUATION.md.
