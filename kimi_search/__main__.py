"""CLI entry point: ``python -m kimi_search "your question"``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    KimiAPIError,
    KimiWebSearchClient,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kimi_search",
        description=(
            "Ask Kimi a question with the built-in $web_search tool enabled. "
            "Reads the API key from --api-key, MOONSHOT_API_KEY, or "
            "KIMI_API_KEY (falling back to the project default)."
        ),
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="The question to ask. If omitted, the program reads from stdin.",
    )
    parser.add_argument("--api-key", dest="api_key", default=None)
    parser.add_argument(
        "--base-url",
        dest="base_url",
        default=None,
        help=f"Override the API base URL (default: {DEFAULT_BASE_URL}).",
    )
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--system",
        default=DEFAULT_SYSTEM_PROMPT,
        help="Override the system prompt.",
    )
    parser.add_argument(
        "--temperature", type=float, default=0.3,
    )
    parser.add_argument(
        "--max-iterations", type=int, default=8,
        help="Maximum tool-call rounds before aborting.",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true",
        help="Print the structured result as JSON instead of plain text.",
    )
    parser.add_argument(
        "--show-queries", action="store_true",
        help="Print the search queries Kimi issued before the final answer.",
    )
    return parser


def _read_query(argv_query: List[str]) -> str:
    if argv_query:
        return " ".join(argv_query).strip()
    if sys.stdin.isatty():
        sys.stderr.write("Enter your question and press Ctrl-D:\n")
    return sys.stdin.read().strip()


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    query = _read_query(args.query)
    if not query:
        parser.error("Empty query.")

    client = KimiWebSearchClient(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        max_tool_iterations=args.max_iterations,
    )

    try:
        result = client.search(
            query,
            system_prompt=args.system,
            temperature=args.temperature,
        )
    except KimiAPIError as exc:
        sys.stderr.write(f"Kimi API error: {exc}\n")
        return 2

    if args.as_json:
        json.dump(
            {
                "answer": result.answer,
                "search_ids": result.search_ids,
                "queries": result.queries,
                "search_tokens": result.search_tokens,
                "tool_calls": result.tool_calls,
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    if args.show_queries and (result.queries or result.search_ids):
        sys.stderr.write("[web_search activity]\n")
        for q in result.queries:
            sys.stderr.write(f"  query: {q}\n")
        for sid in result.search_ids:
            sys.stderr.write(f"  search_id: {sid}\n")
        if result.search_tokens:
            sys.stderr.write(f"  search_tokens: {result.search_tokens}\n")
        sys.stderr.write("\n")

    sys.stdout.write(result.answer + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
