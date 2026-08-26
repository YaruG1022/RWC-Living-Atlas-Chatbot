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
  "question": "string"
}
```

### Success response
```json
{
  "answer": "string"
}
```

### Validation and errors
- Empty/blank question -> HTTP 400
- Missing `OPENAI_API_KEY` -> HTTP 503
- OpenAI API exception -> HTTP 502

---

## Model and Prompt Behavior

Backend sends:
- A Living Atlas system prompt with product/domain constraints
- User question as chat input

Default model:
- `OPENAI_MODEL` env var if set
- fallback: `gpt-4.1-mini`

Generation settings include:
- temperature 0.4
- max_tokens 600

---

## Operational Notes

Current implementation is generation-only and does not include:
- RAG retrieval grounding
- conversation memory persistence
- source citation in responses

The frontend already surfaces development-state and fallback failure messaging.
