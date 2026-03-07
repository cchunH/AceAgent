# UniMind\agents\expert_track_agents.py
from .base import ATOMIC_ACTION_SIGNITURES, BaseAgent, InfoPool
from UniMind.device.action_executor import  execute,execute_atomic_action

class Planner(BaseAgent):

    def init_chat(self):
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant for operating mobile phones. Your goal is to track progress and devise high-level plans to achieve the user's requests. Think as if you are a human user operating the phone."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        if info_pool.plan == "":
            # first time planning
            prompt += "---\n"
            prompt += "Think step by step and make an high-level plan to achieve the user's instruction. If the request is complex, break it down into subgoals. If the request involves exploration, include concrete subgoals to quantify the investigation steps. The screenshot displays the starting state of the phone.\n\n"
            
            if info_pool.skills != {}:
                prompt += "### Available Skills from Past Experience ###\n"
                prompt += "We additionally provide some skill functionalities based on past experience. These skills are predefined sequences of operations that might make the plan more efficient. Each skill includes a precondition specifying when it is suitable for use. If your plan implies the use of certain skills, ensure that the precondition is fulfilled before using them. Note that you don't necessarily need to include the names of these skills in your high-level plan; they are provided as a reference.\n"
                for skill, value in info_pool.skills.items():
                    prompt += f"- {skill}: {value['description']} | Precondition: {value['precondition']}\n"
                prompt += "\n"
            prompt += "---\n"

            prompt += "Provide your output in the following format which contains three parts:\n\n"
            prompt += "### Thought ###\n"
            prompt += "A detailed explanation of your rationale for the plan and subgoals.\n\n"
            prompt += "### Plan ###\n"
            prompt += "1. first subgoal\n"
            prompt += "2. second subgoal\n"
            prompt += "...\n\n"
            prompt += "### Current Subgoal ###\n"
            prompt += "The first subgoal you should work on.\n\n"
        else:
            # continue planning
            prompt += "### Current Plan ###\n"
            prompt += f"{info_pool.plan}\n\n"
            prompt += "### Previous Subgoal ###\n"
            prompt += f"{info_pool.current_subgoal}\n\n"
            prompt += f"### Progress Status ###\n"
            prompt += f"{info_pool.progress_status}\n\n"
            prompt += "### Important Notes ###\n"
            if info_pool.important_notes != "":
                prompt += f"{info_pool.important_notes}\n\n"
            else:
                prompt += "No important notes recorded.\n\n"
            if info_pool.error_flag_plan:
                prompt += "### Potentially Stuck! ###\n"
                prompt += "You have encountered several failed attempts. Here are some logs:\n"
                k = info_pool.err_to_planner_thresh
                recent_actions = info_pool.action_history[-k:]
                recent_summaries = info_pool.summary_history[-k:]
                recent_err_des = info_pool.error_descriptions[-k:]
                for i, (act, summ, err_des) in enumerate(zip(recent_actions, recent_summaries, recent_err_des)):
                    prompt += f"- Attempt: Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"

            prompt += "---\n"
            prompt += "The sections above provide an overview of the plan you are following, the current subgoal you are working on, the overall progress made, and any important notes you have recorded. The screenshot displays the current state of the phone.\n"
            prompt += "Carefully assess the current status to determine if the task has been fully completed. If the user's request involves exploration, ensure you have conducted sufficient investigation. If you are confident that no further actions are required, mark the task as \"Finished\" in your output. If the task is not finished, outline the next steps. If you are stuck with errors, think step by step about whether the overall plan needs to be revised to address the error.\n"
            prompt += "NOTE: If the current situation prevents proceeding with the original plan or requires clarification from the user, make reasonable assumptions and revise the plan accordingly. Act as though you are the user in such cases.\n\n"

            if info_pool.skills != {}:
                prompt += "### Available Skills from Past Experience ###\n"
                prompt += "We additionally provide some skill functionalities based on past experience. These skills are predefined sequences of operations that might make the plan more efficient. Each skill includes a precondition specifying when it is suitable for use. If your plan implies the use of certain skills, ensure that the precondition is fulfilled before using them. Note that you don't necessarily need to include the names of these skills in your high-level plan; they are provided only as a reference.\n"
                for skill, value in info_pool.skills.items():
                    prompt += f"- {skill}: {value['description']} | Precondition: {value['precondition']}\n"
                prompt += "\n"
            
            prompt += "---\n"
            prompt += "Provide your output in the following format, which contains three parts:\n\n"
            prompt += "### Thought ###\n"
            prompt += "Provide a detailed explanation of your rationale for the plan and subgoals.\n\n"
            prompt += "### Plan ###\n"
            prompt += "If an update is required for the high-level plan, provide the updated plan here. Otherwise, keep the current plan and copy it here.\n\n"
            prompt += "### Current Subgoal ###\n"
            prompt += "The next subgoal to work on. If the previous subgoal is not yet complete, copy it here. If all subgoals are completed, write \"Finished\".\n"
        return prompt

    def parse_response(self, response: str) -> dict:
        thought = response.split("### Thought ###")[-1].split("### Plan ###")[0].replace("\n", " ").replace("  ", " ").strip()
        plan = response.split("### Plan ###")[-1].split("### Current Subgoal ###")[0].replace("\n", " ").replace("  ", " ").strip()
        current_subgoal = response.split("### Current Subgoal ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"thought": thought, "plan": plan, "current_subgoal": current_subgoal}

class Executor(BaseAgent):
    def __init__(self, adb_path):
        self.adb = adb_path

    def init_chat(self):
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant for operating mobile phones. Your goal is to choose the correct actions to complete the user's instruction. Think as if you are a human user operating the phone."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### Overall Plan ###\n"
        prompt += f"{info_pool.plan}\n\n"

        prompt += "### Progress Status ###\n"
        if info_pool.progress_status != "":
            prompt += f"{info_pool.progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{info_pool.current_subgoal}\n\n"

        prompt += "### Screen Information ###\n"
        prompt += (
            f"The attached image is a screenshot showing the current state of the phone. "
            f"Its width and height are {info_pool.width} and {info_pool.height} pixels, respectively.\n"
        )
        prompt += (
            "To help you better understand the content in this screenshot, we have extracted positional information for the text elements and icons, including interactive elements such as search bars. "
            "The format is: (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (from left to right) "
            "and y represents the vertical pixel position (from top to bottom)."
        )
        prompt += "The extracted information is as follows:\n"

        for clickable_info in info_pool.perception_infos_pre:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += (
            "Note that a search bar is often a long, rounded rectangle. If no search bar is presented and you want to perform a search, you may need to tap a search button, which is commonly represented by a magnifying glass.\n"
            "Also, the information above might not be entirely accurate. "
            "You should combine it with the screenshot to gain a better understanding."
        )
        prompt += "\n\n"

        prompt += "### Keyboard status ###\n"
        if info_pool.keyboard_pre:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"

        if info_pool.heuristics != "":
            prompt += "### Heuristics ###\n"
            prompt += "From previous experience interacting with the device, you have collected the following heuristics that might be useful for deciding what to do next:\n"
            prompt += f"{info_pool.heuristics}\n\n"

        prompt += "### Important Notes ###\n"
        if info_pool.important_notes != "":
            prompt += "Here are some potentially important content relevant to the user's request you already recorded:\n"
            prompt += f"{info_pool.important_notes}\n\n"
        else:
            prompt += "No important notes recorded.\n\n"

        prompt += "---\n"
        prompt += "Carefully examine all the information provided above and decide on the next action to perform. If you notice an unsolved error in the previous action, think as a human user and attempt to rectify them. You must choose your action from one of the atomic actions or the skills. The skills are predefined sequences of actions that can be used to speed up the process. Each skill has a precondition specifying when it is suitable to use. If you plan to use a skill, ensure the current phone state satisfies its precondition first.\n\n"
        
        prompt += "#### Atomic Actions ####\n"
        prompt += "The atomic action functions are listed in the format of `name(arguments): description` as follows:\n"

        if info_pool.keyboard_pre:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info_pool)}\n"
        else:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                if "Type" not in action:
                    prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info_pool)}\n"
            prompt += "NOTE: Unable to type. The keyboard has not been activated. To type, please activate the keyboard by tapping on an input box or using a skill, which includes tapping on an input box first.”\n"
        
        prompt += "\n"
        prompt += "#### Skills ####\n"
        if info_pool.skills != {}:
            prompt += "The skill functions are listed in the format of `name(arguments): description | Precondition: precondition` as follows:\n"
            for skill, value in info_pool.skills.items():
                prompt += f"- {skill}({', '.join(value['arguments'])}): {value['description']} | Precondition: {value['precondition']}\n"
        else:
            prompt += "No skills are available.\n"
        prompt += "\n"

        prompt += "### Latest Action History ###\n"
        if info_pool.action_history != []:
            prompt += "Recent actions you took previously and whether they were successful:\n"
            num_actions = min(5, len(info_pool.action_history))
            latest_actions = info_pool.action_history[-num_actions:]
            latest_summary = info_pool.summary_history[-num_actions:]
            latest_outcomes = info_pool.action_outcomes[-num_actions:]
            error_descriptions = info_pool.error_descriptions[-num_actions:]
            action_log_strs = []
            for act, summ, outcome, err_des in zip(latest_actions, latest_summary, latest_outcomes, error_descriptions):
                if outcome == "A":
                    action_log_str = f"Action: {act} | Description: {summ} | Outcome: Successful\n"
                else:
                    action_log_str = f"Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
                prompt += action_log_str
                action_log_strs.append(action_log_str)
            if latest_outcomes[-1] == "C" and "Tap" in action_log_strs[-1] and "Tap" in action_log_strs[-2]:
                prompt += "\nHINT: If mulheuristicle Tap actions failed to make changes to the screen, consider using a \"Swipe\" action to view more content or use another way to achieve the current subgoal."
            
            prompt += "\n"
        else:
            prompt += "No actions have been taken yet.\n\n"

        prompt += "---\n"
        prompt += "Provide your output in the following format, which contains three parts:\n"
        prompt += "### Thought ###\n"
        prompt += "Provide a detailed explanation of your rationale for the chosen action. IMPORTANT: If you decide to use a skill, first verify that its precondition is met in the current phone state. For example, if the skill requires the phone to be at the Home screen, check whether the current screenshot shows the Home screen. If not, perform the appropriate atomic actions instead.\n\n"

        prompt += "### Action ###\n"
        prompt += "Choose only one action or skill from the options provided. IMPORTANT: Do NOT return invalid actions like null or stop. Do NOT repeat previously failed actions.\n"
        prompt += "Use skills whenever possible to expedite the process, but make sure that the precondition is met.\n"
        prompt += "You must provide your decision using a valid JSON format specifying the name and arguments of the action. For example, if you choose to tap at position (100, 200), you should write {\"name\":\"Tap\", \"arguments\":{\"x\":100, \"y\":100}}. If an action does not require arguments, such as Home, fill in null to the \"arguments\" field. Ensure that the argument keys match the action function's signature exactly.\n\n"
        
        prompt += "### Description ###\n"
        prompt += "A brief description of the chosen action and the expected outcome.\n\n"
        prompt += "### Next Step Dependency ###\n"
        prompt += "Based on your chosen action, evaluate whether the NEXT planning step (by the Planner) STRONGLY depends on new information (like prices, names, addresses, etc.) that will appear on the screen AFTER this action is successful. Choose ONE of the following:\n"
        prompt += "- \"High\": The next plan strongly depends on new information. (e.g., after searching for a product, the next step is to compare its price).\n"
        prompt += "- \"Low\": The next step is a procedural action and does not depend on new information. (e.g., after typing a name, the next step is to tap the 'Next' button).\n"
        return prompt

    def parse_response(self, response: str) -> dict:
        thought = response.split("### Thought ###")[-1].split("### Action ###")[0].replace("\n", " ").replace("  ", " ").strip()
        action = response.split("### Action ###")[-1].split("### Description ###")[0].replace("\n", " ").replace("  ", " ").strip()
        description = response.split("### Description ###")[-1].split("### Next Step Dependency ###")[0].replace("\n", " ").replace("  ", " ").strip()
        
        # Parse next step dependency
        try:
            dependency = response.split("### Next Step Dependency ###")[-1].strip().lower()
            if "high" in dependency:
                next_step_dependency = "High"
            else:
                next_step_dependency = "Low"
        except:
            next_step_dependency = "High"  # Default to High for safety
        
        return {
            "thought": thought, 
            "action": action, 
            "description": description,
            "next_step_dependency": next_step_dependency
        }
    
    def execute(self, action_str: str, info_pool: InfoPool, **kwargs):
        """Execute the action using the action_executor logic"""
        # Call the execute function from action_executor
        return execute(self, action_str, info_pool, **kwargs)
    
    def execute_atomic_action(self, action: str, arguments: dict, **kwargs):
        return execute_atomic_action(self, action, arguments, **kwargs)
    

    


class VerifyCore(BaseAgent):
    def init_chat(self) -> list:
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant for operating mobile phones. Your goal is to verify whether the last action produced the expected behavior and to keep track of the overall progress."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### Progress Status ###\n"
        if info_pool.progress_status != "":
            prompt += f"{info_pool.progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{info_pool.current_subgoal}\n\n"

        prompt += "---\n"
        prompt += f"The attached two images are two phone screenshots before and after your last action. " 
        prompt += f"The width and height are {info_pool.width} and {info_pool.height} pixels, respectively.\n"
        prompt += (
            "To help you better perceive the content in these screenshots, we have extracted positional information for the text elements and icons. "
            "The format is: (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (from left to right) "
            "and y represents the vertical pixel position (from top to bottom).\n"
        )
        prompt += (
            "Note that these information might not be entirely accurate. "
            "You should combine them with the screenshots to gain a better understanding."
        )
        prompt += "\n\n"

        prompt += "### Screen Information Before the Action ###\n"
        for clickable_info in info_pool.perception_infos_pre:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += "Keyboard status before the action: "
        if info_pool.keyboard_pre:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"


        prompt += "### Screen Information After the Action ###\n"
        for clickable_info in info_pool.perception_infos_post:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += "Keyboard status after the action: "
        if info_pool.keyboard_post:
            prompt += "The keyboard has been activated and you can type."
        else:
            prompt += "The keyboard has not been activated and you can\'t type."
        prompt += "\n\n"

        prompt += "---\n"
        prompt += "### Latest Action ###\n"
        # assert info_pool.last_action != ""
        prompt += f"Action: {info_pool.last_action}\n"
        prompt += f"Expectation: {info_pool.last_summary}\n\n"

        prompt += "---\n"
        prompt += "Carefully examine the information provided above to determine whether the last action produced the expected behavior. If the action was successful, update the progress status accordingly. If the action failed, identify the failure mode and provide reasoning on the potential reason causing this failure. Note that for the “Swipe” action, it may take mulheuristicle attempts to display the expected content. Thus, for a \"Swipe\" action, if the screen shows new content, it usually meets the expectation.\n\n"

        prompt += "Provide your output in the following format containing three parts:\n\n"
        prompt += "### Outcome ###\n"
        prompt += "Choose from the following options. Give your answer as \"A\", \"B\" or \"C\":\n"
        prompt += "A: Successful or Partially Successful. The result of the last action meets the expectation.\n"
        prompt += "B: Failed. The last action results in a wrong page. I need to return to the previous state.\n"
        prompt += "C: Failed. The last action produces no changes.\n\n"

        prompt += "### Error Description ###\n"
        prompt += "If the action failed, provide a detailed description of the error and the potential reason causing this failure. If the action succeeded, put \"None\" here.\n\n"

        prompt += "### Progress Status ###\n"
        prompt += "If the action was successful or partially successful, update the progress status. If the action failed, copy the previous progress status.\n"

        return prompt

    def parse_response(self, response: str) -> dict:
        outcome = response.split("### Outcome ###")[-1].split("### Error Description ###")[0].replace("\n", " ").replace("  ", " ").strip()
        error_description = response.split("### Error Description ###")[-1].split("### Progress Status ###")[0].replace("\n", " ").replace("  ", " ").strip()
        progress_status = response.split("### Progress Status ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"outcome": outcome, "error_description": error_description, "progress_status": progress_status}


class Notetaker(BaseAgent):
    def init_chat(self) -> list:
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant for operating mobile phones. Your goal is to take notes of important content relevant to the user's request."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "### User Instruction ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### Overall Plan ###\n"
        prompt += f"{info_pool.plan}\n\n"

        prompt += "### Current Subgoal ###\n"
        prompt += f"{info_pool.current_subgoal}\n\n"

        prompt += "### Progress Status ###\n"
        prompt += f"{info_pool.progress_status}\n\n"

        prompt += "### Existing Important Notes ###\n"
        if info_pool.important_notes != "":
            prompt += f"{info_pool.important_notes}\n\n"
        else:
            prompt += "No important notes recorded.\n\n"

        prompt += "### Current Screen Information ###\n"
        prompt += (
            f"The attached image is a screenshot showing the current state of the phone. "
            f"Its width and height are {info_pool.width} and {info_pool.height} pixels, respectively.\n"
        )
        prompt += (
            "To help you better perceive the content in this screenshot, we have extracted positional information for the text elements and icons. "
            "The format is: (coordinates; content). The coordinates are [x, y], where x represents the horizontal pixel position (from left to right) "
            "and y represents the vertical pixel position (from top to bottom)."
        )
        prompt += "The extracted information is as follows:\n"

        for clickable_info in info_pool.perception_infos_post:
            if clickable_info['text'] != "" and clickable_info['text'] != "icon: None" and clickable_info['coordinates'] != (0, 0):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"
        prompt += (
            "Note that this information might not be entirely accurate. "
            "You should combine it with the screenshot to gain a better understanding."
        )
        prompt += "\n\n"

        prompt += "---\n"
        prompt += "Carefully examine the information above to identify any important content that needs to be recorded. IMPORTANT: Do not take notes on low-level actions; only keep track of significant textual or visual information relevant to the user's request.\n\n"

        prompt += "Provide your output in the following format:\n"
        prompt += "### Important Notes ###\n"
        prompt += "The updated important notes, combining the old and new ones. If nothing new to record, copy the existing important notes.\n"

        # # --- 非vlm 版本 ---
        # prompt += "### Current Screen Content Report ###\n"
        # prompt += (
        #     "The following is a structured report of all text and icons currently visible "
        #     "on the phone screen. Your task is to analyze this report to extract key information.\n"
        # )
        # prompt += (
        #     "The format is: [x, y]; content. [x, y] represents the central coordinates of the element.\n"
        # )
        # prompt += "The extracted information is as follows:\n"

        # for clickable_info in info_pool.perception_infos_post:
        #     if clickable_info['text'] and clickable_info['text'] not in ["", "icon: None"] and clickable_info['coordinates'] != (0, 0):
        #         prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        # prompt += "\n"
        # prompt += (
        #     "Note: This report is generated by an automated perception system and might contain minor "
        #     "inaccuracies or recognition errors. Please rely on your reasoning to interpret the content.\n"
        # )
        # # --- 核心改动结束 ---

        # prompt += "---\n"
        # prompt += "Carefully examine the information above to identify any important content that needs to be recorded. IMPORTANT: Do not take notes on low-level actions; only keep track of significant textual or visual information relevant to the user's request.\n\n"

        # prompt += "Provide your output in the following format:\n"
        # prompt += "### Important Notes ###\n"
        # prompt += "The updated important notes, combining the old and new ones. If nothing new to record, copy the existing important notes.\n"


        return prompt

    def parse_response(self, response: str) -> dict:
        important_notes = response.split("### Important Notes ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"important_notes": important_notes}
