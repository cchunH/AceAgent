# config.py
"""
Umi-Mind 联通智核 - 统一配置中心

该文件集中管理项目的所有可配置项，包括：
1.  系统路径 (Paths)
2.  外部API与密钥 (API)
3.  AI模型选型 (Models)
4.  智能体行为与初始化设置 (AgentSettings)

通过分离配置与逻辑，实现代码的整洁、可维护和可扩展。
"""

import os

import torch

# --- 核心环境设置 ---
# 解决Hugging Face Tokenizers的并行处理警告，建议在项目启动时最先设置
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class Paths:
    """管理所有文件系统路径"""
    # ADB 可执行文件的路径，优先从环境变量读取
    ADB_PATH = os.environ.get("ADB_PATH", default="adb")
    
    # 运行时生成的临时文件目录
    TEMP_DIR = "temp"
    
    # 运行时生成的截图文件目录
    SCREENSHOT_DIR = "screenshot"
    
    # 所有任务日志的根目录
    LOG_ROOT = "logs"
    
    # (可选) API用量追踪日志的路径
    USAGE_TRACKING_JSONL = None  # 例如 "usage_tracking.jsonl"


class API:
    """管理所有外部API的配置、密钥和端点"""
    # --- 主干模型提供商选择 ---
    # 可选项: "SiliconFlow", "OpenAI"
    # 这是控制所有模型来源的总开关，优先从环境变量读取
    BACKBONE_TYPE = os.environ.get("BACKBONE_TYPE", default="SiliconFlow")
    
    # --- API 密钥管理 ---
    # 将密钥存储在字典中，便于管理和扩展
    _API_KEYS = {
        "OpenAI": os.environ.get("OPENAI_API_KEY", default=None),
        "SiliconFlow": os.environ.get("SILICONFLOW_API_KEY", default="sk-fgxeqnapytlhmpyfnkpvlpkkpqzcfaoofyxdpuveuxuvsmvy") # 示例密钥
    }

    # --- API 端点管理 ---
    _API_URLS = {
        "OpenAI": "https://api.openai.com/v1/chat/completions",
        "SiliconFlow": "https://api.siliconflow.cn/v1/chat/completions"
    }

    @property
    def key(self):
        """根据主干类型，获取当前应使用的API密钥"""
        return self._API_KEYS.get(self.BACKBONE_TYPE)

    @property
    def url(self):
        """根据主干类型，获取当前应使用的API端点"""
        return self._API_URLS.get(self.BACKBONE_TYPE)


class Models:
    """
    管理各个智能体角色所使用的具体AI模型。
    通过这种方式，可以为不同任务强度的角色配置不同规模的模型，实现“大小核”策略。
    """
    _api_provider = API.BACKBONE_TYPE
    
    # --- 为不同提供商定义模型集 ---
    _openai_models = {
        "PLANNER": os.environ.get("PLANNER_MODEL", "gpt-4o"),
        "EXECUTOR": os.environ.get("EXECUTOR_MODEL", "gpt-4o"),
        "VERIFIER": os.environ.get("VERIFIER_MODEL", "gpt-4o"),
        "NOTETAKER": os.environ.get("NOTETAKER_MODEL", "gpt-4o"),
        "EVOLUTION": os.environ.get("EVOLUTION_MODEL", "gpt-4o"),
        "JSON_REPAIR": os.environ.get("JSON_REPAIR_MODEL", "gpt-4o-mini"),
        "FAST_TRACK_EXECUTOR": os.environ.get("FAST_TRACK_EXECUTOR_MODEL", "gpt-4o"),
        "DEFAULT": "gpt-4o"
    }
    
    _siliconflow_models = {
        "PLANNER": os.environ.get("PLANNER_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct"),
        "EXECUTOR": os.environ.get("EXECUTOR_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct"),
        "VERIFIER": os.environ.get("VERIFIER_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct"),
        "NOTETAKER": os.environ.get("NOTETAKER_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct"),
        "EVOLUTION": os.environ.get("EVOLUTION_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
        "JSON_REPAIR": os.environ.get("JSON_REPAIR_MODEL", "Qwen/Qwen3-8B"),
        "FAST_TRACK_EXECUTOR": os.environ.get("FAST_TRACK_EXECUTOR_MODEL", "Qwen/Qwen2.5-VL-32B-Instruct"),
        "DEFAULT": "Qwen/Qwen2.5-VL-32B-Instruct"
    }
    
    @property
    def _current_models(self):
        """根据API提供商，选择当前使用的模型集"""
        if self._api_provider == "SiliconFlow":
            return self._siliconflow_models
        elif self._api_provider == "OpenAI":
            return self._openai_models
        else:
            raise ValueError(f"未知的API提供商: {self._api_provider}")

    @property
    def PLANNER(self): return self._current_models["PLANNER"]
    
    @property
    def EXECUTOR(self): return self._current_models["EXECUTOR"]
    
    @property
    def VERIFIER(self): return self._current_models["VERIFIER"]
    
    @property
    def NOTETAKER(self): return self._current_models["NOTETAKER"]
    
    @property
    def EVOLUTION(self): return self._current_models["EVOLUTION"]
    
    @property
    def JSON_REPAIR(self): return self._current_models["JSON_REPAIR"]
    
    @property
    def FAST_TRACK_EXECUTOR(self): return self._current_models["FAST_TRACK_EXECUTOR"]
    
    @property
    def DEFAULT(self): return self._current_models["DEFAULT"]

    class Perceptor:
        """
        专门存放Perceptor所需的所有底层模型配置。
        这是一个嵌套类，逻辑上属于Models的一部分。
        """
        # Captioning (图标描述) 模型的调用方式 ("api" 或 "local")
        CAPTION_CALL_METHOD = "api"
        
        # Captioning (图标描述) 模型的具体名称
        # 注意：这里的模型名称可能包含"Pro/"前缀，代表专业版或特定版本
        CAPTION_MODEL = "Pro/Qwen/Qwen2.5-VL-7B-Instruct"

        # Icon Detection (图标检测) 模型
        GROUNDINGDINO_MODEL = "AI-ModelScope/GroundingDINO"
        GROUNDINGDINO_REVISION = "v1.0.0"

        # OCR (文字识别) 模型
        OCR_DETECTION_MODEL = "iic/cv_resnet18_ocr-detection-db-line-level_damo"
        OCR_RECOGNITION_MODEL = "iic/cv_convnextTiny_ocr-recognition-document_damo"

        # 硬件设备 ("cuda" 或 "cpu")
        DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

        def to_dict(self):
            """将所有Perceptor配置项转换为字典，便于传递"""
            return {
                "device": self.DEVICE,
                "caption_call_method": self.CAPTION_CALL_METHOD,
                "caption_model": self.CAPTION_MODEL,
                "groundingdino_model": self.GROUNDINGDINO_MODEL,
                "groundingdino_revision": self.GROUNDINGDINO_REVISION,
                "ocr_detection_model": self.OCR_DETECTION_MODEL,
                "ocr_recognition_model": self.OCR_RECOGNITION_MODEL,
            }


    # 在Models类中，实例化这个嵌套类，方便外部调用
    perceptor = Perceptor()



class AgentSettings:
    """管理智能体的行为、初始化知识等设置"""
    
    # 用户提供的、智能体的初始启发性规则 (Heuristics)
    INIT_HEURISTICS = """0. Do not add any payment information. If you are asked to sign in, ignore it or sign in as a guest if possible. Close any pop-up windows when opening an app.
1. By default, no APPs are opened in the background.
2. Screenshots may show partial text in text boxes from your previous input; this does not count as an error.
3. When creating new Notes, you do not need to enter a title unless the user specifically requests it.
"""
    
    # 每一步物理操作之间的固定等待时间（秒）
    SLEEP_BETWEEN_STEPS = 1

# --- 实例化配置对象，供其他模块导入和使用 ---
paths = Paths()
api = API()
models = Models()
settings = AgentSettings()

# --- 打印当前配置，便于调试 ---
print("### Using BACKBONE_TYPE:", api.BACKBONE_TYPE)
print("### Model Configuration:")
print(f"  - Planner: {models.PLANNER}")
print(f"  - Executor: {models.EXECUTOR}")
print(f"  - Verifier: {models.VERIFIER}")
print(f"  - Notetaker: {models.NOTETAKER}")
print(f"  - Evolution Engine: {models.EVOLUTION}")
print(f"  - JSON Repair: {models.JSON_REPAIR}")
print(f"  - Fast Track Executor: {models.FAST_TRACK_EXECUTOR}")
print(f"  - Perceptor Caption Model: {models.Perceptor.CAPTION_MODEL}")