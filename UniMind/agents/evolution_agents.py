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
        
        # 双轨制系统技能学习
        prompt += "### 双轨制系统技能学习 ###\n"
        prompt += "请特别关注以下方面：\n"
        prompt += "1. 高速通道成功执行的操作序列，这些是高效技能的重要来源\n"
        prompt += "2. 专家轨道解决复杂问题的操作模式，这些可以转化为高级技能\n"
        prompt += "3. 两个轨道之间的切换点，这些地方往往需要特殊的技能组合\n"
        prompt += "4. 如何设计既能快速执行又能保证成功率的复合技能\n\n"

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
        
        # 双轨制系统特殊分析
        prompt += "### 双轨制系统分析 ###\n"
        prompt += "请重点分析那些导致从高速通道切换到专家会诊的失败案例，并总结出能避免未来发生类似切换的启发性规则。这些案例是我们学习和改进的关键。\n\n"
        
        prompt += "分析要点：\n"
        prompt += "1. 高速通道失败的原因分析\n"
        prompt += "2. 专家轨道成功的关键因素\n"
        prompt += "3. 如何优化高速通道以避免切换\n"
        prompt += "4. 双轨制系统的协同优化策略\n\n"

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


# 双轨制系统进化学习工具函数
def analyze_dual_track_performance(info_pool: InfoPool) -> dict:
    """分析双轨制系统的性能表现"""
    analysis = {
        "fast_track_success_rate": 0.0,
        "expert_track_usage": 0,
        "track_switches": 0,
        "learning_opportunities": []
    }
    
    # 分析轨道切换情况
    if hasattr(info_pool, 'action_history') and info_pool.action_history:
        total_actions = len(info_pool.action_history)
        successful_actions = sum(1 for outcome in info_pool.action_outcomes if outcome == "A")
        
        if total_actions > 0:
            analysis["fast_track_success_rate"] = successful_actions / total_actions
    
    # 识别学习机会
    if hasattr(info_pool, 'error_descriptions') and info_pool.error_descriptions:
        for error in info_pool.error_descriptions:
            if "高速通道" in error or "Fast Track" in error:
                analysis["learning_opportunities"].append({
                    "type": "fast_track_failure",
                    "description": error,
                    "suggestion": "优化高速通道决策逻辑"
                })
    
    return analysis


def generate_dual_track_insights(info_pool: InfoPool) -> str:
    """生成双轨制系统的洞察报告"""
    insights = []
    
    # 分析成功模式
    if hasattr(info_pool, 'action_history') and info_pool.action_history:
        successful_sequences = []
        current_sequence = []
        
        for i, outcome in enumerate(info_pool.action_outcomes):
            if outcome == "A":
                current_sequence.append(info_pool.action_history[i])
            else:
                if len(current_sequence) > 1:
                    successful_sequences.append(current_sequence)
                current_sequence = []
        
        if current_sequence and len(current_sequence) > 1:
            successful_sequences.append(current_sequence)
        
        if successful_sequences:
            insights.append(f"发现 {len(successful_sequences)} 个成功的操作序列")
    
    # 分析失败模式
    if hasattr(info_pool, 'error_descriptions') and info_pool.error_descriptions:
        error_patterns = {}
        for error in info_pool.error_descriptions:
            error_type = "未知错误"
            if "坐标" in error or "position" in error:
                error_type = "坐标错误"
            elif "文字" in error or "text" in error:
                error_type = "文字识别错误"
            elif "图标" in error or "icon" in error:
                error_type = "图标识别错误"
            
            error_patterns[error_type] = error_patterns.get(error_type, 0) + 1
        
        for error_type, count in error_patterns.items():
            insights.append(f"{error_type}: {count} 次")
    
    return "\n".join(insights) if insights else "暂无特殊洞察"


def optimize_dual_track_strategy(info_pool: InfoPool) -> dict:
    """优化双轨制策略"""
    optimization = {
        "fast_track_threshold": 0.8,  # 高速通道成功率阈值
        "expert_track_trigger": ["连续失败", "复杂操作", "未知状态"],
        "learning_focus": []
    }
    
    # 根据历史表现调整阈值
    if hasattr(info_pool, 'action_outcomes') and info_pool.action_outcomes:
        recent_outcomes = info_pool.action_outcomes[-10:]  # 最近10次操作
        if recent_outcomes:
            success_rate = sum(1 for o in recent_outcomes if o == "A") / len(recent_outcomes)
            if success_rate < 0.6:
                optimization["fast_track_threshold"] = 0.9  # 提高阈值
                optimization["learning_focus"].append("提高高速通道成功率")
            elif success_rate > 0.9:
                optimization["fast_track_threshold"] = 0.7  # 降低阈值
                optimization["learning_focus"].append("优化专家轨道使用策略")
    
    return optimization


# 测试函数
def test_dual_track_evolution():
    """测试双轨制进化学习系统"""
    print("=== 测试双轨制进化学习系统 ===")
    
    # 创建模拟的InfoPool
    from .base import InfoPool
    
    mock_info_pool = InfoPool(
        instruction="测试任务",
        action_history=[{"name": "Tap", "arguments": {"x": 100, "y": 200}}],
        action_outcomes=["A"],
        error_descriptions=["高速通道失败：坐标错误"],
        progress_status="进行中"
    )
    
    # 测试分析函数
    analysis = analyze_dual_track_performance(mock_info_pool)
    print(f"性能分析: {analysis}")
    
    # 测试洞察生成
    insights = generate_dual_track_insights(mock_info_pool)
    print(f"洞察报告: {insights}")
    
    # 测试策略优化
    optimization = optimize_dual_track_strategy(mock_info_pool)
    print(f"策略优化: {optimization}")
    
    print("双轨制进化学习系统测试完成")


if __name__ == "__main__":
    test_dual_track_evolution()

