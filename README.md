# RWC Living Atlas Helper Chatbot

Standalone chatbot microservice for the [RWC Living Atlas](https://github.com/CEREO-WSU/LivingAtlas1) web application. Extracted from the Living Atlas backend so the chatbot can be developed and deployed independently.

## Architecture

Retrieval-augmented generation driven by **tool calling**: the model decides what to look up, rather than the service guessing from keywords.

**Always injected**, because the model cannot know it needs them:

- **First-pass documentation search** — the raw question goes to a [Pinecone](https://www.pinecone.io/) index with hosted embeddings (`multilingual-e5-large`); Pinecone embeds the query server-side and returns the most relevant knowledge-base chunks. No local embedding model required. This guarantees an answer is never completely ungrounded.
- **Atlas facts** (needs `ATLAS_API_URL`) — public card and ArcGIS counts, the card category and tag vocabulary, and the per-state folder inventory, from the backend's `/atlas/summary`. Cached two minutes. This is the only thing stopping the model guessing at numbers.

**Tools the model may then call** (`chat_tools.py`), up to `MAX_TOOL_ROUNDS` rounds:

| Tool | What it does |
|------|--------------|
| `search_documentation` | Re-searches the docs with a query the model writes — lets it reformulate a vague or non-English question into good English keywords |
| `search_cards` | Live public card records from the backend's `/cards/summary?force=1` |
| `browse_arcgis_catalog` | Live state ArcGIS REST catalog via the skill in `chat_agent.py`; also emits the `atlas-upload://` quick-action links the frontend renders |

Generation is DeepSeek (OpenAI-compatible API). If the configured model rejects the `tools` parameter, the service falls back to running every tool eagerly and answering in one shot, so changing `DEEPSEEK_MODEL` cannot take the chatbot down.

```
main.py            FastAPI app: CORS, /health, mounts the chat router
chat.py            /chat/ask endpoint: prompt assembly, tool-calling loop, error mapping
chat_tools.py      Tool registry: schemas the model sees + handlers that run them
chat_agent.py      Skill framework (ArcGIS live catalog, navigation links)
docs/              Knowledge base: feature documentation indexed into Pinecone
scripts/
  index_docs.py    Chunks docs/ and upserts them into the Pinecone index
```

### Why tool calling

Relevance used to be decided by hardcoded keyword lists — "does the question contain `card`, `dataset`, or `layer`?" That silently failed on anything phrased differently ("what's in the Atlas about salmon?" matched nothing) and on every question not written in English. The model makes that call far more reliably, so the keyword lists are gone. The same reasoning applies on the backend: `/cards/summary` keeps its keyword heuristic for callers that need a cheap guess, but the tool passes `force=1` to skip it, because the decision has already been made.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in the keys
```

Required env vars (see `.env.example`): `PINECONE_API_KEY`, `DEEPSEEK_API`.
Optional: `PINECONE_INDEX`, `DEEPSEEK_MODEL`, `ATLAS_API_URL` (card answers), `ALLOWED_ORIGINS`, `PORT`.

### Index the knowledge base

Creates the Pinecone index on first run (hosted embedding model attached), then chunks and uploads everything in `docs/`:

```bash
python scripts/index_docs.py
```

Re-run whenever files in `docs/` change.

### Run the service

```bash
python main.py
```

Serves on `http://localhost:8001` by default. Smoke test:

```bash
curl -X POST http://localhost:8001/chat/ask -H "Content-Type: application/json" -d "{\"question\": \"How do I change the basemap?\"}"
```

## Connecting the Living Atlas frontend

Point the frontend's chatbot requests at this service's URL (e.g. via a `REACT_APP_CHATBOT_API_URL` env var in the Living Atlas client). The endpoint contract is identical to the original backend `/chat/ask`:

- Request: `{ "question": str, "history": [{ "role": "user"|"assistant", "text": str }] }`
- Response: `{ "answer": str }` (may end with a `Quick actions in Upload Panel:` markdown link list)

## Keeping the knowledge base in sync

`docs/` describes Living Atlas features. When the main app changes, update the matching doc here and re-run `python scripts/index_docs.py`.

### What belongs in `docs/` and what does not

`docs/` is for facts that stay true between releases — how a feature works, where a control lives, what a term or folder abbreviation means.

Anything **countable or enumerable** is deliberately kept out, because it goes stale the moment someone adds a card or an admin edits the ArcGIS catalog. The backend serves those live instead:

| Fact | Live source |
|------|-------------|
| Public card count, contributing organizations, catalog size | `GET /atlas/summary/stats` |
| Card categories, tag vocabulary, location types | `GET /atlas/summary/taxonomy` |
| Per-state ArcGIS service counts, hosts, and folder inventory | `GET /atlas/summary/arcgis` |
| All three in one context block | `GET /atlas/summary` |
| Details of cards matching a question | `GET /cards/summary?q=` |

So: write "the AQ folder holds Air Quality services" in a doc; never write "Washington has ~125 services". If you find yourself typing a number or an exhaustive list into `docs/`, it probably belongs behind one of these endpoints.

All of them are read-only and return public, non-sensitive data only — no Users join, no private cards.
