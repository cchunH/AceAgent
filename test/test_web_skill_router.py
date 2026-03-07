import unittest

from guiagent_v2.runtime.web_skill_router import WebSkillRouter


class TestWebSkillRouter(unittest.TestCase):
    def test_system_mobile_action_has_priority(self):
        router = WebSkillRouter()
        decision = router.route(
            intent_key="web:NAVIGATE:PAGE",
            action={"name": "Tap", "arguments": {"x": 1, "y": 2}},
            context={},
        )
        self.assertEqual(decision.channel, "mobile_native")
        self.assertEqual(decision.route_reason, "system_mobile_action")

    def test_web_intent_prefix_routes_to_skill(self):
        router = WebSkillRouter()
        decision = router.route(intent_key="web:NAVIGATE:PAGE", action={"name": "Navigate"})
        self.assertEqual(decision.channel, "web_skill")
        self.assertEqual(decision.route_reason, "web_intent_prefix")
        self.assertEqual(decision.skill_name, "AgentBrowserSkill")

    def test_web_action_prefix_routes_to_skill(self):
        router = WebSkillRouter()
        decision = router.route(intent_key="global:WEB_OPEN:PAGE", action={"name": "web_open"})
        self.assertEqual(decision.channel, "web_skill")
        self.assertEqual(decision.route_reason, "web_action_prefix")

    def test_force_channel_override(self):
        router = WebSkillRouter()
        decision = router.route(
            intent_key="global:TAP:BTN",
            action={"name": "Tap"},
            context={"force_channel": "web_skill"},
        )
        self.assertEqual(decision.channel, "web_skill")
        self.assertEqual(decision.route_reason, "forced_channel")

    def test_web_context_routes_to_skill(self):
        router = WebSkillRouter()
        decision = router.route(
            intent_key="global:UNKNOWN:X",
            action={"name": "CustomAction"},
            context={"task_type": "web"},
        )
        self.assertEqual(decision.channel, "web_skill")
        self.assertEqual(decision.route_reason, "web_context")

    def test_web_skill_name_match(self):
        router = WebSkillRouter(web_skill_names={"site_search"})
        decision = router.route(
            intent_key="global:CUSTOM:SEARCH",
            action={"name": "site_search"},
        )
        self.assertEqual(decision.channel, "web_skill")
        self.assertEqual(decision.route_reason, "web_skill_name_match")


if __name__ == "__main__":
    unittest.main()
