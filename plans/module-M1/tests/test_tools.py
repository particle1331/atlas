import tempfile
import unittest
from pathlib import Path

from agent.tools import ToolExecutor


class ToolExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.tools = ToolExecutor(self.root, timeout_s=1, max_output_chars=100)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_write_then_read(self) -> None:
        result = self.tools.execute(
            "write_file", '{"path": "nested/out.txt", "content": "hello"}'
        )
        self.assertIn("Wrote 5 characters", result)
        self.assertEqual((self.root / "nested/out.txt").read_text(), "hello")
        self.assertEqual(
            self.tools.execute("read_file", '{"path": "nested/out.txt"}'), "hello"
        )

    def test_path_escape_is_rejected(self) -> None:
        result = self.tools.execute("read_file", '{"path": "../secret.txt"}')
        self.assertIn("ERROR:", result)
        result = self.tools.execute("read_file", '{"path": "/etc/passwd"}')
        self.assertIn("ERROR:", result)

    def test_bash_timeout(self) -> None:
        result = self.tools.execute("bash", '{"command": "sleep 2"}')
        self.assertIn("exit_code=124", result)
        self.assertIn("timed out", result)

    def test_bash_output_is_truncated(self) -> None:
        result = self.tools.execute(
            "bash", '{"command": "python3 -c \\"print(\'x\' * 1000)\\""}'
        )
        self.assertIn("chars truncated", result)

    def test_invalid_json_is_returned_as_error(self) -> None:
        result = self.tools.execute("write_file", "{not json")
        self.assertIn("ERROR: invalid JSON", result)


if __name__ == "__main__":
    unittest.main()
