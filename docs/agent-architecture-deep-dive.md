# Agent 架构深潜（职责边界 / 契约 / 协作协议）

本文按统一六段模板拆解关键 Agent 与共享状态：`职责`、`上游输入`、`核心机制`、`下游影响`、`优点`、`缺点/风险`。

---

## 1. 共享状态中心：InfoPool（`UniMind/agents/base.py`）

### 职责
- 作为多 Agent 共享事实源，承载任务上下文、执行历史、感知状态和记忆状态。

### 上游输入
- `run.py` 初始化指令与经验。
- `Perceptor` 写入 pre/post 感知结果。
- `Executor/VerifyCore/Notetaker` 写入动作与反思数据。

### 核心机制
- 字段覆盖“计划-执行-验证-记忆”闭环。
- 通过单对象引用降低状态复制开销。

### 下游影响
- 决定 Planner/Executor/Verify 的推理上下文质量。

### 优点
- 状态统一，协作简单。

### 缺点/风险
- 字段较多且语义依赖隐式约定，缺 schema 校验。

---

## 2. Planner（`UniMind/agents/expert_track_agents.py`）

### 职责
- 生成/更新高层计划与当前子目标。

### 上游输入
- `instruction`、现有计划、进度状态、错误历史、重要笔记、技能列表。

### 核心机制
- 首轮规划与续航规划采用不同 Prompt。
- 连续失败时触发“可能卡住”分支，允许重规划。

### 下游影响
- 直接约束 Executor 的动作选择空间与方向。

### 优点
- 对错误场景有主动重规划策略。

### 缺点/风险
- 输出依赖字符串分段解析，格式漂移会导致解析失败。

---

## 3. Executor（`UniMind/agents/expert_track_agents.py` + `UniMind/device/action_executor.py`）

### 职责
- 将当前子目标转换为单步动作（原子/技能）并执行。

### 上游输入
- 感知结果、键盘状态、计划状态、历史动作、heuristics、skills。

### 核心机制
- 先由 LLM 生成动作 JSON，再由 ActionExecutor 解析并执行。
- 内置 `next_step_dependency`，用于决定 Notetaker 同步/异步策略。

### 下游影响
- 驱动设备状态变化，影响 VerifyCore 判定结果与后续规划。

### 优点
- 技能机制能复用成功序列，降低多步重复决策成本。

### 缺点/风险
- 动作 JSON 质量强依赖模型稳定性，修复链虽存在但增加复杂度。

---

## 4. VerifyCore（`UniMind/agents/expert_track_agents.py`）

### 职责
- 判断动作结果是否符合预期，并更新进度描述。

### 上游输入
- pre/post 截图、感知前后信息、最后动作与预期描述。

### 核心机制
- 输出三分类 `A/B/C` 与 `error_description`、`progress_status`。

### 下游影响
- 直接影响重复失败阈值、Planner 是否重规划、任务是否收敛。

### 优点
- 将“动作正确性”与“任务进度”同时纳入反馈。

### 缺点/风险
- 与 Executor 一样依赖字符串协议解析，结构脆弱。

---

## 5. Notetaker（`UniMind/agents/expert_track_agents.py`）

### 职责
- 提取并维护任务相关的重要屏幕信息（非低层动作）。

### 上游输入
- 当前计划、当前子目标、进度、既有重要笔记、post 感知/截图。

### 核心机制
- 由 `next_step_dependency` 控制执行模式：
- `High` 同步，`Low` 异步线程执行。

### 下游影响
- 影响 Planner 的上下文质量与后续决策准确率。

### 优点
- 在保证关键信息完整性的同时兼顾吞吐。

### 缺点/风险
- 异步线程收尾一致性不足，存在状态更新时序风险。

---

## 6. Evolution Agent（`UniMind/agents/evolution_agents.py`）

### 职责
- 任务后学习新技能/规则，任务前检索相关经验。

### 上游输入
- 全量行动历史、结果、进度轨迹、未来任务（可选）。

### 核心机制
- 学习器输出 `new_skill` 与 `updated_heuristics`。
- 检索器裁剪当前任务所需经验子集。

### 下游影响
- 决定后续任务的初始知识质量与执行效率。

### 优点
- 形成跨任务记忆闭环。

### 缺点/风险
- 经验质量无强约束，长期运行可能出现噪声累积。

---

## 7. Fast Track Agent（`UniMind/agents/fast_track_agents.py`）

### 职责
- 一体化输出动作序列并快速验证，失败时回退专家轨。

### 上游输入
- 与专家轨类似的上下文，但压缩为单次一体决策。

### 核心机制
- `PlannerExecutor` 产出 `action_sequence + success_checkpoint`。
- `QuickVerifier` 三层验证：负向关键词 -> 检查点 -> 屏幕变化哈希。

### 下游影响
- 成功时减少循环轮次；失败时增加回退复杂度。

### 优点
- 潜在高效率，尤其适用于流程清晰的短路径任务。

### 缺点/风险
- 当前默认关闭且协议复杂，治理成本高于专家轨。

---

## 8. 协作协议摘要

- 专家轨协议：`Thought/Plan/Subgoal`、`Thought/Action/Description/Dependency`、`Outcome/Error/Progress`。
- 快轨协议：严格 JSON（thought/updated_plan/action_sequence/next_step_dependency）。
- 执行协议：统一动作对象 `{name, arguments}`，支持原子动作与技能动作。

建议：将上述协议统一为结构化 schema，并在编排层集中做校验与错误分类。

