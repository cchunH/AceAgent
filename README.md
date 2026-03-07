# Uni-Mind 联通智核

## 项目概述

Uni-Mind 是一个基于大语言模型的智能移动设备操作代理系统，能够通过自然语言指令自动完成各种移动设备操作任务。该系统采用多智能体协作架构，具备感知、规划、执行、验证和学习等核心能力。

## 核心特性

- 🤖 **多智能体协作**: Planner、Executor、Perceptor、VerifyCore、Notetaker等智能体协同工作
- 🧠 **自进化学习**: 通过经验反思自动更新启发式规则和操作技能
- 📱 **多模态感知**: 结合OCR文字识别、图标检测和视觉语言模型理解屏幕内容
- 🔄 **智能规划**: 动态调整执行计划，处理异常情况和错误恢复
- 📊 **详细日志**: 完整的操作记录和截图保存，便于调试和分析

## 项目架构

```
Mobile-Agent-E/
├── run.py                 # 主程序入口
├── orchestrator.py        # 核心协调器，管理整个执行流程
├── config.py             # 配置管理，包含路径、API、模型等设置
├── requirements.txt      # 项目依赖
├── UniMind/             # 核心模块目录
│   ├── agents/          # 智能体实现
│   │   ├── base.py      # 基础智能体类和数据结构
│   │   ├── expert_track_agents.py  # 专家级智能体
│   │   ├── evolution_agents.py     # 进化学习智能体
│   ├── perception/      # 感知模块
│   │   ├── perceptor.py # 主感知器
│   │   ├── text_localization.py    # 文字定位
│   │   ├── icon_localization.py    # 图标定位
│   │   └── crop.py      # 图像裁剪处理
│   ├── device/          # 设备控制模块
│   │   ├── controller.py # 设备控制器
│   │   └── action_executor.py      # 动作执行器
│   └── utils/           # 工具函数
├── guiagent_v2/         # GUIAgent v2 运行时骨架（契约、事件、状态API）
├── logs/                # 日志输出目录
├── screenshot/          # 截图存储目录
└── temp/               # 临时文件目录
```

## 核心模块详解

### 1. 协调器 (Orchestrator)

**文件**: `orchestrator.py`

协调器是整个系统的核心，负责：
- 初始化所有智能体和环境
- 管理任务执行的主循环
- 协调各智能体之间的交互
- 处理任务完成条件和异常情况
- 管理日志记录和状态保存

**主要流程**:
```python
# 主执行循环
while True:
    # 1. 感知阶段
    perception_infos = perceptor.get_perception_infos()
    
    # 2. 规划阶段  
    plan, current_subgoal = planner.plan(info_pool)
    
    # 3. 执行阶段
    action_result = executor.execute(action)
    
    # 4. 验证阶段
    outcome = verify_core.verify(action_result)
    
    # 5. 学习阶段
    if task_completed:
        update_heuristics_and_skills()
```

### 2. 智能体系统 (Agents)

#### 2.1 规划器 (Planner)
**文件**: `UniMind/agents/expert_track_agents.py`

**职责**: 制定高层执行计划，分解复杂任务为子目标
**核心功能**:
- 首次规划：分析用户指令，制定完整计划
- 持续规划：根据执行进度调整计划
- 错误处理：当遇到连续失败时重新规划

**工作流程**:
```
用户指令 → 分析任务复杂度 → 制定高层计划 → 确定当前子目标
    ↓
执行监控 → 进度评估 → 计划调整 → 子目标更新
```

#### 2.2 执行器 (Executor)
**文件**: `UniMind/agents/expert_track_agents.py`

**职责**: 将抽象计划转换为具体操作，执行设备动作
**支持的操作类型**:
- `Tap(x, y)`: 点击指定坐标
- `Swipe(x1, y1, x2, y2)`: 滑动操作
- `Type(text)`: 文本输入
- `Back()`: 返回操作
- `Home()`: 返回主页
- `Open_App(app_name)`: 打开应用

**执行流程**:
```
当前子目标 → 分析屏幕状态 → 选择操作类型 → 生成操作指令 → 执行物理操作
```

#### 2.3 感知器 (Perceptor)
**文件**: `UniMind/perception/perceptor.py`

**职责**: 理解屏幕内容，提取可交互元素信息
**感知能力**:
- **OCR文字识别**: 提取屏幕上的文字内容和坐标
- **图标检测**: 使用GroundingDINO检测图标位置
- **图标描述**: 使用VLM为图标生成文字描述

**输出格式**:
```json
{
  "text": "按钮文字",
  "coordinates": [x, y],
  "type": "button",
  "description": "可点击的按钮"
}
```

#### 2.4 验证核心 (VerifyCore)
**文件**: `UniMind/agents/expert_track_agents.py`

**职责**: 验证操作结果，评估任务进度
**验证结果**:
- **A (Success)**: 操作成功，结果符合预期
- **B (Wrong Page)**: 操作导致错误页面，需要返回
- **C (No Change)**: 操作无效果，需要调整策略

#### 2.5 记录员 (Notetaker)
**文件**: `UniMind/agents/expert_track_agents.py`

**职责**: 记录重要信息，为后续操作提供上下文
**记录内容**:
- 关键页面信息
- 重要数据内容
- 操作结果摘要

### 3. 进化学习系统

#### 3.1 技能学习核心 (SkillLearningCore)
**文件**: `UniMind/agents/evolution_agents.py`

**功能**: 从成功操作中学习新的复合技能
**学习机制**:
- 分析成功的操作序列
- 提取可复用的操作模式
- 生成带前置条件的技能描述

#### 3.2 启发式学习核心 (HeuristicsLearningCore)
**文件**: `UniMind/agents/evolution_agents.py`

**功能**: 更新操作启发式规则
**学习内容**:
- 常见错误的避免方法
- 高效操作的策略
- 特定场景的最佳实践

#### 3.3 经验检索器 (ExperienceRetriever)
**文件**: `UniMind/agents/evolution_agents.py`

**功能**: 根据当前任务检索相关的历史经验
**检索策略**:
- 基于任务相似性选择技能
- 根据上下文筛选启发式规则
- 动态调整经验权重

### 4. 设备控制模块

#### 4.1 设备控制器 (Controller)
**文件**: `UniMind/device/controller.py`

**功能**: 管理ADB连接和设备状态
**主要能力**:
- ADB设备连接管理
- 屏幕截图获取
- 屏幕录制控制
- 输入法状态管理

#### 4.2 动作执行器 (ActionExecutor)
**文件**: `UniMind/device/action_executor.py`

**功能**: 执行具体的设备操作
**执行方式**:
- 原子操作：直接ADB命令
- 复合技能：预定义操作序列
- 智能修复：JSON格式错误自动修复

### 5. GUIAgent v2 运行时（进行中）

**目录**: `guiagent_v2/runtime/`

当前已落地能力：
- `orchestrator_v2.py`: `runtime_mode=legacy|guiagent_v2_shadow|guiagent_v2` 统一入口与事件翻译。
- `event_bus.py` + `status_api.py`: `events.jsonl` 结构化事件与任务状态查询（支持 `session_id` 聚合与过滤）。
- `event_schema.py`: Typed Event Schema（`v1`）与运行时事件字段校验。
- `web_skill_router.py`: `mobile_native/web_skill` 路由决策（移动端系统动作优先走原生链路）。
- `agent_browser_skill.py`: `agent-browser` 外部进程适配器与 `AgentBrowserSkill` 封装。
- `action_registry.py`: 动作注册、参数校验、分发统一入口。
- `guard_policy.py`: 执行前 allow/deny/confirm 门禁决策。
- `policy_loader.py`: GuardPolicy 文件化配置加载与缓存重载。
- `v2_executor.py`: `guiagent_v2(_shadow)` probe 执行链（含 web fallback 到 mobile_native）。
- `loop_detector.py` + `context_compaction.py`: 循环检测与上下文压缩治理能力。
- `task_service.py` + `session_runtime.py`: 任务提交、状态查询、会话级隔离调度（进程内 v0）。
- `session_runtime_server.py`: SessionRuntime 本地 HTTP IPC 控制面（session/task/status/timeline）。
- `session_runtime.py`: 支持会话/任务索引持久化恢复（重启后恢复 session/task 查询能力）。
- `watchdogs/*`: `crash_watchdog/security_watchdog` 插件骨架与 `watchdog_alert` 派生事件。
- `watchdog_policy.py`: Watchdog 策略加载与热更新（启停、最小严重级、去重节流参数）。

当前路由可观测字段：
- `channel`
- `route_reason`
- `skill_name`
- `session_id`

当前新增事件：
- `skill_route`
- `skill_fallback`
- `guard_decision`
- `adapter_call`
- `loop_warning`
- `context_compaction`
- `watchdog_alert`

可选运行参数（v2）：
- `--v2_skip_legacy`
- `--guard_policy_path`
- `--guard_policy_reload_interval`
- `--watchdog_policy_path`
- `--watchdog_policy_reload_interval`
- `--session_id`
- `--start_session_runtime_server`
- `--session_runtime_server_host`
- `--session_runtime_server_port`
- `--session_runtime_state_path`

## 工作流程详解

### 1. 系统初始化流程

```
启动程序 → 解析命令行参数 → 加载配置文件 → 初始化模型API
    ↓
创建日志目录 → 加载持久化知识 → 初始化智能体实例 → 连接移动设备
```

### 2. 单任务执行流程

```
接收用户指令
    ↓
初始化信息池 (InfoPool)
    ↓
加载历史启发式和技能
    ↓
开始任务执行循环 (最大40次迭代)
    ↓
感知阶段 → 规划阶段 → 执行阶段 → 验证阶段 → 学习阶段
    ↓
任务完成或达到终止条件
    ↓
保存日志和截图 → 更新持久化知识
```

### 3. 多任务执行流程

**Individual模式**: 每个任务独立执行，不共享经验
**Evolution模式**: 任务间共享持久化记忆，持续更新知识

```
任务1 → 执行完成 → 更新启发式和技能 → 保存到持久化文件
    ↓
任务2 → 加载更新后的知识 → 执行完成 → 进一步更新知识
    ↓
... → 知识持续进化
```

### 4. 智能体协作流程

```
Planner制定计划
    ↓
Perceptor感知屏幕
    ↓
Executor选择并执行操作
    ↓
VerifyCore验证结果
    ↓
Notetaker记录重要信息
    ↓
学习核心更新知识
    ↓
返回规划阶段
```

## 配置说明

### 环境变量配置

```bash
# API提供商选择
export BACKBONE_TYPE="SiliconFlow"  # 或 "OpenAI"

# API密钥配置
export SILICONFLOW_API_KEY="your_key_here"
export OPENAI_API_KEY="your_key_here"

# 模型配置
export PLANNER_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
export EXECUTOR_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
export VERIFIER_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"

# ADB路径配置
export ADB_PATH="/path/to/adb"
```

### 配置文件结构

```python
# config.py 中的主要配置项
class Paths:
    ADB_PATH = "adb"              # ADB可执行文件路径
    TEMP_DIR = "temp"             # 临时文件目录
    SCREENSHOT_DIR = "screenshot" # 截图目录
    LOG_ROOT = "logs"             # 日志根目录

class Models:
    # 不同智能体使用的模型配置
    PLANNER = "Qwen/Qwen2.5-VL-32B-Instruct"
    EXECUTOR = "Qwen/Qwen2.5-VL-32B-Instruct"
    VERIFIER = "Qwen/Qwen2.5-VL-32B-Instruct"
```

