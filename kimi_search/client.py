"""Client wrapper around Kimi's ``builtin_function.$web_search`` tool.

This module implements the tool-call loop described in the official Kimi
documentation:

    https://platform.kimi.com/docs/guide/use-web-search

Key behaviours:

* The ``$web_search`` tool is registered as ``type: "builtin_function"`` -- the
  search itself is performed *server-side* by Moonshot. Our client only has to
  echo the tool's arguments back as the tool result so that Moonshot knows the
  search has been "executed" on the client side.
* The chat is driven in a loop until ``finish_reason`` is no longer
  ``"tool_calls"``.
* Network errors and API errors are surfaced as :class:`KimiAPIError` so callers
  can distinguish them from generic exceptions.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.moonshot.cn/v1"
DEFAULT_MODEL = "moonshot-v1-auto"
DEFAULT_SYSTEM_PROMPT = (
    "You are Kimi, an AI assistant provided by Moonshot AI. You are good at "
    "Chinese and English conversations. When the user asks about facts, "
    "current events, or anything that benefits from up-to-date information, "
    "use the $web_search tool to look it up before answering. Cite the sources "
    "you used at the end of your reply."
)

# The fallback API key is the one supplied by the project owner. It is only
# used when no MOONSHOT_API_KEY / KIMI_API_KEY environment variable is set, so
# operators can override it without touching the source.
_FALLBACK_API_KEY = "sk-UK86xRFRcLSni9XLGuAbGWRyUjpuWLTTU1pkjpIRGA9ziRzf"


class KimiAPIError(RuntimeError):
    """Raised when the Kimi API returns an error or the response is malformed."""

    def __init__(self, message: str, status_code: Optional[int] = None,
                 payload: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass
class SearchResult:
    """High-level result of :meth:`KimiWebSearchClient.search`.

    Attributes
    ----------
    answer:
        Final assistant message content.
    search_ids:
        Server-side search IDs returned by Moonshot for each ``$web_search``
        call (Moonshot performs the search itself and only echoes back an ID).
    queries:
        Best-effort extraction of any human-readable query strings from tool
        arguments. Often empty for ``$web_search`` because Moonshot does not
        expose the query through the public tool-call payload.
    search_tokens:
        Tokens reported by Moonshot as used by the web search backend.
    tool_calls:
        Number of tool calls made during the loop.
    messages:
        Full conversation including assistant tool calls and tool responses.
    raw_responses:
        Raw chat-completion responses for debugging / advanced inspection.
    """

    answer: str
    search_ids: List[str] = field(default_factory=list)
    queries: List[str] = field(default_factory=list)
    search_tokens: int = 0
    tool_calls: int = 0
    messages: List[Dict[str, Any]] = field(default_factory=list)
    raw_responses: List[Dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.answer


_QUERY_LIKE_KEYS = (
    "query", "q", "queries", "search_query", "search_queries",
    "keyword", "keywords", "input", "text",
)


def _extract_queries(arguments: Dict[str, Any]) -> List[str]:
    """Best-effort extraction of human-readable query strings."""
    found: List[str] = []
    for key in _QUERY_LIKE_KEYS:
        value = arguments.get(key)
        if isinstance(value, str) and value.strip():
            found.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    found.append(item)
    if found:
        return found
    # Fall back: capture any direct string values in the arguments dict.
    for value in arguments.values():
        if isinstance(value, str) and value.strip():
            found.append(value)
    return found


def _resolve_api_key(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    for env_var in ("MOONSHOT_API_KEY", "KIMI_API_KEY"):
        value = os.environ.get(env_var)
        if value:
            return value
    return _FALLBACK_API_KEY


class KimiWebSearchClient:
    """Thin client that exposes Kimi's built-in web search.

    Parameters
    ----------
    api_key:
        Moonshot / Kimi API key. If omitted, falls back to ``MOONSHOT_API_KEY``
        or ``KIMI_API_KEY`` environment variables, then to the project-default
        key shipped with the repository.
    base_url:
        Base URL of the Kimi-compatible endpoint. Defaults to the Chinese
        Moonshot endpoint (``https://api.moonshot.cn/v1``). Use
        ``https://api.moonshot.ai/v1`` for the international endpoint, or set
        ``MOONSHOT_BASE_URL`` in the environment.
    model:
        Model name. ``moonshot-v1-auto`` (the default) automatically picks the
        cheapest context length large enough for the conversation. Other valid
        values include ``moonshot-v1-8k``/``32k``/``128k``, ``kimi-k2.5``, and
        ``kimi-k2.6``.
    timeout:
        Per-request timeout in seconds.
    max_tool_iterations:
        Safety cap on the number of tool-call rounds. The search loop exits
        once the model produces a final answer, but this prevents runaway loops
        if something misbehaves.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
        max_tool_iterations: int = 8,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = _resolve_api_key(api_key)
        self.base_url = (
            base_url
            or os.environ.get("MOONSHOT_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_tool_iterations = max_tool_iterations
        self._session = session or requests.Session()

    # ------------------------------------------------------------------ utils

    @property
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def web_search_tool() -> Dict[str, Any]:
        """Return the tool spec for ``builtin_function.$web_search``."""
        return {
            "type": "builtin_function",
            "function": {"name": "$web_search"},
        }

    @staticmethod
    def _search_impl(arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Mock client-side handler for ``$web_search``.

        Per the Kimi documentation, the actual search is executed server-side
        by Moonshot. Clients only need to echo the arguments back as the tool
        result, signalling that the call has been "handled" locally.
        """
        return arguments

    # ------------------------------------------------------------------ HTTP

    def _post_chat(self, messages: List[Dict[str, Any]],
                   temperature: float, tools: List[Dict[str, Any]],
                   extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
        }
        if extra:
            payload.update(extra)

        try:
            response = self._session.post(
                url, headers=self._headers, json=payload, timeout=self.timeout,
            )
        except requests.RequestException as exc:  # network-level failure
            raise KimiAPIError(f"Network error talking to Kimi: {exc}") from exc

        if response.status_code >= 400:
            try:
                err_payload = response.json()
            except ValueError:
                err_payload = response.text
            raise KimiAPIError(
                f"Kimi API returned HTTP {response.status_code}: {err_payload}",
                status_code=response.status_code,
                payload=err_payload,
            )

        try:
            return response.json()
        except ValueError as exc:
            raise KimiAPIError(
                f"Kimi API returned non-JSON body: {response.text!r}",
            ) from exc

    # ----------------------------------------------------------------- core

    def run(
        self,
        messages: List[Dict[str, Any]],
        *,
        temperature: float = 0.3,
        extra_tools: Optional[Iterable[Dict[str, Any]]] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> SearchResult:
        """Drive the chat / tool-call loop and return the final answer.

        ``messages`` is mutated in place to contain the full conversation,
        including assistant tool-calls and tool responses, after the loop
        completes. The same list is also returned via :class:`SearchResult`
        for callers that prefer immutability.
        """
        tools: List[Dict[str, Any]] = [self.web_search_tool()]
        if extra_tools:
            tools.extend(extra_tools)

        queries: List[str] = []
        search_ids: List[str] = []
        search_tokens = 0
        raw_responses: List[Dict[str, Any]] = []
        tool_calls_total = 0
        final_message: Dict[str, Any] = {}

        for iteration in range(self.max_tool_iterations + 1):
            data = self._post_chat(
                messages, temperature=temperature, tools=tools,
                extra=extra_payload,
            )
            raw_responses.append(data)

            try:
                choice = data["choices"][0]
            except (KeyError, IndexError, TypeError) as exc:
                raise KimiAPIError(
                    f"Unexpected Kimi response shape: {data!r}",
                    payload=data,
                ) from exc

            message = choice.get("message", {}) or {}
            finish_reason = choice.get("finish_reason")

            if finish_reason == "tool_calls":
                messages.append(message)
                for tool_call in message.get("tool_calls") or []:
                    tool_calls_total += 1
                    fn = tool_call.get("function", {}) or {}
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments") or "{}"
                    try:
                        arguments = json.loads(raw_args)
                    except json.JSONDecodeError:
                        arguments = {"_raw": raw_args}

                    if name == "$web_search":
                        if isinstance(arguments, dict):
                            queries.extend(_extract_queries(arguments))
                            sr = arguments.get("search_result")
                            if isinstance(sr, dict):
                                sid = sr.get("search_id")
                                if isinstance(sid, str):
                                    search_ids.append(sid)
                            usage = arguments.get("usage")
                            if isinstance(usage, dict):
                                tok = usage.get("total_tokens")
                                if isinstance(tok, int):
                                    search_tokens += tok
                        tool_result: Any = self._search_impl(
                            arguments if isinstance(arguments, dict) else {}
                        )
                    else:
                        tool_result = {
                            "error": f"Unsupported tool '{name}'",
                        }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.get("id"),
                        "name": name,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    })
                continue

            final_message = message
            messages.append(message)
            break
        else:
            raise KimiAPIError(
                "Exceeded max_tool_iterations while waiting for a final answer."
            )

        answer = (final_message.get("content") or "").strip()
        return SearchResult(
            answer=answer,
            search_ids=search_ids,
            queries=queries,
            search_tokens=search_tokens,
            messages=messages,
            tool_calls=tool_calls_total,
            raw_responses=raw_responses,
        )

    # ------------------------------------------------------------- helpers

    def search(
        self,
        query: str,
        *,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        temperature: float = 0.3,
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> SearchResult:
        """Convenience wrapper: build a fresh conversation and run a query."""
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": query})
        return self.run(messages, temperature=temperature)


def search(query: str, **kwargs: Any) -> SearchResult:
    """Module-level convenience: ``kimi_search.search('...')``."""
    client_kwargs = {
        k: kwargs.pop(k)
        for k in ("api_key", "base_url", "model", "timeout",
                  "max_tool_iterations")
        if k in kwargs
    }
    client = KimiWebSearchClient(**client_kwargs)
    return client.search(query, **kwargs)


# Surface the module-level convenience under ``kimi_search.search`` too.
__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_SYSTEM_PROMPT",
    "KimiAPIError",
    "KimiWebSearchClient",
    "SearchResult",
    "search",
]