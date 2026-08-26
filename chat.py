"""
chat.py  —  /chat/ask endpoint

Docs retrieval: Pinecone with hosted (integrated inference) embeddings — the
query text is embedded server-side by the model attached to the index.
Card data:      fetched over HTTP from the Living Atlas backend's
                /cards/summary endpoint (optional, enabled by ATLAS_API_URL).
Agent skills:   live ArcGIS catalog lookups + navigation links (chat_agent.py).
Generation:     DeepSeek API (OpenAI-compatible), set DEEPSEEK_API.
"""

import os
from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from openai import APIConnectionError, APITimeoutError, OpenAI

from chat_agent import build_default_chat_agent

chat_router = APIRouter(prefix="/chat", tags=["chat"])

NAMESPACE = "__default__"
_CHAT_AGENT = build_default_chat_agent()

# ---------------------------------------------------------------------------
# System prompt: gives the model context about the Living Atlas project
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_BASE = """You are the RWC Living Atlas Helper, an AI assistant for the
Regional Water Center (RWC) Living Atlas web application — an interactive map
that showcases environmental datasets, GIS layers, and research resources for
the Pacific Northwest (Idaho, Oregon, and Washington).

Answer the user's question using the reference documentation, live card data, and skill outputs provided below.
If the documentation does not cover the question, say so honestly — do not invent information.
Be concise, friendly, and factual.
Do not answer questions unrelated to the Living Atlas or environmental/GIS topics.

For ArcGIS folder/service/layer questions, prioritize LIVE SKILL OUTPUTS over static docs when available.
If LIVE SKILL OUTPUTS contain ArcGIS catalog entries, do not respond with "docs do not contain this".

When live skill outputs are relevant to the answer, append a final section titled exactly:
Sources
Then include 1-4 bullet points in this format:
- [ArcGIS live catalog] <source snippet>
Use the provided structured source snippets when available.

PRIVACY (strict): The card data you receive contains only public, non-sensitive fields.
It never includes usernames, emails, passwords, or any account/identity information.
Never reveal, guess, or discuss who created or uploaded a card, and never disclose any
user's username, email, password, or contact details. If asked who made a card or for any
user's personal or login information, politely decline and explain that contributor
identities and account data are private and not accessible to this assistant.

⚠️ This feature is under development. Always verify critical information with the original data source.
"""


# ---------------------------------------------------------------------------
# Pinecone retrieval (hosted embeddings — text in, matches out)
# ---------------------------------------------------------------------------
def get_pinecone_index():
    """Return a Pinecone Index object. Raises RuntimeError if not configured."""
    api_key = os.environ.get("PINECONE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY environment variable is not set.")

    index_name = os.environ.get("PINECONE_INDEX", "living-atlas-docs-hosted")

    from pinecone import Pinecone

    pc = Pinecone(api_key=api_key)
    return pc.Index(index_name)


def get_relevant_docs(question: str, top_k: int = 3) -> str:
    """Query Pinecone for the top-k most relevant chunks. Fails silently."""
    try:
        index = get_pinecone_index()

        result = index.search(
            namespace=NAMESPACE,
            top_k=top_k,
            inputs={"text": question},
        )

        hits = result["result"]["hits"]
        if not hits:
            return ""

        chunks = [
            hit["fields"]["content"]
            for hit in hits
            if hit.get("fields", {}).get("content")
        ]
        return "\n\n---\n\n".join(chunks)

    except Exception as exc:
        print(f"[chat] Retrieval warning: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Live card data (non-sensitive, optional)
# ---------------------------------------------------------------------------
# Lets the assistant answer questions about the cards currently in the Living
# Atlas database. The card summary is fetched over HTTP from the main
# backend's /cards/summary endpoint, which returns public, non-sensitive card
# data only — this service never talks to the database directly. Enabled by
# setting ATLAS_API_URL; when unset, card questions gracefully fall back to
# docs-only answers.
# ---------------------------------------------------------------------------
_CARD_QUERY_KEYWORDS = (
    "card", "cards", "dataset", "datasets", "data point", "datapoint",
    "marker", "markers", "pin", "pins", "monitoring", "station", "stations",
    "how many", "count", "list", "show me", "what data", "which data",
    "uploaded", "contributed", "category", "categories", "tag", "tags",
    "river", "watershed", "places", "water quality", "organization",
)

def _looks_like_card_question(question: str) -> bool:
    lowered = question.lower()
    return any(keyword in lowered for keyword in _CARD_QUERY_KEYWORDS)


def get_card_context(question: str) -> str:
    """Fetch the card-context block from the Living Atlas backend. Fail silently."""
    if not _looks_like_card_question(question):
        return ""

    base = os.environ.get("ATLAS_API_URL", "").strip().rstrip("/")
    if not base:
        return ""

    try:
        resp = requests.get(
            f"{base}/cards/summary",
            params={"q": question},
            timeout=8,
        )
        resp.raise_for_status()
        context = resp.json().get("context", "")
        return context if isinstance(context, str) else ""
    except Exception as exc:
        print(f"[chat] Card context warning: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str
    history: list[dict[str, Any]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@chat_router.post("/ask", response_model=ChatResponse)
def ask(payload: ChatRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    raw_api_key = os.environ.get("DEEPSEEK_API", "")
    api_key = raw_api_key.strip()
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Chatbot is not configured (missing DEEPSEEK_API). Please contact the administrator.",
        )
    if raw_api_key != api_key:
        # Env vars sometimes include trailing newline/space from copy-paste.
        print("[chat] Warning: DEEPSEEK_API contained leading/trailing whitespace; sanitized automatically.")

    doc_context = get_relevant_docs(question)
    card_context = get_card_context(question)
    agent_result = _CHAT_AGENT.build_skill_context(question)
    skill_context = agent_result.context
    navigation_links = agent_result.navigation_links

    context_sections = []
    if doc_context:
        context_sections.append("=== REFERENCE DOCUMENTATION ===\n" + doc_context)
    if card_context:
        context_sections.append(
            "=== LIVE CARD DATA (PUBLIC, NON-SENSITIVE) ===\n" + card_context
        )
    if skill_context:
        context_sections.append("=== LIVE SKILL OUTPUTS ===\n" + skill_context)

    if context_sections:
        system_prompt = SYSTEM_PROMPT_BASE + "\n\n" + "\n\n".join(context_sections)
    else:
        system_prompt = SYSTEM_PROMPT_BASE

    client = OpenAI(base_url="https://api.deepseek.com", api_key=api_key)
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

    messages = [{"role": "system", "content": system_prompt}]

    for msg in payload.history[-6:]:
        role = msg.get("role") if isinstance(msg, dict) else None
        text = msg.get("text") if isinstance(msg, dict) else None
        if role in {"user", "assistant"} and isinstance(text, str) and text.strip():
            messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=2500,
            temperature=0.4,
            # deepseek-v4-flash defaults to thinking mode, whose hidden
            # reasoning tokens count toward max_tokens — long reasoning can
            # truncate the visible answer or leave it empty entirely, and it
            # roughly doubles response latency. This chatbot's answers are
            # grounded in the provided context, so thinking adds no value.
            extra_body={"thinking": {"type": "disabled"}},
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            print(
                "[chat] Warning: model returned empty content "
                f"(finish_reason={response.choices[0].finish_reason}); returning fallback."
            )
            return ChatResponse(
                answer="Sorry — I couldn't finish generating an answer. Please try asking again."
            )
        if navigation_links:
            link_lines = [
                "",
                "Quick actions in Upload Panel:",
            ]
            for link in navigation_links[:5]:
                title = link.get("title", "Open in Upload Panel")
                url = link.get("url", "")
                if title and url:
                    link_lines.append(f"- [{title}]({url})")
            answer = answer + "\n" + "\n".join(link_lines)
        return ChatResponse(answer=answer)
    except Exception as e:
        # Print safe diagnostics for server logs (no API key content).
        print(
            "[chat] DeepSeek request failed:",
            f"type={type(e).__name__}",
            f"status={getattr(e, 'status_code', None)}",
            f"message={str(e)}",
        )
        if getattr(e, "__cause__", None):
            print(f"[chat] DeepSeek cause type: {type(e.__cause__).__name__}")

        err_str = str(e)
        lowered = err_str.lower()
        status_code = getattr(e, "status_code", None)

        if "illegal header value" in lowered:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The chatbot is temporarily unavailable because the DeepSeek API key format is invalid "
                    "(it may contain whitespace/newline). Please contact the administrator."
                ),
            ) from e

        if isinstance(e, (APIConnectionError, APITimeoutError)) or "connection error" in lowered or "timed out" in lowered:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The chatbot is temporarily unavailable because the DeepSeek API "
                    "could not be reached. Please try again later or contact the administrator."
                ),
            ) from e

        if status_code == 402 or "insufficient_balance" in lowered or "402" in err_str:
            raise HTTPException(
                status_code=402,
                detail=(
                    "The chatbot is temporarily unavailable because the DeepSeek API credits "
                    "have been exhausted. Please contact the administrator."
                ),
            ) from e

        if status_code in {401, 403} or "authentication" in lowered or "permission" in lowered:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The chatbot is temporarily unavailable because the DeepSeek API "
                    "credentials are invalid or unauthorized. Please contact the administrator."
                ),
            ) from e

        if status_code == 429 or "rate limit" in lowered:
            raise HTTPException(
                status_code=503,
                detail=(
                    "The chatbot is temporarily unavailable because the DeepSeek API "
                    "rate limit was reached. Please try again later."
                ),
            ) from e

        raise HTTPException(status_code=502, detail=f"AI service error: {err_str}") from e
