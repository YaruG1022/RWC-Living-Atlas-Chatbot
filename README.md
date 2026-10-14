# RWC Living Atlas Helper

The helper retrieves feature instructions from **the same chapter content rendered by the app's User Manual**. `docs/*.md` is retained only as historical reference; neither chat nor indexing reads it.

## Data flow

1. The app maintains `client/src/manual/sections/*.json`. React renders those blocks while retaining its existing layout and interactive examples.
2. Each app build validates the catalog and exports `/manual/current.json` plus an immutable `/manual/releases/<version>/` bundle. The manifest records the app commit, chapter/block inventory, SHA-256 and byte count.
3. The app workflow waits until that exact release is published, then sends `atlas-manual-published` to this repository. Failed/cancelled app deployments do not dispatch. A serialized 15-minute scheduled sync also reconciles the published marker; GitHub may delay schedules.
4. This repository fetches the configured app origin, validates the manifest/bundle and accessible manual page, and writes a new Pinecone namespace. It checks every record, exact count and a filtered search for each chapter.
5. Immediately before activation it checks the published app version again. Only then is the durable `manual-control/active-manual` record updated. Old namespaces remain available. Duplicate active versions do not reindex.
6. Chat pins one active version for the entire request, including tool retries. Structured `sources` carry verified chapter links, version and block/step/image IDs. The service resolves links from retrieved records; it removes model-generated manual URLs.

Generation continues through DeepSeek. Live `search_cards`, Atlas summary facts and state ArcGIS catalog tools remain separate: changing counts, tag/category vocabulary and inventories never come from manual examples. For icon, position and layout questions, the model can call `inspect_manual_visuals` with verified text and version-matched screenshots through a separately configured OpenAI-compatible vision API. Text-only questions do not incur a vision call. Missing images/configuration/provider failures fall back to sourced text with an explicit limitation.

## Run locally

```bash
python -m venv .venv
# Activate .venv, then:
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Set `PINECONE_API_KEY` and `DEEPSEEK_API` in the service environment. Optional `ATLAS_API_URL` enables live public cards and summary facts. `PINECONE_INDEX` defaults to `living-atlas-docs-hosted`; use `PINECONE_INDEX_HOST` to target an existing index directly. The index must support integrated embeddings with source text mapped to `content` (default model `multilingual-e5-large`).

Set the app frontend's `REACT_APP_CHATBOT_API_URL` to this service origin and allow the app origin in this service's `ALLOWED_ORIGINS`. The app backend in the current checkout does not contain `/chat/ask`; do not rely on the old widget comment about a built-in fallback.

Request: `{ "question": "...", "history": [{ "role": "user", "text": "..." }] }`.
Response: `{ "answer": "...", "sources": [{ "section_id": "add-card", "title": "Card Creation Form", "url": "https://<app>/user-manual?section=add-card", "version": "<sha>-<digest-prefix>", "revision": "<sha>", "block_ids": [], "step_ids": [], "image_ids": [] }] }`.

The widget remains compatible with an older response containing only `answer`, but the deployed service must be upgraded to stop consulting legacy knowledge. Before the first manual is activated, the new service reports that feature knowledge is unavailable; it never falls back to the old docs namespace. Deploy the package and activate its first index before switching traffic to the upgraded service.

## Repository configuration

In the **app repository**, configure:

| Kind | Name | Purpose |
|---|---|---|
| Variable | `ATLAS_MANUAL_BASE_URL` | Canonical published HTTPS app origin, without a path |
| Variable | `CHATBOT_REPO` | This repository as `owner/repo` |
| Optional secret | `CHATBOT_DISPATCH_TOKEN` | Fine-grained token scoped to this repository, Contents write for immediate repository dispatch; scheduled reconciliation does not require it |

In **this repository**, configure:

| Kind | Name | Purpose |
|---|---|---|
| Variable | `MANUAL_BASE_URL` | Same canonical published app origin |
| Secret | `PINECONE_API_KEY` | Index access for the sync job |
| Variable, optional | `PINECONE_INDEX` | Same index used by the running service |
| Variable, optional | `PINECONE_INDEX_HOST` | Existing index host |
| Variable, optional | `PINECONE_EMBED_MODEL` | Default `multilingual-e5-large` |

Use the same index settings in the running service. GitHub Actions writes the durable active pointer directly; Render processes observe it on subsequent requests, without depending on an ephemeral worker file or GitHub committing a generated pointer. When pointer lookup fails temporarily, a process may continue with its last validated pointer. Index query failures return an unavailable message, never cached legacy instructions.

The two workflows serialize publication and indexing. All index writers must use the same CI queue; do not run simultaneous manual activation/rollback jobs. Cancellation can leave an unused staged namespace, which is safe to retry. Record counts/search readiness are eventually consistent; verification retries for up to one minute by default. No code automatically deletes any namespace.

## Import, retry and rollback

```bash
# Verify/stage the currently published app manual (no active switch):
MANUAL_BASE_URL=https://<app-origin> python scripts/index_docs.py

# Operator activation after validating the deployed release:
MANUAL_BASE_URL=https://<app-origin> python scripts/index_docs.py --revision <full-app-commit-sha> --activate

# Validate a generated local release against its checksum; stage only:
MANUAL_BASE_URL=https://<app-origin> python scripts/index_docs.py --bundle-dir /path/to/manual/releases/<version>

# Explicit recovery to an already validated retained namespace:
python scripts/index_docs.py --rollback <previous-version>
```

The sync workflow uses the dispatch's commit/version/checksum as expectations, but fetches only the configured origin; payloads cannot select URLs or shell commands. A stale queued event fails safely if a newer app is published. Retry a failed job after fixing the failed stage; a retry resumes deterministic upserts, and an already active version performs no writes. A manual workflow run with an empty revision imports the currently published version.

Rollback checks the retained release inventory and chapter searches before changing the pointer. Coordinate rollback with the corresponding app release if its instructions differ. Old namespaces and the legacy docs can be removed only after release acceptance and a separately planned retention cleanup.

## Verification

```bash
pip install pytest httpx
python -m pytest -q tests
```

Tests use an app-exported representative fixture, a Pinecone substitute, mocked live tools and mocked model responses. They verify publication/checksum guards, failed and repeated updates, stale deployment events, rollback, request-version consistency, real source resolution, API contract and refusal to query legacy docs. They do not measure live semantic relevance, model answer accuracy/cost or production latency. In a restricted sandbox, ASGI TestClient needs permission for its local event-loop sockets even though external providers are mocked.

## Visual configuration and evidence

In the Render chatbot service, set `VISION_API_KEY` and `VISION_MODEL` (for example `gpt-4.1-mini`); `VISION_BASE_URL` defaults to `https://api.openai.com/v1`. The model must support OpenAI-style `image_url` message parts. Its key is independent from `DEEPSEEK_API`, stays server-side and is never forwarded to the text provider. No user screenshot upload is part of this feature.

The app build uses Playwright and packaged Chromium to capture all manual chapters/examples, including separate gallery states. Its optional `visuals` manifest descriptor points to a SHA-256-addressed catalog and PNGs. The importer verifies catalog digest, dimensions, chapter/block/step/example references and coverage before activation. Records carry related screenshot IDs. Each request pins text and visuals to one release; the runtime verifies each selected PNG again before sending a data URL to the vision provider. Arbitrary model-supplied URLs, redirects, HTML fallback, unbounded images and cross-version catalogs are rejected. Default text-only manifests remain importable.

At most one visual tool call, two PNGs (each <=2 MB), 1,000 visual output tokens and no provider retries per question. Text fallback for a model without tool support never eagerly invokes vision. Catalog cache is bounded to four validated versions. Provider/catalog/image failures have explicit fallbacks; no namespace is deleted. Old image URLs may become unavailable when deployments are retired, in which case the retained text namespace still works.

`/health` exposes the manual protocol, Render commit and whether vision configuration is present. Configuration is not proof of a successful provider call. `/chat/ask` adds machine-readable `metrics` with request duration, text completion token usage and visual status/usage; the app displays only `answer` and `sources`.

## Release evaluation

`evaluation/manual-cases.json` contains 11 English/Chinese, text, visual, multistep, unsupported and live-data questions. The manual `Evaluate published manual answers` workflow runs a selected subset against the actual deployed API and uploads the complete results. Default T01,T03,V01 is three sequential billed requests, not a load test. Enable require_vision after configuring the visual provider.

```bash
python scripts/evaluate_manual.py --base-url https://rwc-living-atlas-chatbot.onrender.com --ids T01,T03,V01 --expected-version <published-version> --output /tmp/manual-evaluation.json
# Add --require-vision to require actual visual evidence.
# Optional --text-input-price/--text-output-price/--vision-input-price/--vision-output-price:
# USD per million tokens from your actual provider plan, not assumed prices.
```

The evaluator checks source/version consistency, required chapter references, visual use and unnecessary visual calls. Human review is still required for correctness, complete prerequisites/steps, supported citations and honest unknown answers. It records p50/p95/p99 for the supplied sample; small samples are not capacity evidence. Missing prices/usage produce null model cost. Estimates exclude Pinecone/hosting/other provider fees. Save a text-only baseline for the same release/service before comparing visual cases.

Tests cover 22 contracts/recovery cases with substitutes. Visual fixtures are synthetic for protocol checks; the app's full 21-chapter export and 146 real Playwright captures are separately validated. No real-model correctness or cost claim follows from a mocked completion. Actual release results belong in the PR/release record.
