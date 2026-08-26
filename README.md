# RWC Living Atlas Helper Chatbot

Standalone chatbot microservice for the [RWC Living Atlas](https://github.com/CEREO-WSU/LivingAtlas1) web application. Extracted from the Living Atlas backend so the chatbot can be developed and deployed independently.

## Architecture

RAG (retrieval-augmented generation) pipeline:

1. **Retrieval** — the user's question is sent to a [Pinecone](https://www.pinecone.io/) index with hosted embeddings (`multilingual-e5-large`); Pinecone embeds the query server-side and returns the most relevant knowledge-base chunks. No local embedding model required.
2. **Live context** — two additional context sources are gathered per question:
   - **Card data** (optional): fetched over HTTP from the Living Atlas backend's `/cards/summary` endpoint — public, non-sensitive card records only; this service never talks to the database directly. Enabled by `ATLAS_API_URL`.
   - **Agent skills**: live ArcGIS REST catalog lookups (`chat_agent.py`) that also produce `atlas-upload://` navigation links the Living Atlas frontend turns into quick actions.
3. **Generation** — DeepSeek (OpenAI-compatible API) writes the answer from the assembled context.

```
main.py            FastAPI app: CORS, /health, mounts the chat router
chat.py            /chat/ask endpoint: retrieval + card context + agent + generation
chat_agent.py      Agent skill framework (ArcGIS live catalog, navigation links)
docs/              Knowledge base: feature documentation indexed into Pinecone
scripts/
  index_docs.py    Chunks docs/ and upserts them into the Pinecone index
```

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
