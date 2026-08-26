"""
index_docs.py — Index docs/ markdown files into Pinecone using Pinecone's
hosted (integrated inference) embedding model.

No local embedding model is needed: raw text is uploaded and Pinecone embeds
it server-side with the model attached to the index.

Required env vars:
  PINECONE_API_KEY      — your Pinecone API key

Optional env vars:
  PINECONE_INDEX        — index name (default: "living-atlas-docs-hosted")
  PINECONE_EMBED_MODEL  — hosted model (default: "multilingual-e5-large")

Usage:
  python scripts/index_docs.py
"""

import os
import sys
from pathlib import Path

print("=== index_docs.py starting ===", flush=True)

# Load .env from the repo root if present (local development)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except Exception as _e:
    print(f"[dotenv] Warning: {_e}", flush=True)

MAX_CHARS = 400
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX", "living-atlas-docs-hosted")
PINECONE_EMBED_MODEL = os.environ.get("PINECONE_EMBED_MODEL", "multilingual-e5-large")
NAMESPACE = "__default__"


# ---------------------------------------------------------------------------
# Chunking: split by paragraphs, merge short consecutive ones up to max_chars
# ---------------------------------------------------------------------------
def chunk_markdown(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        candidate = f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph

    if current:
        chunks.append(current)

    return [c for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Pinecone helpers
# ---------------------------------------------------------------------------
def get_pinecone_index(api_key: str):
    """Connect to (or create) the integrated-embedding index and return it."""
    try:
        from pinecone import Pinecone
    except ImportError as exc:
        raise RuntimeError(
            "pinecone is required. Install it with: pip install pinecone"
        ) from exc

    pc = Pinecone(api_key=api_key)

    existing = [idx.name for idx in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in existing:
        print(
            f"Index '{PINECONE_INDEX_NAME}' not found — creating it "
            f"with hosted model '{PINECONE_EMBED_MODEL}'..."
        )
        pc.create_index_for_model(
            name=PINECONE_INDEX_NAME,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": PINECONE_EMBED_MODEL,
                "field_map": {"text": "content"},
            },
        )
        print(f"✓ Index '{PINECONE_INDEX_NAME}' created.")
    else:
        print(f"✓ Using existing index '{PINECONE_INDEX_NAME}'.")

    return pc.Index(PINECONE_INDEX_NAME)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    api_key = os.environ.get("PINECONE_API_KEY", "").strip()
    if not api_key:
        print("Error: PINECONE_API_KEY environment variable is not set.")
        return 1

    docs_dir = Path(__file__).resolve().parents[1] / "docs"
    md_files = sorted(docs_dir.glob("*.md"))

    if not md_files:
        print(f"No markdown files found in {docs_dir}")
        return 0

    index = get_pinecone_index(api_key)

    # Clear existing records for a clean re-index
    print("Clearing existing records from index...")
    try:
        index.delete(delete_all=True, namespace=NAMESPACE)
    except Exception as e:
        print(f"  (Clear warning — continuing anyway: {e})")
    print("✓ Index cleared.")

    records = []
    total_chunks = 0

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        chunks = chunk_markdown(text)

        for i, chunk in enumerate(chunks):
            records.append({
                "_id": f"{md_file.stem}-{i}",
                "content": chunk,
                "source": md_file.name,
            })
            total_chunks += 1

        print(f"✓ Prepared {md_file.name} — {len(chunks)} chunks")

    # upsert_records accepts at most 96 text records per batch
    BATCH_SIZE = 90
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        index.upsert_records(records=batch, namespace=NAMESPACE)
        print(f"  Upserted batch {i // BATCH_SIZE + 1} ({len(batch)} records)")

    print(f"\nDone. Total chunks indexed into Pinecone: {total_chunks}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        import traceback
        print(f"\nIndexing failed: {exc}")
        traceback.print_exc()
        sys.exit(1)
