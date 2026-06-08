"""Multi-turn conversation that re-uses web search across turns."""

from __future__ import annotations

from kimi_search import KimiWebSearchClient


def main() -> None:
    client = KimiWebSearchClient()
    history = []

    questions = [
        "今天 (今日) 北京的天气如何？请联网查询。",
        "那上海呢？也请联网查询并对比。",
    ]

    for q in questions:
        print(f"\n>>> {q}")
        result = client.search(q, history=history)
        print(result.answer)
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": result.answer})


if __name__ == "__main__":
    main()
