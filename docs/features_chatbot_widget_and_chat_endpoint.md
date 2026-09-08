# Chatbot Widget and Chat Endpoint

## Scope

This document describes the floating chatbot feature and its backend API contract.

Covered:
- Frontend floating widget behavior
- Message lifecycle and UI states
- Request and response format for `/chat/ask`
- Runtime constraints and failure modes

---

## Frontend Entry and Placement

Component: `ChatbotWidget`
Mounted in: `Home`

The widget is always rendered on Home and appears as a floating handle.

---

## Widget Interaction Model

### Handle behavior
- Default state: collapsed handle near screen edge
- Click handle: toggles open/close state
- Open state: shows full chat panel

### Panel structure
- Header with assistant title
- Message list
- Typing indicator while waiting for response
- Input textarea and send button

### Keyboard behavior
- Enter: send message
- Shift+Enter: newline

### Auto-focus and scrolling
- Input auto-focuses when panel opens
- Message list auto-scrolls to latest item on message/typing updates

---

## Initial and Runtime Messages

### Initial assistant message
On first render, messages contain a fixed notice:
- "RWC Living Atlas Helper is currently under development and is currently unavailable."

### User send flow
1. Trim input
2. Reject empty input or send while loading
3. Append user message
4. POST to `/chat/ask`
5. Append assistant answer on success
6. Append fallback error message on failure

---

## Backend API Contract

Router: `chat_router`
Prefix: `/chat`
Endpoint: `POST /chat/ask`

### Request body
```json
{
  "question": "string",
  "history": [{ "role": "user", "text": "string" }]
}
```

`history` is optional; the most recent few turns are replayed to the model for context.

### Success response
```json
{
  "answer": "string"
}
```

### Validation and errors
- Empty/blank question -> HTTP 400
- Chatbot not configured, or the language-model provider is unreachable, unauthorized, or rate-limited -> HTTP 503
- Provider credits exhausted -> HTTP 402
- Any other provider error -> HTTP 502

Model name, token limits, and provider credentials are supplied by environment variables and are not recorded here — they change without any change to this contract.

---

## How an Answer Is Assembled

The service is retrieval-grounded, not generation-only. For each question it gathers up to four context blocks and injects them into the system prompt:

| Block | Source | What it provides |
|-------|--------|------------------|
| Reference documentation | Pinecone vector search over `docs/*.md` | Stable explanations of how features work |
| Live Atlas facts | Backend `GET /atlas/summary` | Counts, card categories and tags, ArcGIS folder inventory |
| Live card data | Backend `GET /cards/summary` | Public, non-sensitive details of matching cards |
| Live skill outputs | `chat_agent.py` skills | Live ArcGIS REST catalog lookups and navigation links |

The split matters: documentation holds what is *true in general*, while the live blocks hold what is *true right now*. Anything countable or enumerable is served live so it cannot go stale in the docs.

The live blocks require `ATLAS_API_URL` to be set to the Living Atlas backend. When it is unset or the backend is unreachable, those blocks are omitted and the assistant answers from documentation alone rather than failing.

---

## Operational Notes

Not currently included:
- conversation memory persisted across sessions
- source citation for documentation passages (live skill outputs do get a `Sources` section)

The frontend surfaces development-state and fallback failure messaging.
