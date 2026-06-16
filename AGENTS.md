# chinese-chess-desktop

The long-term goal of this repository is a Chinese Chess (Xiangqi) desktop
application. That desktop app does not exist yet.

## Cursor Cloud specific instructions

### Repository state

- The `main` branch is currently a placeholder: it contains only `README.md`
  (and this `AGENTS.md`). There is no application, package manifest, or test
  suite on `main`, so there is nothing to build or run from a fresh `main`
  checkout.
- The only real code today is the `kimi_search` Python project, which lives on
  the unmerged feature branch `cursor/kimi-web-search-e047` (a Kimi/Moonshot
  `$web_search` client: library + `python -m kimi_search` CLI). Check that
  branch out to work on it.

### Toolchain

- Python 3.12 and `pip` are preinstalled. The only runtime dependency of
  `kimi_search` is `requests`, which is already present in the base image (and
  re-installed by the startup update script when a `requirements.txt` exists).
- No linter, type checker, or build/packaging step is configured anywhere in
  the repo.

### Running and testing `kimi_search` (on its feature branch)

Standard commands are documented in that branch's `README.md`. In short:

- Tests (offline, HTTP layer is mocked — no network or API key needed):
  `python -m unittest discover tests -v`
- CLI: `python -m kimi_search "your query"` (flags: `--json`, `--show-queries`,
  `--model`, `--api-key`, `--base-url`).

### Live web-search caveats (non-obvious)

- The CLI/library makes real calls to the Moonshot/Kimi API. API key resolution
  order is `--api-key` → `MOONSHOT_API_KEY` → `KIMI_API_KEY` → a bundled
  fallback key.
- The bundled fallback key only works against the **`.cn`** endpoint
  (`https://api.moonshot.cn/v1`, the default). The international endpoint
  `https://api.moonshot.ai/v1` rejects it with HTTP 401, so do not switch
  `MOONSHOT_BASE_URL` to `.ai` unless you also supply a `.ai`-scoped key.
- The shared `.cn` engine frequently returns HTTP 429
  `engine_overloaded_error`; this is a Moonshot-side limitation, not a code or
  environment problem. Live searches may need retries, or set your own
  `MOONSHOT_API_KEY` to get more reliable results. The offline test suite does
  not depend on the API at all.
