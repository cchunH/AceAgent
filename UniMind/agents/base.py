
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

@dataclass
class InfoPool:
    """Keeping track of all information across the agents."""

    # User input / accumulated knowledge
    instruction: str = ""
    heuristics: str = ""
    skills: dict = field(default_factory=dict)

    # Perception
    width: int = 1080
    height: int = 2340
    perception_infos_pre: list = field(default_factory=list) # List of clickable elements pre action
    keyboard_pre: bool = False # keyboard status pre action
    perception_infos_post: list = field(default_factory=list) # List of clickable elements post action
    keyboard_post: bool = False # keyboard status post action

    # Working memory
    summary_history: list = field(default_factory=list)  # List of action descriptions
    action_history: list = field(default_factory=list)  # List of actions
    action_outcomes: list = field(default_factory=list)  # List of action outcomes
    error_descriptions: list = field(default_factory=list)

    last_summary: str = ""  # Last action description
    last_action: str = ""  # Last action
    last_action_thought: str = ""  # Last action thought
    important_notes: str = ""
    
    error_flag_plan: bool = False # if an error is not solved for mulheuristicle attempts with the executor
    error_description_plan: bool = False # explanation of the error for modifying the plan

    # Planning
    plan: str = ""
    progress_status: str = ""
    progress_status_history: list = field(default_factory=list)
    finish_thought: str = ""
    current_subgoal: str = ""
    prev_subgoal: str = ""
    err_to_planner_thresh: int = 2

    # future tasks
    future_tasks: list = field(default_factory=list)


class BaseAgent(ABC):
    @abstractmethod
    def init_chat(self) -> list:
        pass
    @abstractmethod
    def get_prompt(self, info_pool: InfoPool) -> str:
        pass
    @abstractmethod
    def parse_response(self, response: str) -> dict:
        pass

# name: {arguments: [argument_keys], description: description}
ATOMIC_ACTION_SIGNITURES = {
    "Open_App": {
        "arguments": ["app_name"],
        "description": lambda info: "If the current screen is Home or App screen, you can use this action to open the app named \"app_name\" on the visible on the current screen."
    },
    "Tap": {
        "arguments": ["x", "y"],
        "description": lambda info: "Tap the position (x, y) in current screen."
    },
    "Swipe": {
        "arguments": ["x1", "y1", "x2", "y2"],
        "description": lambda info: (
            f"Swipe from position (x1, y1) to position (x2, y2). "
            f"IMPORTANT: To ensure the swipe is registered correctly, start and end points should be within a 'safe area' of the screen, typically away from the extreme edges. "
            f"For a RELIABLE HORIZONTAL swipe from right to left (to see the next page), a good example is: "
            f"x1 = {int(0.8 * info.width)}, y1 = {int(0.5 * info.height)}, x2 = {int(0.2 * info.width)}, y2 = {int(0.5 * info.height)}. "
            f"For a RELIABLE VERTICAL swipe from bottom to top (to scroll down), a good example is: "
            f"x1 = {int(0.5 * info.width)}, y1 = {int(0.8 * info.height)}, x2 = {int(0.5 * info.width)}, y2 = {int(0.2 * info.height)}."
        )
    },
    "Type": {
        "arguments": ["text"],
        "description": lambda info: "Type the \"text\" in an input box."
    },
    "Enter": {
        "arguments": [],
        "description": lambda info: "Press the Enter key after typing (useful for searching)."
    },
    "Switch_App": {
        "arguments": [],
        "description": lambda info: "Show the App switcher for switching between opened apps."
    },
    "Back": {
        "arguments": [],
        "description": lambda info: "Return to the previous state."
    },
    "Home": {
        "arguments": [],
        "description": lambda info: "Return to home page."
    },
    "Wait": {
        "arguments": [],
        "description": lambda info: "Wait for 10 seconds to give more time for a page loading."
    },
    "Long_press": {
        "arguments": ["x", "y"],
        "description": lambda info: "Press and hold at the position (x, y) for 1 second. Use this to select text or open context menus when a simple 'Tap' does not work."
    },
}

INIT_SKILLS = {
    "Tap_Type_and_Enter": {
        "name": "Tap_Type_and_Enter",
        "arguments": ["x", "y", "text"],
        "description": "Tap an input box at position (x, y), Type the \"text\", and then perform the Enter operation. Very useful for searching and sending messages!",
        "precondition": "There is a text input box on the screen with no previously entered content.",
        "atomic_action_sequence":[
            {"name": "Tap", "arguments_map": {"x":"x", "y":"y"}},
            {"name": "Type", "arguments_map": {"text":"text"}},
            {"name": "Enter", "arguments_map": {}}
        ]
    }
}
