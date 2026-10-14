"""
chat_tools.py — the tools the model may call while answering a question.

Every way of gathering context lives here as a *tool*: a JSON schema the model
sees, plus a handler that runs it. chat.py owns the conversation loop and calls
``execute_tool`` when the model asks for one.

Why tools instead of keyword triggers
-------------------------------------
These lookups used to be gated by hardcoded keyword lists ("does the question
contain 'card' or 'dataset'?"). That misfires constantly: a question phrased as
"what's in the Atlas about salmon?" matches nothing, and a question in any
language other than English matches nothing at all. The model decides far more
reliably than a substring check, so the decision is now its own — the keyword
lists are gone.

Handlers always return a string (never raise): a tool failing should degrade
the answer, not break the request. Failures come back as text the model can
read and react to, so it can say "the live catalog is unreachable" instead of
inventing an answer.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from chat_agent import build_default_chat_agent
from manual_knowledge import read_active, search_manual

_LAST_MANUAL_POINTER = None

_CHAT_AGENT = build_default_chat_agent()


# ---------------------------------------------------------------------------
# Per-request state
# ---------------------------------------------------------------------------
@dataclass
class ToolContext:
    """Side outputs collected while running tools for one request.

    Instantiated per request rather than kept module-level: FastAPI runs sync
    endpoints in a threadpool, so shared mutable state would race between
    concurrent questions.
    """

    navigation_links: list[dict] = field(default_factory=list)
    manual_sources: list[dict] = field(default_factory=list)
    manual_pointer: dict | None = None
    manual_lookup_done: bool = False
    visual_lookup_done: bool = False
    visual_result: str = ''
    visual_status: dict = field(default_factory=dict)
    user_question: str = ''
    last_manual_sources: list[dict] = field(default_factory=list)
    generation_usage: list[dict] = field(default_factory=list)

    def add_manual_sources(self, sources):
        for source in sources:
            existing = next((item for item in self.manual_sources if
                (item['section_id'], item['version']) == (source['section_id'], source['version'])), None)
            if existing:
                for field in ['block_ids', 'step_ids', 'image_ids']:
                    existing[field] = list(dict.fromkeys(existing.get(field, []) + source.get(field, [])))
            else:
                self.manual_sources.append(dict(source))

    def add_navigation_links(self, links: list[dict] | None) -> None:
        seen = {link.get("url") for link in self.navigation_links}
        for link in links or []:
            url = link.get("url")
            if url and url not in seen:
                self.navigation_links.append(link)
                seen.add(url)


def _atlas_base_url() -> str:
    return os.environ.get("ATLAS_API_URL", "").strip().rstrip("/")


# ---------------------------------------------------------------------------
# Tool: documentation search (Pinecone, hosted embeddings)
# ---------------------------------------------------------------------------
def get_pinecone_index():
    """Return a Pinecone Index object. Raises RuntimeError if not configured."""
    api_key = os.environ.get("PINECONE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PINECONE_API_KEY environment variable is not set.")

    index_name = (os.environ.get("PINECONE_INDEX") or "living-atlas-docs-hosted")

    from pinecone import Pinecone

    pc = Pinecone(api_key=api_key)
    host = os.environ.get('PINECONE_INDEX_HOST', '').strip()
    return pc.Index(host=host) if host else pc.Index(index_name)


def search_documentation(query: str, top_k: int = 3, ctx: ToolContext | None = None) -> str:
    """Read only a validated version of the app manual; never the legacy docs namespace."""
    global _LAST_MANUAL_POINTER
    ctx = ctx or ToolContext()
    ctx.last_manual_sources = []
    query = (query or "").strip()
    if not query:
        return "No search query was provided."

    try:
        index = get_pinecone_index()
        if not ctx.manual_lookup_done:
            try:
                ctx.manual_pointer = read_active(index)
                _LAST_MANUAL_POINTER = ctx.manual_pointer
            except Exception:
                ctx.manual_pointer = _LAST_MANUAL_POINTER
            ctx.manual_lookup_done = True
        if not ctx.manual_pointer:
            return "The app user manual has not been activated yet. No legacy documentation was used. Do not guess feature instructions."
        passages, sources = search_manual(index, query, ctx.manual_pointer, top_k)
        ctx.last_manual_sources = sources
        ctx.add_manual_sources(sources)
        if not passages:
            return "No app manual passages matched. Say the manual does not provide enough information."
        return "\n\n---\n\n".join(passages)
    except Exception as exc:
        print(f"[chat-tools] Documentation search failed: {exc}")
        return "The documentation index is currently unreachable."


# ---------------------------------------------------------------------------
# Tool: live card search
# ---------------------------------------------------------------------------
def search_cards(query: str) -> str:
    """Fetch matching public cards from the Living Atlas backend."""
    base = _atlas_base_url()
    if not base:
        return (
            "Live card data is not available: this deployment has no link to the "
            "Living Atlas backend (ATLAS_API_URL is unset)."
        )

    try:
        resp = requests.get(
            f"{base}/cards/summary",
            # force=1 skips the backend's own keyword heuristic: the decision to
            # look up cards has already been made by calling this tool.
            params={"q": (query or "").strip(), "force": 1},
            timeout=8,
        )
        resp.raise_for_status()
        context = resp.json().get("context", "")
        if not isinstance(context, str) or not context:
            return "No cards matched that query."
        return context
    except Exception as exc:
        print(f"[chat-tools] Card search failed: {exc}")
        return "The card database is currently unreachable."


def inspect_manual_visuals(query: str, ctx: ToolContext, state: str = 'default') -> str:
    """One bounded visual inspection per request, using its pinned manual version."""
    if ctx.visual_lookup_done:
        return ctx.visual_result
    ctx.visual_lookup_done = True
    passages = search_documentation(query, ctx=ctx)
    if not ctx.manual_pointer or not ctx.last_manual_sources:
        ctx.visual_status = {'status': 'unavailable', 'reason': 'manual-unavailable'}
        ctx.visual_result = passages
        return passages
    from manual_visuals import describe_visuals
    answer, ctx.visual_status = describe_visuals(ctx.user_question or query, passages, ctx.last_manual_sources, ctx.manual_pointer, state)
    if answer:
        ids = set(ctx.visual_status['image_ids'])
        for source in ctx.manual_sources:
            source['inspected_image_ids'] = [value for value in source.get('image_ids', []) if value in ids]
        ctx.visual_result = '=== Verified manual visual evidence ===\n' + answer
    else:
        ctx.visual_result = ('Manual screenshots could not be inspected. Explain only what the retrieved text supports; '
            'say that image details could not be checked, and do not guess button positions or icons.\n' + passages)
    return ctx.visual_result


# ---------------------------------------------------------------------------
# Live Atlas facts (counts, taxonomy, ArcGIS inventory)
# ---------------------------------------------------------------------------
# Not a tool: this block is small, applies to a wide range of questions, and is
# the only defence against the model guessing at counts. It is injected into
# every request as system state and cached so that costs one HTTP call every
# couple of minutes.
# ---------------------------------------------------------------------------
_ATLAS_FACTS_TTL_SECONDS = 120
_atlas_facts_cache: tuple[float, str] | None = None


def get_atlas_facts() -> str:
    """Fetch the live Atlas fact block from the backend. Fail silently."""
    global _atlas_facts_cache

    base = _atlas_base_url()
    if not base:
        return ""

    now = time.time()
    if _atlas_facts_cache and now - _atlas_facts_cache[0] < _ATLAS_FACTS_TTL_SECONDS:
        return _atlas_facts_cache[1]

    try:
        resp = requests.get(f"{base}/atlas/summary", timeout=8)
        resp.raise_for_status()
        context = resp.json().get("context", "")
        if not isinstance(context, str):
            return ""
        _atlas_facts_cache = (now, context)
        return context
    except Exception as exc:
        print(f"[chat-tools] Atlas facts warning: {exc}")
        # Serve a stale block rather than nothing if we ever had one.
        return _atlas_facts_cache[1] if _atlas_facts_cache else ""


# ---------------------------------------------------------------------------
# Tool: live ArcGIS REST catalog
# ---------------------------------------------------------------------------
def browse_arcgis_catalog(query: str, ctx: ToolContext) -> str:
    """Run the live ArcGIS catalog skill and collect its navigation links."""
    query = (query or "").strip()
    if not query:
        return "No search query was provided."

    result = _CHAT_AGENT.run_skill("arcgis-service-catalog", query)
    if result is None:
        return "The ArcGIS catalog skill is not available."

    ctx.add_navigation_links(result.navigation_links)

    if result.warning:
        print(f"[chat-tools] {result.warning}")
        return (
            f"The live ArcGIS catalog could not be reached ({result.warning}). "
            "Do not claim live catalog data was retrieved."
        )
    return result.context_block or "The live catalog returned no matching entries."


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any], ToolContext], str]


TOOLS: list[Tool] = [
    Tool(
        name='inspect_manual_visuals',
        description=('Inspect the versioned user manual screenshots together with retrieved text. Use only when '
            'the user needs visual evidence about an icon, button position, interface layout, or gallery state. '
            'Do not call for text-only instructions, live data, or topics the manual does not cover. '
            'Supply English feature keywords and optionally a gallery state. At most one visual inspection per question.'),
        parameters={'type': 'object', 'properties': {
            'query': {'type': 'string', 'description': 'English keywords identifying the feature/control to inspect.'},
            'state': {'type': 'string', 'enum': ['default', 'slideshow', 'slideshow-next']}}, 'required': ['query']},
        handler=lambda args, ctx: inspect_manual_visuals(args.get('query', ''), ctx, args.get('state', 'default')),
    ),
    Tool(
        name="search_documentation",
        description=(
            "Search the Living Atlas feature documentation. Use this for how-to and "
            "conceptual questions: how a panel or control works, where to find "
            "something in the interface, what a term or ArcGIS folder abbreviation "
            "means. Phrase the query as English keywords describing the feature, "
            "regardless of the language the user asked in. The documentation "
            "deliberately contains no counts or exhaustive lists — those are in the "
            "live Atlas facts already provided to you."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "English keywords describing the feature or concept to look "
                        "up, e.g. 'basemap panel switch style' or 'create card "
                        "polygon drawing'."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=lambda args, ctx: search_documentation(args.get("query", ""), ctx=ctx),
    ),
    Tool(
        name="search_cards",
        description=(
            "Search the cards currently in the Living Atlas database and return "
            "matching public ones with their category, organization, tags, location, "
            "and description. Use this whenever the user asks about actual content in "
            "the Atlas — datasets on a topic, cards from an organization, what exists "
            "near a place, or anything requiring real records rather than an "
            "explanation of how the app works. Returns only public, non-sensitive "
            "fields; it can never reveal who created a card."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "English keywords describing the cards to find, e.g. 'salmon "
                        "habitat', 'Columbia River water quality', or a specific "
                        "organization name. Pass an empty string to list recent cards."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=lambda args, ctx: search_cards(args.get("query", "")),
    ),
    Tool(
        name="browse_arcgis_catalog",
        description=(
            "Look up folders, services, and layers directly on the live state ArcGIS "
            "REST server. Use this when the user asks what a specific folder or "
            "service actually contains right now, or wants to find and open a layer. "
            "This reads the agency's server live, so it is authoritative for what "
            "exists today. It also produces quick-action links the user can click to "
            "open a service in the Upload Panel."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to look for. Include the folder name when the user "
                        "named one, phrased naturally so the folder is recognised, "
                        "e.g. 'services in the AQ folder' or 'smoke forecast layer'."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=lambda args, ctx: browse_arcgis_catalog(args.get("query", ""), ctx),
    ),
]

_TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def tool_schemas() -> list[dict]:
    """The `tools` payload for an OpenAI-compatible chat completion request."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in TOOLS
    ]


def execute_tool(name: str, args: dict[str, Any], ctx: ToolContext) -> str:
    """Run one tool by name. Never raises — errors come back as readable text."""
    tool = _TOOLS_BY_NAME.get(name)
    if tool is None:
        return f"Unknown tool '{name}'."
    try:
        return tool.handler(args, ctx)
    except Exception as exc:
        print(f"[chat-tools] Tool '{name}' raised: {type(exc).__name__}: {exc}")
        return f"The '{name}' tool failed to run."


def gather_all_context(question: str, ctx: ToolContext) -> str:
    """Run every tool eagerly against the raw question.

    The fallback for a model that cannot do tool calling: recreates the old
    "gather everything up front" behaviour so a model swap can never take the
    chatbot down.
    """
    blocks = []
    for tool in TOOLS:
        # An eager text fallback cannot determine visual intent. Never charge for
        # image calls merely because the primary model rejected tool calling.
        if tool.name == 'inspect_manual_visuals':
            continue
        output = execute_tool(tool.name, {"query": question}, ctx)
        if output:
            blocks.append(f"=== {tool.name} ===\n{output}")
    return "\n\n".join(blocks)
