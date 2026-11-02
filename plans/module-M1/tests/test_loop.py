import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agent.loop import run_agent


def tool_call(name: str, arguments: dict, call_id: str = "call_1") -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
    )


def response(content=None, tool_calls=None, usage=None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content, tool_calls=tool_calls)
            )
        ],
        usage=usage
        or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    )


class FakeCompletions:
    def __init__(self, responses) -> None:
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class AgentLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_tool_call_then_final_answer(self) -> None:
        client = FakeClient(
            [
                response(
                    tool_calls=[
                        tool_call("write_file", {"path": "out.txt", "content": "ok"})
                    ]
                ),
                response(content="done"),
            ]
        )
        result = run_agent("write out.txt", self.root, client=client, max_turns=5)
        self.assertEqual(result["stop_reason"], "no_tool_call")
        self.assertEqual(result["turns"], 2)
        self.assertEqual(result["tool_calls"], 1)
        self.assertEqual((self.root / "out.txt").read_text(), "ok")
        self.assertGreater(result["cost_usd"], 0.0)

    def test_max_turns_stop(self) -> None:
        responses = [
            response(
                tool_calls=[tool_call("bash", {"command": "true"}, f"call_{index}")]
            )
            for index in range(3)
        ]
        result = run_agent("loop", self.root, client=FakeClient(responses), max_turns=2)
        self.assertEqual(result["stop_reason"], "max_turns")
        self.assertEqual(result["turns"], 2)

    def test_token_budget_stop(self) -> None:
        usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        client = FakeClient(
            [
                response(
                    tool_calls=[tool_call("bash", {"command": "true"})],
                    usage=usage,
                )
            ]
        )
        result = run_agent(
            "loop", self.root, client=client, max_turns=5, token_budget=1
        )
        self.assertEqual(result["stop_reason"], "token_budget")
        self.assertEqual(result["turns"], 1)

    def test_api_error_stop(self) -> None:
        result = run_agent(
            "fail", self.root, client=FakeClient([RuntimeError("boom")]), max_turns=2
        )
        self.assertEqual(result["stop_reason"], "api_error")
        self.assertIn("RuntimeError", result["error"])


if __name__ == "__main__":
    unittest.main()
