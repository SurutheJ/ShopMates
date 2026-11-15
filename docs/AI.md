# AI features

Status: design draft. The provider is open; Gemini was assumed.

## Principle

The LLM is an **assistant**, not the product. The product is the negotiation and redemption workflow. The model writes and explains. Python decides and calculates.

## Features

| Feature | Model does | Code does |
|---|---|---|
| Draft a deal | From two shops' profiles (category, hours, typical order value), proposes terms and writes the message | Validates the terms (discount range, cap is a number, dates make sense) |
| Suggest a counter | Proposes terms that balance a lopsided deal | Checks the suggestion against caps and limits before showing it |
| Explain the balance | Turns computed numbers into plain English ("the cafe sent 14 customers, the bookstore sent 3") | Computes every number |
| Playbook Q&A | Answers "what deal should a bakery offer a flower shop?" using retrieved passages | Retrieves passages from a short written guide and the shop's own past deals, and shows sources |

## Flow

1. A view calls `ai.services.draft_deal(shop_a, shop_b)`.
2. The service builds a prompt from database fields only (no free-text customer data exists).
3. `ai/client.py` sends the request to the provider with a timeout and asks for structured JSON.
4. The service parses and validates the JSON in Python. On any failure, return a fallback message and leave the form blank.
5. The owner reviews and edits. Nothing is sent to another shop until the owner clicks send.

## Guardrails

- The API key lives in `.env` and is only read server-side.
- Only business information goes to the model.
- The model never produces a number that the app then trusts; numbers come from queries.
- One client file means a provider swap touches one place, and tests use a fake client.
- Rate-limit per user to protect the quota.
- A call runs on a button click with a loading state. No background workers.
- Log failures (status and error type), not prompts containing user text, in production.
- Treat model output as untrusted text: escape it in templates.

## Output contract (draft)

Ask the model for JSON like:

```json
{
  "offer_text": "10% off any drink with a Pageturner receipt",
  "discount_percent": 10,
  "redemption_cap": 50,
  "suggested_duration_days": 30,
  "message_to_neighbor": "Hi, we're the cafe next door..."
}
```

Validation rejects: discount outside the allowed range, cap not a positive integer, duration outside the allowed range, missing keys, or text over a length limit.

## Playbook retrieval

A short markdown guide of deal types (reciprocal discount, purchase-triggered benefit, bundled experience, with pros and cons) plus the shop's past deals. Retrieve with TF-IDF and cosine similarity (as in the course RAG notebook) and pass the top passages to the model. No vector database. Show the sources next to the answer.

## What this is not

- Not a local model. A local LLM needs too much disk and CPU for free hosting.
- Not an advisor. Outputs are suggestions; the owner decides.

## To verify before relying on it

- The provider's free-tier limits
- That the provider's host is reachable from the deployed site
- Output quality on realistic shop profiles (try 10 before trusting the prompt)
