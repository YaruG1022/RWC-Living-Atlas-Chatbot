"""
chat.py  —  /chat/ask endpoint

The model answers by calling tools (chat_tools.py) rather than being handed
everything up front:

  search_documentation   Pinecone search over the published app manual
  inspect_manual_visuals verified manual screenshots + a separate vision model
  search_cards           live public card records from the Atlas backend
  browse_arcgis_catalog  live state ArcGIS REST catalog + quick-action links

Two blocks are still injected unconditionally, because they are small and the
model cannot know it needs them: a first-pass documentation search on the raw
question (grounding, so an answer is never ungrounded even if no tool is
called), and the live Atlas fact block (counts and vocabulary — the only thing
stopping the model guessing at numbers).

Generation: DeepSeek API (OpenAI-compatible), set DEEPSEEK_API.
"""

import json
import os
import time
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from openai import APIConnectionError, APITimeoutError, OpenAI

from chat_tools import (
    ToolContext,
    execute_tool,
    gather_all_context,
    get_atlas_facts,
    search_documentation,
    tool_schemas,
)

chat_router = APIRouter(prefix="/chat", tags=["chat"])

# How many times the model may call tools before it must answer. Three covers
# the deepest realistic chain (look up a folder, then a service inside it, then
# check the docs for what it means) without letting a confused model loop.
MAX_TOOL_ROUNDS = 3

# ---------------------------------------------------------------------------
# System prompt: gives the model context about the Living Atlas project
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_BASE = """You are the RWC Living Atlas Helper, an AI assistant for the
Rivers, Watersheds, Communities (RWC) Living Atlas web application — an interactive map
that showcases environmental datasets, GIS layers, and research resources for
the Pacific Northwest (Idaho, Oregon, and Washington).

Be concise, friendly, and factual.
Do not answer questions unrelated to the Living Atlas or environmental/GIS topics.

TOOLS: You have tools for searching the documentation, the live card database, and the
live ArcGIS catalog. Call them whenever the answer depends on information you were not
already given — do not guess, and do not answer from memory about what the Atlas
contains. Call a tool even when the question is not in English; pass English keywords
as the query and answer in the user's own language. If a tool reports that a service is
unreachable, say so plainly rather than inventing an answer.

VISUAL QUESTIONS: For icon appearance, button positions, layout or expanded gallery
states, call inspect_manual_visuals after retrieving the relevant chapter. Use its
verified screenshots and text. For text-only questions, do not call the visual tool.
Screenshots depict manual examples, not current cards or real users. If images cannot
be inspected, say so and use only sourced text; never guess an unseen visual detail.

If, after using the tools, you still cannot answer, say so honestly.

FEATURE INSTRUCTIONS: The published app user manual is the only feature authority.
Use the retrieved passages, including prerequisites, complete steps and cautions.
If the passages do not explain the requested action, say you cannot confirm it from
the manual. Do not invent steps from historical documentation or general memory.
When using a manual chapter, cite its exact ID as [manual:chapter-id]. These markers
are resolved by the service into verified links. Never compose user-manual URLs.
Do not cite a chapter that was not returned by search. Live tools remain the source
for current records and inventory, not the sample values in the manual.

For any countable or enumerable fact — how many cards or ArcGIS services exist, which
categories or tags are available, which folders a state publishes — use LIVE ATLAS FACTS
below. The reference documentation deliberately omits these numbers and lists because
they change as the Atlas grows; never estimate them from the documentation.

When you used the live ArcGIS catalog, append a final section titled exactly:
Sources
Then include 1-4 bullet points in this format:
- [ArcGIS live catalog] <source snippet>
Use the structured source snippets the tool returned.

PRIVACY (strict): The card data you receive contains only public, non-sensitive fields.
It never includes usernames, emails, passwords, or any account/identity information.
Never reveal, guess, or discuss who created or uploaded a card, and never disclose any
user's username, email, password, or contact details. If asked who made a card or for any
user's personal or login information, politely decline and explain that contributor
identities and account data are private and not accessible to this assistant.

⚠️ This feature is under development. Always verify critical information with the original data source.
"""


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str
    history: list[dict[str, Any]] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    # Machine-readable evaluation data; the widget displays only answer/sources.
    metrics: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------
def build_system_prompt(question: str, ctx: ToolContext | None = None) -> str:
    """Base prompt plus the two unconditionally-injected context blocks."""
    sections = []

    doc_context = search_documentation(question, ctx=ctx)
    if doc_context:
        sections.append("=== REFERENCE DOCUMENTATION (first-pass search) ===\n" + doc_context)

    atlas_facts = get_atlas_facts()
    if atlas_facts:
        sections.append("=== LIVE ATLAS FACTS ===\n" + atlas_facts)

    if not sections:
        return SYSTEM_PROMPT_BASE
    return SYSTEM_PROMPT_BASE + "\n\n" + "\n\n".join(sections)


def build_messages(payload: ChatRequest, question: str, ctx: ToolContext | None = None) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(question, ctx)}
    ]

    for msg in payload.history[-6:]:
        role = msg.get("role") if isinstance(msg, dict) else None
        text = msg.get("text") if isinstance(msg, dict) else None
        if role in {"user", "assistant"} and isinstance(text, str) and text.strip():
            messages.append({"role": role, "content": text})

    messages.append({"role": "user", "content": question})
    return messages


def resolve_manual_sources(answer: str, ctx: ToolContext):
    import re
    used = set(re.findall(r'\[manual:([a-z0-9-]+)\]', answer))
    # Even if the provider omits markers, expose retrieved references with precise
    # block/version metadata. The UI labels these as manual references, not proof of every claim.
    sources = [source for source in ctx.manual_sources if not used or source['section_id'] in used]
    answer = re.sub(r'\[manual:[^\]]*\]', '', answer).strip()
    # Model-produced manual links never survive; the only links are the structured sources.
    answer = re.sub(r'\[[^\]]*\]\([^\s)]*\/user-manual[^)]*\)', '', answer)
    answer = re.sub(r'https?://[^\s<>]*\/user-manual[^\s<>]*', '', answer)
    return answer, sources


def append_navigation_links(answer: str, navigation_links: list[dict]) -> str:
    if not navigation_links:
        return answer

    link_lines = ["", "Quick actions in Upload Panel:"]
    for link in navigation_links[:5]:
        title = link.get("title", "Open in Upload Panel")
        url = link.get("url", "")
        if title and url:
            link_lines.append(f"- [{title}]({url})")
    return answer + "\n" + "\n".join(link_lines)


# ---------------------------------------------------------------------------
# Tool-calling loop
# ---------------------------------------------------------------------------
def _completion(client: OpenAI, model: str, messages: list, with_tools: bool, force_visual=False):
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": 2500,
        "temperature": 0.4,
        # deepseek-v4-flash defaults to thinking mode, whose hidden reasoning
        # tokens count toward max_tokens — long reasoning can truncate the
        # visible answer or leave it empty entirely, and it roughly doubles
        # response latency. Answers here are grounded in retrieved context, so
        # thinking adds no value.
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    if with_tools:
        kwargs["tools"] = tool_schemas()
        kwargs["tool_choice"] = ({'type': 'function', 'function': {'name': 'inspect_manual_visuals'}} if force_visual else 'auto')
    return client.chat.completions.create(**kwargs)


def _parse_tool_args(raw: str | None) -> dict[str, Any]:
    """Tool arguments arrive as a JSON string the model wrote; it can be junk."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        print(f"[chat] Ignoring malformed tool arguments: {raw[:200]}")
        return {}


def run_tool_loop(client: OpenAI, model: str, messages: list, ctx: ToolContext):
    """Let the model call tools until it produces an answer.

    Returns the final completion. Tools are withdrawn on the last round so the
    model has no choice but to answer with what it has gathered.
    """
    for round_index in range(MAX_TOOL_ROUNDS):
        # Real smoke testing found direct answers to explicit icon/position questions
        # despite the visual instruction. A narrow guard forces their first tool;
        # text questions and other phrasing keep the existing model routing.
        force_visual = round_index == 0 and requires_visual_evidence(ctx.user_question)
        response = _completion(client, model, messages, with_tools=True, force_visual=force_visual)
        record_usage(response, model, ctx)
        message = response.choices[0].message

        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            return response

        messages.append(message.model_dump(exclude_none=True))

        for call in tool_calls:
            name = call.function.name
            args = _parse_tool_args(call.function.arguments)
            print(f"[chat] round {round_index + 1}: {name}({args})")
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": execute_tool(name, args, ctx),
            })

    # Budget spent and the model still wants tools — make it answer.
    print(f"[chat] Tool budget of {MAX_TOOL_ROUNDS} rounds exhausted; forcing an answer.")
    response = _completion(client, model, messages, with_tools=False)
    record_usage(response, model, ctx)
    return response


def record_usage(response, model, ctx):
    usage = getattr(response, 'usage', None)
    ctx.generation_usage.append({'model': model,
        'prompt_tokens': getattr(usage, 'prompt_tokens', None),
        'completion_tokens': getattr(usage, 'completion_tokens', None)})


def requires_visual_evidence(question):
    return bool(re.search(r'\b(?:icons?|layout|look like)\b|\bwhere\b.{0,80}\b(?:button|dropdown|control|toolbar)\b|图标|布局|按钮.{0,20}(?:位置|在哪|哪里)|(?:哪里|哪儿|在哪).{0,20}(?:按钮|控件)', question, re.IGNORECASE))


def _looks_like_missing_tool_support(exc: Exception) -> bool:
    """Whether an error suggests the configured model cannot do tool calling."""
    status = getattr(exc, "status_code", None)
    if status not in {400, 404, 422}:
        return False
    lowered = str(exc).lower()
    return "tool" in lowered or "function" in lowered


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

    client = OpenAI(base_url="https://api.deepseek.com", api_key=api_key)
    started = time.perf_counter()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

    ctx = ToolContext()
    ctx.user_question = question
    messages = build_messages(payload, question, ctx)

    try:
        try:
            response = run_tool_loop(client, model, messages, ctx)
        except Exception as exc:
            if not _looks_like_missing_tool_support(exc):
                raise
            # The configured model cannot call tools. Rather than fail, gather
            # every tool's output up front and answer in one shot, so swapping
            # DEEPSEEK_MODEL can never take the chatbot down.
            print(f"[chat] Model '{model}' rejected tools ({exc}); falling back to eager context.")
            fallback = build_messages(payload, question, ctx)
            fallback[0]["content"] += (
                "\n\n=== PRE-GATHERED CONTEXT (tools unavailable) ===\n"
                + gather_all_context(question, ctx)
            )
            response = _completion(client, model, fallback, with_tools=False)
            record_usage(response, model, ctx)

        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            print(
                "[chat] Warning: model returned empty content "
                f"(finish_reason={response.choices[0].finish_reason}); returning fallback."
            )
            return ChatResponse(
                answer="Sorry — I couldn't finish generating an answer. Please try asking again."
            )
        answer, sources = resolve_manual_sources(answer, ctx)
        return ChatResponse(answer=append_navigation_links(answer, ctx.navigation_links), sources=sources,
            metrics={'duration_ms': round((time.perf_counter() - started) * 1000),
                'generation': ctx.generation_usage, 'vision': ctx.visual_status or {'status': 'not-requested'},
                'manual_version': (ctx.manual_pointer or {}).get('version')})

    except HTTPException:
        raise
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
