
import json
import re
from UniMind.agents.base import BaseAgent

class JSONRepairAgent(BaseAgent):
    """专门负责修复JSON格式错误的Agent"""
    
    def init_chat(self) -> list:
        operation_history = []
        system_prompt = (
            "You are a JSON repair specialist. Your goal is to fix malformed JSON strings "
            "based on the expected format and atomic action signatures. You should output "
            "only valid JSON without any additional text or explanation."
        )
        operation_history.append(["system", [{"type": "text", "text": system_prompt}]])
        return operation_history
    
    def get_prompt(self, broken_json: str, atomic_actions: dict) -> str:
        prompt = "### Broken JSON ###\n"
        prompt += f"The following JSON string is malformed and needs to be fixed:\n"
        prompt += f"```\n{broken_json}\n```\n\n"
        
        prompt += "### Expected Format ###\n"
        prompt += "The JSON should follow this format:\n"
        prompt += '{"name": "ActionName", "arguments": {"param1": value1, "param2": value2}}\n\n'
        
        prompt += "### Available Atomic Actions ###\n"
        prompt += "The action name must be one of the following, with the correct arguments:\n"
        for action, info in atomic_actions.items():
            args_str = ", ".join(info['arguments']) if info['arguments'] else "no arguments"
            prompt += f"- {action}({args_str})\n"
        prompt += "\n"
        
        prompt += "### Common Issues to Fix ###\n"
        prompt += "- Missing or extra quotes\n"
        prompt += "- Missing or extra commas\n"
        prompt += "- Unclosed brackets or braces\n"
        prompt += "- Incorrect argument names or types\n"
        prompt += "- Line breaks within strings\n\n"
        
        prompt += "### Instructions ###\n"
        prompt += "Please fix the broken JSON and return ONLY the corrected JSON string. "
        prompt += "Do not include any explanations, comments, or additional text. "
        prompt += "The output should be a single line of valid JSON.\n"
        
        return prompt
    
    def parse_response(self, response: str) -> dict:
        # 清理响应，移除可能的额外文本
        response = response.strip()
        
        # 尝试提取JSON
        try:
            # 首先尝试直接解析
            return {"repaired_json": json.loads(response)}
        except json.JSONDecodeError:
            # 如果失败，尝试提取JSON部分
            json_match = re.search(r'({.*})', response, re.DOTALL)
            if json_match:
                try:
                    return {"repaired_json": json.loads(json_match.group(1))}
                except json.JSONDecodeError:
                    pass
        
        return {"repaired_json": None}