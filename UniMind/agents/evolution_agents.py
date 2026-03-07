from .utils.json_utils import extract_json_object
from .base import BaseAgent, InfoPool
from .base import ATOMIC_ACTION_SIGNITURES


SKILL_EXMPALE = """
{
    "name": "Tap_Type_and_Enter",
    "arguments": ["x", "y", "text"],
    "description": "Tap an input box at position (x, y), Type the \"text\", and then perform the Enter operation (useful for searching or sending messages).",
    "precondition": "There is a text input box on the screen.",
    "atomic_action_sequence":[
        {"name": "Tap", "arguments_map": {"x":"x", "y":"y"}},
        {"name": "Type", "arguments_map": {"text":"text"}},
        {"name": "Enter", "arguments_map": {}}
    ]
}
"""


class SkillLearningCore(BaseAgent):
    def init_chat(self) -> list:
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant specializing in mobile phone operations. Your goal is to reflect on past experiences and provide insights to improve future interactions."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "### Current Task ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### Overall Plan ###\n"
        prompt += f"{info_pool.plan}\n\n"

        prompt += "### Progress Status ###\n"
        prompt += f"{info_pool.progress_status}\n\n"

        prompt += "### Atomic Actions ###\n"
        prompt += "Here are the atomic actions in the format of `name(arguments): description` as follows:\n"
        for action, value in ATOMIC_ACTION_SIGNITURES.items():
            prompt += f"{action}({', '.join(value['arguments'])}): {value['description'](info_pool)}\n"
        prompt += "\n"

        prompt += "### Existing Skills from Past Experience ###\n"
        if info_pool.skills != {}:
            prompt += "Here are some existing skills you have created:\n"
            for skill, value in info_pool.skills.items():
                prompt += f"- {skill}({', '.join(value['arguments'])}): {value['description']} | Precondition: {value['precondition']}\n"
        else:
            prompt += "No skills are provided.\n"
        prompt += "\n"

        prompt += "### Full Action History ###\n"
        if info_pool.action_history != []:
            latest_actions = info_pool.action_history
            latest_summary = info_pool.summary_history
            action_outcomes = info_pool.action_outcomes
            error_descriptions = info_pool.error_descriptions
            progress_status_history = info_pool.progress_status_history
            for act, summ, outcome, err_des, progress in zip(latest_actions, latest_summary, action_outcomes, error_descriptions, progress_status_history):
                if outcome == "A":
                    prompt += f"- Action: {act} | Description: {summ} | Outcome: Successful | Progress: {progress}\n"
                else:
                    prompt += f"- Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
            prompt += "\n"
        else:
            prompt += "No actions have been taken yet.\n\n"

        if len(info_pool.future_tasks) > 0:
            prompt += "---\n"
            prompt += "### Future Tasks ###\n"
            prompt += "Here are some tasks that you might be asked to do in the future:\n"
            for task in info_pool.future_tasks:
                prompt += f"- {task}\n"
            prompt += "\n"

        prompt += "---\n"
        prompt += "Carefully reflect on the interaction history of the current task. Check if there are any subgoals that are accomplished by a sequence of successful actions and can be consolidated into new \"Skills\" to improve efficiency for future tasks? These skills are subroutines consisting of a series of atomic actions that can be executed under specific preconditions. For example, tap, type and enter text in a search bar or creating a new note in Notes.\n\n"
        
        prompt += "### 关键学习关注点 ###\n"
        prompt += "请特别关注以下方面：\n"
        prompt += "1. 高成功率操作序列，可抽象为可复用技能\n"
        prompt += "2. 复杂问题解决模式，可沉淀为高级技能\n"
        prompt += "3. 失败后的恢复动作组合，可形成稳健技能模板\n"
        prompt += "4. 兼顾效率和成功率的复合技能设计\n\n"

        prompt += "Provide your output in the following format:\n\n"

        prompt += "### New Skill ###\n"
        prompt += "If you decide to create a new skill (not already in the existing skills), provide your skill object in a valid JSON format which is detailed below. If not, put \"None\" here.\n"
        prompt += "A skill object contains the following fields: name, arguments, description, precondition, and atomic_action_sequence. The keys in the arguements need to be unique. The atomic_action_sequence is a list of dictionaries, each containing the name of an atomic action and a mapping of its atomic argument names to the skill's argument name. If an atomic action in the atomic_action_sequence does not take any arugments, set the `arguments_map` to an empty dict. \n"
        prompt += "IMPORTANT: The skill must ONLY include the Atomic Actions listed above. Create a new skill only if you are confident it will be useful in the future. Ensure that duplicated skills with overly similar functionality are not included.\n"
        prompt += "PRO HEURISTIC: Avoid creating skills with too many arguments, such as involving mulheuristicle taps at different positions. All coordinate arguments required for the skill should be visible on the current screen. Imagine that when you start executing the skill, you are essentially blind.\n"
        prompt += f"Follow the example below to format the skill. Avoid adding comments that could cause errors with json.loads().\n {SKILL_EXMPALE}\n\n"
        return prompt

    def add_new_skill(self, skill_str: str, info_pool: InfoPool) -> str:
        if skill_str is None or skill_str == "None":
            return
        skill_object = extract_json_object(skill_str)
        if skill_object is None:
            print("Error! Invalid JSON for adding new skill: ", skill_str)
            return
        skill_name = skill_object["name"]
        if skill_name in info_pool.skills:
            print("Error! The skill already exists: ", skill_name)
            return
        info_pool.skills[skill_name] = skill_object
        print("Updated skills:", info_pool.skills)

    def parse_response(self, response: str) -> dict:
        new_skill = response.split("### New Skill ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"new_skill": new_skill}


class HeuristicsLearningCore(BaseAgent):
    def init_chat(self) -> list:
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant specializing in mobile phone operations. Your goal is to reflect on past experiences and provide insights to improve future interactions."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        prompt = "### Current Task ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### Overall Plan ###\n"
        prompt += f"{info_pool.plan}\n\n"

        prompt += "### Progress Status ###\n"
        prompt += f"{info_pool.progress_status}\n\n"
    
        prompt += "### Existing Heuristics from Past Experience ###\n"
        if info_pool.heuristics != "":
            prompt += f"{info_pool.heuristics}\n\n"
        else:
            prompt += "No heuristics recorded.\n\n"

        prompt += "### Full Action History ###\n"
        if info_pool.action_history != []:
            latest_actions = info_pool.action_history
            latest_summary = info_pool.summary_history
            action_outcomes = info_pool.action_outcomes
            error_descriptions = info_pool.error_descriptions
            progress_status_history = info_pool.progress_status_history
            for act, summ, outcome, err_des, progress in zip(latest_actions, latest_summary, action_outcomes, error_descriptions, progress_status_history):
                if outcome == "A":
                    prompt += f"- Action: {act} | Description: {summ} | Outcome: Successful | Progress: {progress}\n"
                else:
                    prompt += f"- Action: {act} | Description: {summ} | Outcome: Failed | Feedback: {err_des}\n"
            prompt += "\n"
        else:
            prompt += "No actions have been taken yet.\n\n"
            
        if len(info_pool.future_tasks) > 0:
            prompt += "---\n"
            # if the setting provides future tasks explicitly
            prompt += "### Future Tasks ###\n"
            prompt += "Here are some tasks that you might be asked to do in the future:\n"
            for task in info_pool.future_tasks:
                prompt += f"- {task}\n"
            prompt += "\n"

        prompt += "---\n"
        prompt += "Carefully reflect on the interaction history of the current task. Check if there are any general heuristics that might be useful for handling future tasks, such as advice on preventing certain common errors?\n\n"
        
        prompt += "### 失败与恢复分析 ###\n"
        prompt += "请重点分析失败案例和恢复过程，总结能提升稳定性的启发式规则。\n\n"
        prompt += "分析要点：\n"
        prompt += "1. 失败的主要原因\n"
        prompt += "2. 成功恢复的关键因素\n"
        prompt += "3. 如何在前置判断中规避失败\n"
        prompt += "4. 如何减少重复错误\n\n"

        prompt += "Provide your output in the following format:\n\n"

        prompt += "### Updated Heuristics ###\n"
        prompt += "If you have any important new heuristics to add (not already included in the existing heuristics), combine them with the current list. If there are no new heuristics, simply copy the existing heuristics here. Keep your heuristics concise and general.\n"
        return prompt

    def parse_response(self, response: str) -> dict:
        updated_heuristics = response.split("### Updated Heuristics ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        return {"updated_heuristics": updated_heuristics}


class ExperienceRetrieverSkill(BaseAgent):
    def init_chat(self) -> list:
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant specializing in mobile phone operations. Your goal is to select relevant skills from previous experience to the current task."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, instruction, skills) -> str:
        
        prompt = "### Existing Skills from Past Experience ###\n"
        for skill, value in skills.items():
            prompt += f"- Name: {skill} | Description: {value['description']}\n"
        
        prompt += "\n"
        prompt += "### Current Task ###\n"
        prompt += f"{instruction}\n\n"

        prompt += "---\n"
        prompt += "Carefully examine the information provided above to pick the skills that can be helpful to the current task. Remove skills that are irrelevant to the current task.\n"

        prompt += "Provide your output in the following format:\n\n"
        prompt += "### Selected Skills ###\n"
        prompt += "Provide your answer as a list of selected skill names: [\"skill1\", \"skill2\", ...]. If there are no relevant skills, put \"None\" here.\n"
        return prompt
    
    def parse_response(self, response: str) -> dict:
        selected_skills_str = response.split("### Selected Skills ###")[-1].replace("\n", " ").replace("  ", " ").strip()
        try:
            selected_skill_names = extract_json_object(selected_skills_str, json_type="list")
            selected_skill_names = [s.strip() for s in selected_skill_names]
        except:
            selected_skill_names = []
            
        return {"selected_skill_names": selected_skill_names}


class ExperienceRetrieverHeuristics(BaseAgent):
    def init_chat(self) -> list:
        operation_history = []
        sysetm_prompt = "You are a helpful AI assistant specializing in mobile phone operations. Your goal is to select relevant heuristics from previous experience to the current task."
        operation_history.append(["system", [{"type": "text", "text": sysetm_prompt}]])
        return operation_history

    def get_prompt(self, instruction, heuristics) -> str:
        prompt = "### Existing Heuristics from Past Experience ###\n"
        prompt += f"{heuristics}\n\n"
        
        prompt += "\n"
        prompt += "### Current Task ###\n"
        prompt += f"{instruction}\n\n"

        prompt += "---\n"
        prompt += "Carefully examine the information provided above to pick the heuristics that can be helpful to the current task. Remove heuristics that are irrelevant to the current task.\n"

        prompt += "Provide your output in the following format:\n\n"
        prompt += "### Selected Heuristics ###\n"
        prompt += "Heuristics that are generally useful and relevant to the current task. Feel free to reorganize the bullets. If there are no relevant heuristics, put \"None\" here.\n"

        return prompt
    
    def parse_response(self, response: str) -> dict:
        selected_heuristics = response.split("### Selected Heuristics ###")[-1].replace("\n", " ").replace("  ", " ").strip()        
        return {"selected_heuristics": selected_heuristics}

