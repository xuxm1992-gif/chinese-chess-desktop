"""Offline tests for KimiWebSearchClient.

These tests stub out the HTTP layer with a fake ``requests.Session`` so we can
exercise the tool-call loop without hitting the real API.
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from typing import Any, Dict, List
from unittest import mock

# Make the repo root importable when tests are run directly.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from kimi_search import KimiAPIError, KimiWebSearchClient  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int, body: Dict[str, Any]):
        self.status_code = status_code
        self._body = body
        self.text = json.dumps(body)

    def json(self) -> Dict[str, Any]:
        return self._body


class _FakeSession:
    """Returns a queue of canned responses, capturing each request payload."""

    def __init__(self, responses: List[_FakeResponse]):
        self._responses = list(responses)
        self.calls: List[Dict[str, Any]] = []

    def post(self, url, headers=None, json=None, timeout=None):  # noqa: A002
        self.calls.append({"url": url, "headers": headers, "json": json,
                           "timeout": timeout})
        if not self._responses:
            raise AssertionError("No more fake responses queued")
        return self._responses.pop(0)


class ClientLoopTests(unittest.TestCase):

    def _make_client(self, responses: List[_FakeResponse]) -> KimiWebSearchClient:
        session = _FakeSession(responses)
        client = KimiWebSearchClient(api_key="test-key", session=session)
        client._fake_session = session  # type: ignore[attr-defined]
        return client

    def test_tool_call_loop_executes_search_and_returns_final_answer(self):
        tool_call_response = _FakeResponse(200, {
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "$web_search",
                            "arguments": json.dumps({
                                "query": "Moonshot AI Kimi"
                            }),
                        },
                    }],
                },
            }]
        })
        final_response = _FakeResponse(200, {
            "choices": [{
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Moonshot AI is the company behind Kimi.",
                },
            }]
        })
        client = self._make_client([tool_call_response, final_response])

        result = client.search("Tell me about Moonshot AI's Kimi.")

        self.assertEqual(result.answer, "Moonshot AI is the company behind Kimi.")
        self.assertEqual(result.tool_calls, 1)
        self.assertEqual(result.queries, ["Moonshot AI Kimi"])

        session = client._fake_session  # type: ignore[attr-defined]
        self.assertEqual(len(session.calls), 2)

        first_payload = session.calls[0]["json"]
        self.assertEqual(first_payload["model"], "moonshot-v1-auto")
        self.assertEqual(first_payload["tools"], [{
            "type": "builtin_function",
            "function": {"name": "$web_search"},
        }])

        second_payload = session.calls[1]["json"]
        roles = [m["role"] for m in second_payload["messages"]]
        self.assertIn("tool", roles)
        tool_msg = next(m for m in second_payload["messages"] if m["role"] == "tool")
        self.assertEqual(tool_msg["name"], "$web_search")
        self.assertEqual(json.loads(tool_msg["content"]), {"query": "Moonshot AI Kimi"})

    def test_http_error_raises_kimi_api_error(self):
        bad_response = _FakeResponse(401, {"error": {"message": "bad key"}})
        client = self._make_client([bad_response])
        with self.assertRaises(KimiAPIError) as ctx:
            client.search("hi")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_max_iterations_guard(self):
        infinite = [
            _FakeResponse(200, {
                "choices": [{
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": "$web_search",
                                "arguments": json.dumps({"query": "loop"}),
                            },
                        }],
                    },
                }]
            })
            for i in range(20)
        ]
        client = self._make_client(infinite)
        client.max_tool_iterations = 2
        with self.assertRaises(KimiAPIError):
            client.search("loop")

    def test_api_key_resolution_prefers_explicit_then_env(self):
        with mock.patch.dict(os.environ, {"MOONSHOT_API_KEY": "env-key"},
                             clear=False):
            self.assertEqual(KimiWebSearchClient(api_key="x").api_key, "x")
            self.assertEqual(KimiWebSearchClient().api_key, "env-key")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
