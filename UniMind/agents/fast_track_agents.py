# UniMind\agents\fast_track_agents.py
"""
高速通道智能体模块
实现PlannerExecutor一体化决策和QuickVerifier快速验证
"""
import os
from .base import BaseAgent, InfoPool, ATOMIC_ACTION_SIGNITURES
from UniMind.device.action_executor import execute, execute_atomic_action
from enum import Enum
import json
from PIL import Image
import imagehash
from UniMind.utils.api_client import get_model_api_response
from .utils.prompt_utils import add_response
import config

# 全局负向关键词列表，用于快速验证
NEGATIVE_KEYWORDS = [
    "error", "failed", "failure", "wrong", "incorrect", "invalid",
    "not found", "404", "500", "timeout", "connection failed",
    "permission denied", "access denied", "unauthorized",
    "network error", "server error", "system error"
]

class VerificationResult(Enum):
    """验证结果枚举"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    UNCERTAIN = "UNCERTAIN"

class PlannerExecutor(BaseAgent):
    """
    高速通道的一体化决策智能体
    融合了Planner和Executor的功能，实现快速决策
    """
    
    def __init__(self, adb_path):
        self.adb = adb_path
        # 调试开关
        self.enable_debug_log = True

    def init_chat(self):
        """初始化对话历史"""
        operation_history = []
        system_prompt = """You are a high-speed AI assistant for operating mobile phones. 
Your goal is to quickly analyze the current situation and make efficient decisions to complete user requests.
Think as if you are a human user operating the phone, but prioritize speed and efficiency over deep analysis.
You must output a valid JSON object with the exact structure specified."""
        operation_history.append(["system", [{"type": "text", "text": system_prompt}]])
        return operation_history

    def get_prompt(self, info_pool: InfoPool) -> str:
        """生成决策提示词，融合规划和执行的精华"""
        prompt = "### User Instruction ###\n"
        prompt += f"{info_pool.instruction}\n\n"

        prompt += "### Overall Plan ###\n"
        if info_pool.plan:
            prompt += f"{info_pool.plan}\n\n"
        else:
            prompt += "No plan yet. Create one based on the instruction.\n\n"

        prompt += "### Progress Status ###\n"
        if info_pool.progress_status:
            prompt += f"{info_pool.progress_status}\n\n"
        else:
            prompt += "No progress yet.\n\n"

        prompt += "### Current Subgoal ###\n"
        if info_pool.current_subgoal:
            prompt += f"{info_pool.current_subgoal}\n\n"
        else:
            prompt += "Determine the next subgoal.\n\n"

        prompt += "### Screen Information ###\n"
        prompt += (
            f"The attached image shows the current phone state. "
            f"Screen dimensions: {info_pool.width} x {info_pool.height} pixels.\n"
        )
        prompt += "Extracted screen elements (coordinates; content):\n"

        for clickable_info in info_pool.perception_infos_pre:
            if (clickable_info['text'] and 
                clickable_info['text'] != "icon: None" and 
                clickable_info['coordinates'] != (0, 0)):
                prompt += f"{clickable_info['coordinates']}; {clickable_info['text']}\n"
        prompt += "\n"

        prompt += "### Keyboard Status ###\n"
        if info_pool.keyboard_pre:
            prompt += "Keyboard is active - you can type.\n\n"
        else:
            prompt += "Keyboard is not active - you cannot type.\n\n"

        prompt += "### Available Actions ###\n"
        prompt += "#### Atomic Actions ####\n"
        if info_pool.keyboard_pre:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info_pool)}\n"
        else:
            for action, value in ATOMIC_ACTION_SIGNITURES.items():
                if "Type" not in action:
                    prompt += f"- {action}({', '.join(value['arguments'])}): {value['description'](info_pool)}\n"
            prompt += "NOTE: Cannot type - keyboard not active.\n"
        prompt += "\n"

        prompt += "#### Skills ####\n"
        if info_pool.skills:
            for skill, value in info_pool.skills.items():
                prompt += f"- {skill}({', '.join(value['arguments'])}): {value['description']} | Precondition: {value['precondition']}\n"
        else:
            prompt += "No skills available.\n"
        prompt += "\n"

        prompt += "### Recent Action History ###\n"
        if info_pool.action_history:
            num_actions = min(3, len(info_pool.action_history))
            latest_actions = info_pool.action_history[-num_actions:]
            latest_outcomes = info_pool.action_outcomes[-num_actions:]
            for act, outcome in zip(latest_actions, latest_outcomes):
                status = "✓" if outcome == "A" else "✗"
                prompt += f"{status} {act}\n"
        else:
            prompt += "No actions taken yet.\n"
        prompt += "\n"

        prompt += "### Heuristics ###\n"
        if info_pool.heuristics:
            prompt += f"{info_pool.heuristics}\n\n"
        else:
            prompt += "No heuristics available.\n\n"

        prompt += "### Important Notes ###\n"
        if info_pool.important_notes:
            prompt += f"{info_pool.important_notes}\n\n"
        else:
            prompt += "No important notes.\n\n"

        prompt += "---\n"
        prompt += "IMPORTANT: You must output a valid JSON object with the following exact structure:\n\n"
        prompt += "```json\n"
        prompt += "{\n"
        prompt += '  "thought": "Your detailed reasoning for the decision",\n'
        prompt += '  "updated_plan": "Updated high-level plan if needed, otherwise copy current plan",\n'
        prompt += '  "action_sequence": [\n'
        prompt += '    {\n'
        prompt += '      "name": "action_name",\n'
        prompt += '      "arguments": {"arg1": "value1", "arg2": "value2"},\n'
        prompt += '      "description": "What this action will do",\n'
        prompt += '      "success_checkpoint": {\n'
        prompt += '        "type": "text|icon|screen_change",\n'
        prompt += '        "value": "specific text/icon to look for",\n'
        prompt += '        "isPresent": true\n'
        prompt += '      }\n'
        prompt += '    }\n'
        prompt += '  ],\n'
        prompt += '  "next_step_dependency": "High|Low"\n'
        prompt += "}\n"
        prompt += "```\n\n"
        prompt += "CRITICAL REQUIREMENTS:\n"
        prompt += "1. action_sequence must be a list, even if only one action\n"
        prompt += "2. success_checkpoint must specify how to verify success\n"
        prompt += "3. Choose actions that maximize efficiency and minimize steps\n"
        prompt += "4. Use skills when possible, but verify preconditions\n"
        prompt += "5. Output ONLY valid JSON, no other text"

        return prompt

    def parse_response(self, response: str) -> dict:
        """解析LLM响应，提取决策信息"""
        try:
            # 尝试直接解析JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].strip()
            else:
                # 尝试找到JSON开始和结束
                start_idx = response.find("{")
                end_idx = response.rfind("}") + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                else:
                    raise ValueError("No JSON found in response")
            
            parsed = json.loads(json_str)
            
            # 验证必需字段
            required_fields = ["thought", "updated_plan", "action_sequence", "next_step_dependency"]
            for field in required_fields:
                if field not in parsed:
                    raise ValueError(f"Missing required field: {field}")
            
            # 验证action_sequence结构
            if not isinstance(parsed["action_sequence"], list):
                raise ValueError("action_sequence must be a list")
            
            for action in parsed["action_sequence"]:
                if not isinstance(action, dict):
                    raise ValueError("Each action must be a dictionary")
                if "name" not in action or "arguments" not in action:
                    raise ValueError("Each action must have 'name' and 'arguments' fields")
            
            return parsed
            
        except Exception as e:
            print(f"Failed to parse PlannerExecutor response: {e}")
            print(f"Raw response: {response}")
            # 返回默认值
            return {
                "thought": "Failed to parse response",
                "updated_plan": InfoPool.plan if hasattr(InfoPool, 'plan') else "",
                "action_sequence": [],
                "next_step_dependency": "High"
            }

    def decide(self, info_pool: InfoPool, screenshot_file: str = None):
        """快速决策接口"""
        prompt = self.get_prompt(info_pool)
        chat = self.init_chat()
        
        if screenshot_file:
            chat = add_response("user", prompt, chat, image=screenshot_file)
        else:
            chat = add_response("user", prompt, chat)
        
        # 使用配置的模型进行推理
        from config import models
        response = get_model_api_response(chat, model=models.EXECUTOR, temperature=0.0)
        
        if response:
            if getattr(self, 'enable_debug_log', False):
                print("[PlannerExecutor][RAW RESPONSE]:")
                print(response)
            parsed = self.parse_response(response)
            if getattr(self, 'enable_debug_log', False):
                print("[PlannerExecutor][PARSED]:", json.dumps(parsed, ensure_ascii=False, indent=2))
            return parsed
        else:
            raise Exception("Failed to get response from LLM")

    def execute(self, action_str: str, info_pool: InfoPool, **kwargs):
        """执行动作的接口，复用现有的action_executor逻辑"""
        return execute(self, action_str, info_pool, **kwargs)

    def execute_atomic_action(self, action: str, arguments: dict, **kwargs):
        """执行原子动作的接口"""
        return execute_atomic_action(self, action, arguments, **kwargs)
    
    def get_action_summary(self, action_sequence: list) -> str:
        """获取动作序列的摘要描述"""
        if not action_sequence:
            return "无动作"
        
        summaries = []
        for i, action in enumerate(action_sequence):
            action_name = action.get('name', 'Unknown')
            description = action.get('description', '无描述')
            summaries.append(f"{i+1}. {action_name}: {description}")
        
        return "\n".join(summaries)
    
    def validate_action_sequence(self, action_sequence: list) -> bool:
        """验证动作序列的有效性"""
        if not isinstance(action_sequence, list):
            return False
        
        for action in action_sequence:
            if not isinstance(action, dict):
                return False
            if 'name' not in action or 'arguments' not in action:
                return False
            if not isinstance(action['arguments'], dict):
                return False
        
        return True


class QuickVerifier:
    """
    快速验证器 - 两个轨道间的"扳道工"
    实现三层递进式校验逻辑
    """
    
    def __init__(self, perceptor=None):
        self.negative_keywords = NEGATIVE_KEYWORDS
        self.perceptor = perceptor  # 复用现有的Perceptor实例
        # 仅使用OCR进行快速验证，避免调用完整Perceptor的图标检测与Caption
        self._init_lightweight_ocr()

    def _init_lightweight_ocr(self):
        try:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks
            import config
            self.ocr_detection = pipeline(Tasks.ocr_detection, model=config.models.Perceptor.OCR_DETECTION_MODEL)
            self.ocr_recognition = pipeline(Tasks.ocr_recognition, model=config.models.Perceptor.OCR_RECOGNITION_MODEL)
            if getattr(self, 'perceptor', None) is not None:
                # 如果提供了Perceptor，将其OCR对象复用，避免重复加载
                self.ocr_detection = getattr(self.perceptor, 'ocr_detection', self.ocr_detection)
                self.ocr_recognition = getattr(self.perceptor, 'ocr_recognition', self.ocr_recognition)
        except Exception as e:
            print(f"QuickVerifier: Lightweight OCR init failed: {e}")
            self.ocr_detection = None
            self.ocr_recognition = None
    
    def verify(self, pre_screenshot_path: str, post_screenshot_path: str, 
               success_checkpoint: dict = None) -> VerificationResult:
        """
        三层递进式校验逻辑
        
        Args:
            pre_screenshot_path: 操作前截图路径
            post_screenshot_path: 操作后截图路径
            success_checkpoint: 成功检查点，包含type, value, isPresent
            
        Returns:
            VerificationResult: 验证结果
        """
        import time
        start_time = time.time()
        
        # 第一层：负向关键词校验
        negative_result = self._check_negative_keywords(post_screenshot_path)
        if negative_result:
            print(f"Quick Verifier: Negative keywords detected - {negative_result}")
            return VerificationResult.FAILED
        
        # 第二层：预期元素校验
        if success_checkpoint:
            checkpoint_result = self._check_success_checkpoint(post_screenshot_path, success_checkpoint)
            if checkpoint_result is not None:
                print(f"Quick Verifier: Checkpoint verification result - {checkpoint_result}")
                # 如果检查点验证失败，但屏幕确实发生了变化，仍然认为成功
                if checkpoint_result == VerificationResult.FAILED:
                    # 检查屏幕是否有变化
                    change_result = self._check_screen_changes(pre_screenshot_path, post_screenshot_path)
                    if change_result == VerificationResult.SUCCESS:
                        print(f"Quick Verifier: 检查点验证失败但屏幕有变化，认为操作成功")
                        return VerificationResult.SUCCESS
                return checkpoint_result
        
        # 第三层：屏幕变化校验
        change_result = self._check_screen_changes(pre_screenshot_path, post_screenshot_path)
        print(f"Quick Verifier: Screen change verification result - {change_result}")
        
        # 性能统计
        end_time = time.time()
        verification_time = end_time - start_time
        print(f"Quick Verifier: 验证耗时 {verification_time:.2f} 秒")
        
        # 生成验证报告
        self._generate_verification_report(pre_screenshot_path, post_screenshot_path, 
                                         success_checkpoint, change_result, verification_time)
        
        return change_result
    
    def _check_negative_keywords(self, screenshot_path: str) -> str:
        """检查负向关键词"""
        try:
            # 仅使用OCR提取文本，避免完整Perceptor
            texts = []
            if self.ocr_detection is None or self.ocr_recognition is None:
                return None
            from UniMind.perception.text_localization import ocr
            text_list, _ = ocr(screenshot_path, self.ocr_detection, self.ocr_recognition)
            for raw in text_list:
                if raw:
                    texts.append(raw.lower())
            # 检查所有提取的文字是否包含负向关键词
            for text in texts:
                for keyword in self.negative_keywords:
                    if keyword.lower() in text:
                        return f"检测到负向关键词: {keyword} in '{text}'"
            
            return None  # 没有检测到负向关键词
            
        except Exception as e:
            print(f"Error checking negative keywords: {e}")
            return None
    
    def _check_success_checkpoint(self, screenshot_path: str, 
                                 checkpoint: dict) -> VerificationResult:
        """检查成功检查点"""
        try:
            checkpoint_type = checkpoint.get("type", "")
            checkpoint_value = checkpoint.get("value", "")
            is_present = checkpoint.get("isPresent", True)
            
            if not checkpoint_type or not checkpoint_value:
                return None  # 无法验证，交给下一层
            
            # 根据检查点类型进行验证
            if checkpoint_type == "text":
                # 检查特定文字是否出现
                # 这里需要OCR实现
                detected = self._check_text_presence(screenshot_path, checkpoint_value)
                if detected == is_present:
                    return VerificationResult.SUCCESS
                else:
                    return VerificationResult.FAILED
                    
            elif checkpoint_type == "icon":
                # 检查特定图标是否出现
                # 这里需要图标检测实现
                detected = self._check_icon_presence(screenshot_path, checkpoint_value)
                if detected == is_present:
                    return VerificationResult.SUCCESS
                else:
                    return VerificationResult.FAILED
                    
            elif checkpoint_type == "screen_change":
                # 屏幕变化检查
                return None  # 交给下一层处理
                
            else:
                return None  # 未知类型，交给下一层
                
        except Exception as e:
            print(f"Error checking success checkpoint: {e}")
            return None
    
    def _check_text_presence(self, screenshot_path: str, text: str) -> bool:
        """检查特定文字是否出现"""
        try:
            # 仅使用OCR提取文本
            if self.ocr_detection is None or self.ocr_recognition is None:
                return False
            from UniMind.perception.text_localization import ocr
            text_list, _ = ocr(screenshot_path, self.ocr_detection, self.ocr_recognition)

            target_text = text.lower()
            detected_texts = [t.lower() for t in text_list if t]

            for detected_text in detected_texts:
                # 完全匹配
                if target_text in detected_text:
                    print(f"Quick Verifier: 文本检测成功 - 找到 '{text}' 在 '{detected_text}'")
                    return True
                # 部分匹配（至少包含目标文本的60%字符）
                if len(target_text) > 3:
                    common_chars = sum(1 for c in target_text if c in detected_text)
                    if common_chars / len(target_text) >= 0.6:
                        print(f"Quick Verifier: 文本部分匹配 - 目标 '{text}' 与检测 '{detected_text}' 匹配度 {common_chars/len(target_text):.2f}")
                        return True

            print(f"Quick Verifier: 文本检测失败 - 目标 '{text}' 未在检测文本中找到")
            print(f"Quick Verifier: 检测到的文本: {detected_texts[:5]}...")
            return False
            
        except Exception as e:
            print(f"Error checking text presence: {e}")
            return False
    
    def _check_icon_presence(self, screenshot_path: str, icon_description: str) -> bool:
        """检查特定图标是否出现"""
        try:
            # 仅使用OCR，不进行图标检测；此处退化为文本近似匹配
            if self.ocr_detection is None or self.ocr_recognition is None:
                return False
            from UniMind.perception.text_localization import ocr
            text_list, _ = ocr(screenshot_path, self.ocr_detection, self.ocr_recognition)
            target_description = icon_description.lower()
            for detected_text in [t.lower() for t in text_list if t]:
                if target_description in detected_text:
                    return True
            return False
            
        except Exception as e:
            print(f"Error checking icon presence: {e}")
            return False
    
    def _check_screen_changes(self, pre_screenshot_path: str, 
                             post_screenshot_path: str) -> VerificationResult:
        """检查屏幕变化"""
        try:
            # 使用imagehash进行图像相似度比较
            pre_image = Image.open(pre_screenshot_path)
            post_image = Image.open(post_screenshot_path)
            
            # 计算图像哈希
            pre_hash = imagehash.average_hash(pre_image)
            post_hash = imagehash.average_hash(post_image)
            
            # 计算哈希差异
            hash_diff = pre_hash - post_hash
            
            # 设置更宽松的阈值：差异小于2认为没有变化
            print(f"Quick Verifier: 屏幕变化检测 - 哈希差异: {hash_diff}")
            if hash_diff < 2:
                print(f"Quick Verifier: 屏幕变化检测失败 - 差异 {hash_diff} < 2")
                return VerificationResult.FAILED  # 没有变化，操作失败
            else:
                print(f"Quick Verifier: 屏幕变化检测成功 - 差异 {hash_diff} >= 2")
                return VerificationResult.SUCCESS  # 有变化，操作成功
                
        except Exception as e:
            print(f"Error checking screen changes: {e}")
            return VerificationResult.UNCERTAIN  # 无法确定，交给专家系统
    
    def _generate_verification_report(self, pre_screenshot_path: str, post_screenshot_path: str,
                                    success_checkpoint: dict, final_result: VerificationResult,
                                    verification_time: float):
        """生成详细的验证报告"""
        print(f"\n=== Quick Verifier 详细报告 ===")
        print(f"验证结果: {final_result.value}")
        print(f"验证耗时: {verification_time:.2f} 秒")
        
        if success_checkpoint:
            print(f"检查点类型: {success_checkpoint.get('type', 'N/A')}")
            print(f"检查点值: {success_checkpoint.get('value', 'N/A')}")
            print(f"期望出现: {success_checkpoint.get('isPresent', True)}")
        
        # 获取文件大小信息
        try:
            pre_size = os.path.getsize(pre_screenshot_path) if os.path.exists(pre_screenshot_path) else 0
            post_size = os.path.getsize(post_screenshot_path) if os.path.exists(post_screenshot_path) else 0
            print(f"截图文件大小 - 前: {pre_size} bytes, 后: {post_size} bytes")
        except:
            pass
        
        print(f"=== 报告结束 ===\n")


# 配置和工具函数
def get_fast_track_config():
    """获取高速通道的配置"""
    return {
        "max_sequence_length": 5,  # 最大动作序列长度
        "hash_threshold": 2,        # 图像哈希差异阈值（降低以提高灵敏度）
        "negative_keywords": NEGATIVE_KEYWORDS,
        "verification_timeout": 2.0,  # 验证超时时间（秒）
        "enable_async_logging": True,  # 启用异步日志
        "fallback_to_expert": True,    # 失败时回退到专家轨道
        "reuse_perceptor": True,       # 复用Perceptor实例以提高性能
        "text_match_threshold": 0.6,   # 文本匹配阈值（60%字符匹配即认为成功）
    }


def create_fast_track_agent(adb_path: str, config: dict = None, perceptor=None):
    """创建高速通道智能体的工厂函数"""
    if config is None:
        config = get_fast_track_config()
    
    planner_executor = PlannerExecutor(adb_path)
    quick_verifier = QuickVerifier(perceptor=perceptor)
    
    return planner_executor, quick_verifier


# 测试和调试函数
def test_quick_verifier():
    """测试快速验证器"""
    verifier = QuickVerifier()
    
    # 测试负向关键词检测
    test_keywords = ["error", "failed", "wrong"]
    print("测试负向关键词:", test_keywords)
    
    # 测试验证结果枚举
    results = [VerificationResult.SUCCESS, VerificationResult.FAILED, VerificationResult.UNCERTAIN]
    print("验证结果枚举:", [r.value for r in results])
    
    print("QuickVerifier测试完成")


if __name__ == "__main__":
    test_quick_verifier()