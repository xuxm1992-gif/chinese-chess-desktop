"""Minimal example: ask Kimi a question with web search enabled.

Run with:

    python examples/quickstart.py
"""

from __future__ import annotations

from kimi_search import KimiWebSearchClient


def main() -> None:
    client = KimiWebSearchClient()
    result = client.search(
        "请用中文搜索 Moonshot AI 的 Kimi K2 模型最新动态，并告诉我它的主要特性。"
    )
    print("==== Search queries Kimi issued ====")
    for q in result.queries:
        print(f"- {q}")
    print()
    print("==== Final answer ====")
    print(result.answer)


if __name__ == "__main__":
    main()
