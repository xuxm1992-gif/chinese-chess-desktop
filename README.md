# chinese-chess-desktop

This repository currently hosts a small Python module, `kimi_search`, that
implements **Kimi-powered web search** using Moonshot's `builtin_function.$web_search`
tool. It will be wired into the larger Chinese-chess desktop app for
features such as opening-database lookups and rules / commentary search.

Reference docs:

- 中文：<https://platform.moonshot.cn/docs/guide/use-web-search>
- English: <https://platform.kimi.com/docs/guide/use-web-search>
- **踩坑指南 / Agent skill 文档**：[`docs/kimi-web-search-skill.md`](docs/kimi-web-search-skill.md)
  — 把另一个 AI Agent 反复写挂的 6 个坑（endpoint/model 错配、`builtin_function` 写法、tool-call 循环、arguments 回显约定等）整理成一份可直接喂给 Agent 的实战教学。

## Features

- ✅ Drives Kimi's official `builtin_function.$web_search` tool — no third-party
  search backend required; Moonshot performs the actual search.
- ✅ Handles the full `tool_calls` loop, including assistant tool-call messages
  and tool-result echoing, exactly as required by the docs.
- ✅ Exposes server-side `search_id` and `search_tokens` for observability.
- ✅ CLI entry point (`python -m kimi_search "..."`) and a tiny Python API.
- ✅ API key resolution from `--api-key` → `MOONSHOT_API_KEY` →
  `KIMI_API_KEY` → built-in default. Override the endpoint with
  `MOONSHOT_BASE_URL`.
- ✅ Network errors and API errors are surfaced as `KimiAPIError`.
- ✅ Multi-turn conversations supported via `history=[...]`.
- ✅ Offline unit tests covering the tool-call loop, error handling, and
  iteration cap.

## Install

```bash
pip install -r requirements.txt
```

Python 3.9+ is required (uses `dataclasses` and PEP 604-compatible typing).

## Configuration

The provided API key
(`sk-UK86xRFRcLSni9XLGuAbGWRyUjpuWLTTU1pkjpIRGA9ziRzf`)
is hard-coded as a fallback so the package works out of the box. **For real
deployments, override it with an environment variable:**

```bash
export MOONSHOT_API_KEY=sk-...
# Optional — defaults to the .cn endpoint that matches the bundled key.
export MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
```

Use `https://api.moonshot.ai/v1` for the international endpoint.

## CLI usage

```bash
# Plain text answer
python -m kimi_search "今天上海天气怎么样？请联网搜索后回答。"

# Show search activity on stderr alongside the answer
python -m kimi_search --show-queries "Moonshot AI 最近一周有什么新闻？"

# Structured JSON output
python -m kimi_search --json "Kimi K2 模型有哪些主要特点？"

# Override the model
python -m kimi_search --model kimi-k2.6 "..."
```

Live example output (truncated):

```text
$ python -m kimi_search --json "今日 (2026-06-08) 上海天气如何？"
{
  "answer": "根据搜索结果，2026年6月8日上海的天气情况如下：...",
  "search_ids": ["f0bddc816a26642d680f160001ee8c69"],
  "queries": [],
  "search_tokens": 7954,
  "tool_calls": 1
}
```

## Python usage

```python
from kimi_search import KimiWebSearchClient

client = KimiWebSearchClient()  # picks up env vars / defaults
result = client.search("请联网搜索 Moonshot Kimi 的最新动态并用中文总结。")

print(result.answer)
print("search ids:", result.search_ids)
print("tool calls:", result.tool_calls)
print("search tokens:", result.search_tokens)
```

For multi-turn:

```python
history = []
for q in ["北京今天天气如何？", "上海呢？请对比一下。"]:
    r = client.search(q, history=history)
    print(r.answer)
    history += [
        {"role": "user", "content": q},
        {"role": "assistant", "content": r.answer},
    ]
```

For full control (e.g. injecting your own messages and additional tools):

```python
messages = [
    {"role": "system", "content": "You are Kimi."},
    {"role": "user", "content": "Search for the latest Moonshot AI news."},
]
result = client.run(messages, temperature=0.6)
```

## How it works

Moonshot's `$web_search` is registered as a *built-in* tool — meaning the
search itself is executed inside Moonshot's infrastructure. Clients only need
to:

1. Declare the tool:

   ```python
   tools = [{"type": "builtin_function", "function": {"name": "$web_search"}}]
   ```

2. Loop on the chat completion endpoint while `finish_reason == "tool_calls"`,
   appending the assistant's tool-call message and a `role: "tool"` message
   that **echoes the arguments back** as the tool result.

3. Stop when `finish_reason` becomes anything else (typically `"stop"`).

That logic is encapsulated in `KimiWebSearchClient.run()`.

## Tests

```bash
python -m unittest discover tests -v
```

The test suite stubs out the HTTP layer with a fake `requests.Session`, so it
runs offline and does not consume any API credit.

## Project layout

```
kimi_search/
  __init__.py        # Public re-exports
  __main__.py        # CLI: `python -m kimi_search ...`
  client.py          # KimiWebSearchClient + SearchResult + KimiAPIError
examples/
  quickstart.py      # One-shot search demo
  multi_turn.py      # Multi-turn conversation demo
tests/
  test_client_offline.py
requirements.txt
```
