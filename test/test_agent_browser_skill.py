import subprocess
import unittest
from unittest.mock import patch

from guiagent_v2.runtime.agent_browser_skill import AgentBrowserCLIAdapter, AgentBrowserSkill


class TestAgentBrowserCLIAdapter(unittest.TestCase):
    def test_execute_success_and_command_shape(self):
        adapter = AgentBrowserCLIAdapter(executable="agent-browser", timeout_sec=1)
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"success":true,"data":{"url":"https://example.com"}}\n',
            stderr="",
        )
        with patch("guiagent_v2.runtime.agent_browser_skill.subprocess.run", return_value=completed) as mocked:
            result = adapter.execute(
                {
                    "action": "open",
                    "url": "https://example.com",
                    "session_id": "s1",
                }
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["session_id"], "s1")
        self.assertEqual(result["data"], {"url": "https://example.com"})
        called_command = mocked.call_args[0][0]
        self.assertEqual(called_command[:4], ["agent-browser", "--json", "--session", "s1"])
        self.assertEqual(called_command[-2:], ["open", "https://example.com"])

    def test_execute_cli_not_found(self):
        adapter = AgentBrowserCLIAdapter(executable="agent-browser")
        with patch(
            "guiagent_v2.runtime.agent_browser_skill.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            result = adapter.execute({"action": "open", "url": "https://example.com"})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "CLI_NOT_FOUND")

    def test_execute_unsupported_request(self):
        adapter = AgentBrowserCLIAdapter()
        result = adapter.execute({"action": "unknown_action"})
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "UNSUPPORTED_REQUEST")


class TestAgentBrowserSkill(unittest.TestCase):
    def test_invoke_with_ensure_session_failure(self):
        adapter = AgentBrowserCLIAdapter()
        skill = AgentBrowserSkill(adapter=adapter)

        with patch.object(adapter, "start_session", return_value={"success": False, "error": "DENIED"}):
            response = skill.invoke(
                task={"action": "open", "url": "https://example.com"},
                session={"session_id": "web-a"},
                constraints={"ensure_session": True},
            )

        self.assertFalse(response["success"])
        self.assertEqual(response["error"], "DENIED")

    def test_invoke_success(self):
        adapter = AgentBrowserCLIAdapter()
        skill = AgentBrowserSkill(adapter=adapter)
        with patch.object(
            adapter,
            "execute",
            return_value={
                "success": True,
                "data": {"snapshot": "ok"},
                "error": None,
                "session_id": "web-b",
                "command": ["agent-browser", "snapshot"],
            },
        ):
            response = skill.invoke(
                task={"action": "snapshot"},
                session="web-b",
            )

        self.assertTrue(response["success"])
        self.assertEqual(response["result"], {"snapshot": "ok"})
        self.assertEqual(response["trace"][0]["session_id"], "web-b")


if __name__ == "__main__":
    unittest.main()
