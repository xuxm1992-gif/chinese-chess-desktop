"""Kimi web-search helpers.

Wraps Moonshot / Kimi's ``builtin_function.$web_search`` so callers can ask
the model a question and transparently receive an answer that is grounded in
real-time internet search results.

The public surface is intentionally tiny:

* :class:`KimiWebSearchClient` -- a stateful client that handles authentication,
  the tool-call loop, and exposes both raw ``run`` and convenience ``search``
  methods.
* :class:`SearchResult` -- a small dataclass returned by :meth:`search`.

See ``examples/`` and the project README for usage.
"""

from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    KimiAPIError,
    KimiWebSearchClient,
    SearchResult,
    search,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_SYSTEM_PROMPT",
    "KimiAPIError",
    "KimiWebSearchClient",
    "SearchResult",
    "search",
]
