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

`docs/` describes Living Atlas features. Two GitHub Actions workflows keep it honest:

- **[`reindex-docs.yml`](.github/workflows/reindex-docs.yml)** — any push to `main` touching `docs/**` or `scripts/index_docs.py` rebuilds the Pinecone index automatically. You no longer need to run the indexer by hand; the *Actions* tab has a manual "Run workflow" button for when you do. Runs are serialised (`concurrency: pinecone-index`) and never cancelled mid-flight, because the script clears the index before upserting and a half-finished run would leave it empty.
- **[`docs-drift-alert.yml`](.github/workflows/docs-drift-alert.yml)** — the main app repo pings this repo when its user-facing documentation changes, and this opens (or comments on) an issue labelled `docs-drift` asking someone to check `docs/` for drift.

### Why the drift alert is a nudge rather than a sync

The obvious idea is to index the main repo's docs directly and delete the copies here. It does not work in this codebase:

- That repo's `documentation/` folder holds project deliverables — sprint reports, client meeting notes, final report PDFs. It is not a description of how the app behaves, and indexing it would fill the chatbot's knowledge base with course paperwork.
- The real user-facing documentation lives in `client/src/UserManual.js`: 240 KB of React, with the prose interleaved with icons, styling, and interactive demos. Any extractor would be guessing at what is content and what is chrome, and would break on the next refactor.

So the duplication stays, and CI makes it visible instead of silent: when the manual changes, an issue appears here. If the user manual is ever moved into Markdown, indexing it directly becomes worth revisiting.

### One-time setup

In **this** repo, under *Settings → Secrets and variables → Actions*:

| Kind | Name | Value |
|------|------|-------|
| Secret | `PINECONE_API_KEY` | Your Pinecone API key |
| Variable *(optional)* | `PINECONE_INDEX` | Index name, if not `living-atlas-docs-hosted` |
| Variable *(optional)* | `PINECONE_EMBED_MODEL` | Hosted model, if not `multilingual-e5-large` |

In the **main Living Atlas** repo, for the drift alert:

| Kind | Name | Value |
|------|------|-------|
| Secret | `CHATBOT_DISPATCH_TOKEN` | A fine-grained PAT scoped to *this repo only*, with **Contents: read and write** |
| Variable | `CHATBOT_REPO` | `YaruG1022/RWC-Living-Atlas-Chatbot` |

`Contents: write` is what GitHub's `POST /repos/{owner}/{repo}/dispatches` endpoint requires — it is the documented permission for sending a `repository_dispatch`, not a sign the token edits files. Scope the token to this one repository so that is all it can reach. The issue itself is filed by this repo's own `GITHUB_TOKEN`, so the PAT needs no issue permissions.

If either the secret or the variable is missing, the notifier logs a warning and skips, rather than failing the main app's build.

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
