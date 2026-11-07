"""A tiny tool-calling agent over the index.

The model chooses between two tools (search, match). If the local model does not
emit a tool call — 7B models are erratic at this — we fall back to a plain
search so the endpoint still answers instead of erroring.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

MAX_STEPS = 3

SYSTEM = (
    "You are JobFit, a job-search assistant for one user's local index of tech "
    "job postings. Use the tools to answer. Prefer search_jobs for questions "
    "about what roles exist and match_resume when the user supplies a resume. "
    "Answer in at most 6 short lines and cite company names."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_jobs",
            "description": "Semantic search over job postings in the local index.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "what to look for"},
                    "k": {"type": "integer", "description": "how many results, 1-20"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_resume",
            "description": "Rank postings against a resume the user supplied.",
            "parameters": {
                "type": "object",
                "properties": {
                    "k": {"type": "integer", "description": "how many results, 1-20"}
                },
                "required": [],
            },
        },
    },
]


class AgentResult(dict):
    """dict with .model_dump() so FastAPI can serialise it either way."""

    def model_dump(self) -> dict[str, Any]:  # duck typing for pydantic
        return dict(self)


def run(
    question: str,
    *,
    ollama_url: str,
    model: str,
    tools_impl: dict[str, Any],
    resume_text: str | None = None,
) -> AgentResult:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": question},
    ]
    trace: list[dict[str, Any]] = []
    answered_by = "model"

    with httpx.Client(timeout=180) as client:
        for _ in range(MAX_STEPS):
            try:
                resp = client.post(
                    f"{ollama_url}/api/chat",
                    json={"model": model, "messages": messages, "tools": TOOLS, "stream": False},
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                return AgentResult(
                    answer=f"local model unavailable ({exc}); no tool was called",
                    trace=trace,
                    answered_by="error",
                )
            message = resp.json().get("message", {})
            calls = message.get("tool_calls") or []
            if not calls:
                # Some local models answer with the tool call as plain JSON text
                # instead of native tool_calls. Same intent — act on it, don't
                # hand the user a JSON blob.
                coerced = _coerce_text_call(message.get("content", ""))
                if coerced is None:
                    return AgentResult(
                        answer=message.get("content", ""), trace=trace, answered_by=answered_by
                    )
                trace.append({"coerced_from_text": True})
                calls = [coerced]

            messages.append(message)
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                impl = tools_impl.get(name)
                if impl is None:
                    result: Any = {"error": f"unknown tool {name}"}
                else:
                    result = impl(args)
                trace.append({"tool": name, "args": args, "n_results": _count(result)})
                messages.append({"role": "tool", "name": name, "content": _to_json(result)[:6000]})

    # Tool budget spent without a final answer: answer from the last result.
    last = trace[-1]["tool"] if trace else "none"
    answered_by = "fallback"
    fallback = tools_impl["search_jobs"]({"query": question, "k": 5})
    return AgentResult(
        answer=_summarise(fallback),
        trace=trace,
        answered_by=f"{answered_by} (stopped after {MAX_STEPS} steps, last tool: {last})",
    )


def _to_json(value: Any) -> str:
    """Tool results carry dates and Decimals from Postgres; JSON needs strings."""

    def default(obj: Any) -> str:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)

    return json.dumps(value, default=default)


def _coerce_text_call(content: str) -> dict[str, Any] | None:
    """Parse a tool call that arrived as text, e.g. {"name": ..., "arguments": ...}."""
    text = (content or "").strip()
    if not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    name = payload.get("name") or payload.get("tool") or payload.get("function")
    args = payload.get("arguments") or payload.get("parameters") or {}
    if not isinstance(name, str):
        return None
    return {"function": {"name": name, "arguments": args}}


def _count(result: Any) -> int:
    if isinstance(result, list):
        return len(result)
    if isinstance(result, dict):
        return len(result.get("results", []))
    return 0


def _summarise(results: Any) -> str:
    items = results if isinstance(results, list) else results.get("results", [])
    if not items:
        return "No postings matched that."
    lines = [f"{i}. {r['title']} — {r['company']}" for i, r in enumerate(items[:5], 1)]
    return "Closest postings:\n" + "\n".join(lines)
