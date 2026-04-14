import unittest
from unittest.mock import patch

from guiagent_v2.runtime.model_task_planner import build_task_plan_with_model


class TestModelTaskPlanner(unittest.TestCase):
    def test_build_task_plan_with_subtasks(self):
        raw = (
            '{"subtasks":[{"instruction":"打开微信","subtask_key":"wechat.open",'
            '"page_hint":"首页","goal_state":"wechat_home","task_level":"L2"},'
            '{"instruction":"进入马世恒会话","subtask_key":"wechat.chat.open",'
            '"page_hint":"会话列表","goal_state":"chat_open","task_level":"L2"}],'
            '"steps":[],"plan_confidence":0.91,"reason":"ok"}'
        )
        with patch("guiagent_v2.runtime.model_task_planner.get_model_api_response", return_value=raw):
            plan = build_task_plan_with_model(
                instruction="给微信好友马世恒发一个晚安",
                max_steps=4,
                model="qwen3.5-plus",
            )
        self.assertTrue(plan["ok"])
        self.assertEqual(len(plan["steps"]), 2)
        self.assertEqual(plan["steps"][0], "打开微信")
        self.assertEqual(plan["subtasks"][0]["subtask_key"], "wechat.open")

    def test_build_task_plan_empty_should_fail(self):
        raw = '{"steps":[],"subtasks":[],"plan_confidence":0.1,"reason":"empty"}'
        with patch("guiagent_v2.runtime.model_task_planner.get_model_api_response", return_value=raw):
            plan = build_task_plan_with_model(
                instruction="测试",
                max_steps=2,
                model="qwen3.5-plus",
            )
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["error"], "MODEL_TASK_PLAN_EMPTY")


if __name__ == "__main__":
    unittest.main()
