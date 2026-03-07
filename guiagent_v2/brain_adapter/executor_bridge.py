from typing import Any

from UniMind.agents import Executor, InfoPool, add_response
from UniMind.utils.api_client import get_model_api_response
import config


class ExecutorBridge:
    """Bridge adapter that reuses legacy Executor as System-2 executor."""

    def __init__(self, adb_path: str, model: str | None = None, temperature: float = 0.0):
        self.agent = Executor(adb_path=adb_path)
        self.model = model or config.models.EXECUTOR
        self.temperature = temperature

    def decide_action(
        self,
        info_pool: InfoPool,
        screenshot_file: str,
    ) -> dict[str, Any]:
        prompt = self.agent.get_prompt(info_pool)
        chat = self.agent.init_chat()
        chat = add_response("user", prompt, chat, image=screenshot_file)
        output = get_model_api_response(chat, model=self.model, temperature=self.temperature)
        return self.agent.parse_response(output)

    def execute(
        self,
        action_str: str,
        info_pool: InfoPool,
        **kwargs,
    ) -> tuple[dict[str, Any] | None, int, Any]:
        return self.agent.execute(action_str, info_pool, **kwargs)

