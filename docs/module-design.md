# 模块设计详解

## 关联阅读

- Agent 深潜：[`agent-architecture-deep-dive.md`](./agent-architecture-deep-dive.md)
- 设计权衡：[`system-tradeoff-analysis.md`](./system-tradeoff-analysis.md)
- 模块定位：[`module-locator-index.md`](./module-locator-index.md)

## 1. Orchestrator（编排层）

职责：
- 统一调度 Agent、感知器、执行器
- 管理任务循环、终止条件、日志落盘
- 管理本地/持久化知识

关键实现点：
- `steps.json` 以“操作节点”为单位记录（perception/planning/action/verify/notetaking/finish）
- Notetaker 支持异步线程，并通过锁保护 `InfoPool` 更新
- 快轨失败自动回退专家轨

## 2. Agent 层

### 2.1 Planner
- 输入：指令、当前计划、进度、错误历史、重要笔记、技能描述
- 输出：`thought` + `plan` + `current_subgoal`
- 特性：当连续失败达到阈值时，会收到“可能卡住”提示并改计划

### 2.2 Executor
- 输入：目标子任务 + 感知元素 + 键盘状态 + heuristics + 历史动作
- 输出：动作 JSON + 描述 + 下一步依赖等级（High/Low）
- 设计：原子动作与技能动作共用同一接口

### 2.3 VerifyCore
- 输入：动作前后截图与结构化感知、动作预期
- 输出：
  - `A` 成功/部分成功
  - `B` 到了错误页面
  - `C` 基本无变化
- 同时更新 `progress_status`

### 2.4 Notetaker
- 输入：当前任务上下文 + 屏幕信息 + 既有笔记
- 输出：合并后的 `important_notes`
- 调度策略：
  - `High`：同步执行（阻塞主循环）
  - `Low`：异步执行（后台线程）

### 2.5 Evolution（学习）
- `SkillLearningCore`：从成功序列提取新技能（JSON 结构）
- `HeuristicsLearningCore`：更新通用启发式规则
- `ExperienceRetriever*`：任务前筛选相关经验，减少上下文噪声

## 3. 感知层（Perceptor）

处理链：
1. `get_screenshot` 拉取设备截图
2. OCR 检测+识别文本框
3. 文本块合并（纵向邻近合并）
4. GroundingDINO 检测 icon 框
5. 小框过滤（尺寸阈值）
6. 裁剪 icon 并用 VLM 生成描述
7. 输出统一结构：`[{text, coordinates(center)}...]`

输入输出设计：
- 输出坐标统一为中心点，便于直接 `Tap(x,y)`。
- 同时提供文字与图标描述，供 Planner/Executor 联合推理。

## 4. 执行层（Device + ActionExecutor）

### 4.1 Controller
- 原子 ADB 能力：`tap/swipe/type/back/home/enter/switch_app/long_press`
- 工具能力：截图拉取、录屏、输入法切换与 ADB Keyboard 激活

### 4.2 ActionExecutor
- 解析动作 JSON（增强版提取）
- 支持两类动作：
  - 原子动作：直接调用 controller
  - 技能动作：展开为原子动作序列执行
- 关键容错：
  - 本地规则修复 JSON（正则 + 智能修补）
  - 失败后可调用 LLM 修复 JSON 再执行

## 5. API 层（LLM/VLM 调用）

统一入口：`get_model_api_response`
- 支持 `OpenAI` 与 `SiliconFlow` 两种后端
- 消息格式兼容多模态（text + image_url）
- 可选 usage 追踪（token 与成本估算）

图标描述路径：
- 图标裁剪后并发调用 `process_image` -> `get_model_api_response`
