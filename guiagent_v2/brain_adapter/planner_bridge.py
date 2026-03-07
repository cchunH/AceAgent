from typing import Any

from UniMind.agents import InfoPool, Planner, add_response
from UniMind.utils.api_client import get_model_api_response
import config


class PlannerBridge:
    """Bridge adapter that reuses legacy Planner as System-2 planner."""

    def __init__(self, model: str | None = None, temperature: float = 0.0):
        self.agent = Planner()
        self.model = model or config.models.PLANNER
        self.temperature = temperature

    def plan(
        self,
        info_pool: InfoPool,
        screenshot_file: str,
    ) -> dict[str, Any]:
        prompt = self.agent.get_prompt(info_pool)
        chat = self.agent.init_chat()
        chat = add_response("user", prompt, chat, image=screenshot_file)
        output = get_model_api_response(chat, model=self.model, temperature=self.temperature)
        return self.agent.parse_response(output)

