# Cards Database — What the Chatbot Can Answer

## Scope

This document tells the chatbot what it can and cannot say about the **cards** stored in the Living Atlas database. The assistant can answer questions about the cards that currently exist — for example counts, categories, organizations, tags, locations, and descriptions — using **live data** pulled from the database at question time.

Crucially, the assistant only ever sees **public, non-sensitive** card fields. It never has access to usernames, emails, passwords, or any account information, and it will not reveal who created a card.

---

## What a Card Is

A card is the core data unit of the Living Atlas — a geographically located environmental resource shown on the map as a point, polygon, or image overlay. (See the Create Card documentation for how cards are made.)

---

## Fields the Chatbot Can Use (Public, Non-Sensitive)

When answering card questions, the assistant is given only these fields:

| Field | Description |
|-------|-------------|
| Title | The card's name |
| Category | River, Watershed, Places, Other, or None |
| Description | Text describing the card's content |
| Organization | The institution/organization that produced the data |
| Funding | The funding source, if provided |
| Tags | Comma-separated keywords |
| Link | An external URL associated with the card |
| Latitude / Longitude | The card's map location |
| Location Type | point, polygon, or image overlay |
| Date Posted | When the card was created |

The assistant also receives summary statistics: the **total number of public cards** and a **breakdown by category**.

---

## Fields the Chatbot Can NEVER Access or Reveal

The following are **excluded by design** — the chatbot's data query never selects them and never joins the Users table:

- **Username** of the card's creator
- **Email** address
- **Password / hashed password / salt**
- **User ID** or any account identity
- Any **private (uploader-only)** cards — only cards marked public are visible to the assistant

If a user asks "who created this card?", "what is the uploader's email?", or anything about user accounts or credentials, the assistant must politely decline and explain that contributor identities and account data are private.

---

## How the Live Query Works (for reference)

- The backend detects card-related questions and runs a fixed, parameterized, **read-only** query.
- Only the public columns listed above are selected; the query filters out private cards (`is_public IS NOT FALSE`).
- The assistant does **not** write or execute SQL itself — the backend runs a safe, hardcoded query and passes the results in as context. This prevents SQL injection and accidental exposure of sensitive data.
- Results are limited (most recent or keyword-matched cards) to keep responses focused.

---

## Example Questions the Chatbot Can Answer

- "How many cards are in the Atlas?"
- "How many cards are in each category?"
- "What cards are about water quality?"
- "List some cards from a specific organization."
- "Are there any cards tagged 'salmon'?"
- "What's the description of the card titled X?"
- "Where is the card about the Columbia River located?"

## Example Questions the Chatbot Will Decline

- "Who uploaded this card?"
- "What's the username/email of the person who created card X?"
- "Show me a user's password."
- "List all registered users."

---

## Frequently Asked Questions

**Q: Can the chatbot tell me how many cards exist right now?**
A: Yes. It reads live summary data from the database, including the total public card count and a per-category breakdown.

**Q: Can it find cards about a topic?**
A: Yes. It can match cards by keywords against the title, description, organization, and tags, and summarize what it finds.

**Q: Will it tell me who made a card?**
A: No. Contributor identities (username, email) and all account data are private and are never provided to the assistant.

**Q: Can the chatbot see private or unpublished cards?**
A: No. Only cards marked public are included in what the assistant can see.

**Q: Is the card data live or a static snapshot?**
A: Live. The assistant queries the current database each time a card-related question is asked.

---

## Glossary

| Term | Meaning |
|------|---------|
| Card | The core geolocated data unit of the Living Atlas |
| Category | The card's classification: River, Watershed, Places, Other, or None |
| Tag | A keyword attached to a card for search/filtering |
| Public card | A card visible to everyone; only these are exposed to the chatbot |
| Private (uploader-only) card | A card visible only to its creator; never exposed to the chatbot |
| Sensitive data | Usernames, emails, passwords — never accessible to the chatbot |
