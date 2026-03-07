# 项目总览与架构

## 关联阅读

- 深度总报告：[`deep-system-audit-report.md`](./deep-system-audit-report.md)
- Agent 深潜：[`agent-architecture-deep-dive.md`](./agent-architecture-deep-dive.md)
- 模块定位：[`module-locator-index.md`](./module-locator-index.md)

## 1. 项目定位

Uni-Mind 是一个“面向移动设备自动操作”的多智能体系统。输入是自然语言任务，输出是 Android 设备上的一系列 ADB 操作与任务日志。

核心目标：
- 理解当前屏幕（OCR + 图标检测 + 图标描述）
- 规划当前阶段目标（Planner）
- 生成并执行动作（Executor + ActionExecutor）
- 评估动作结果（VerifyCore）
- 记录关键信息并沉淀经验（Notetaker + Evolution）

## 2. 顶层架构

```text
run.py
  -> orchestrator.run_single_task(...)
      -> 感知层 Perceptor
      -> 决策层 Agent 集群
         - Planner
         - Executor
         - VerifyCore
         - Notetaker
         - SkillLearningCore / HeuristicsLearningCore
         - (可选) PlannerExecutor / QuickVerifier
      -> 执行层 Device Controller + ActionExecutor
      -> 记忆层 Skills/Heuristics（本地 + 持久化）
      -> 日志层 steps.json + 截图/录屏
```

## 3. 核心设计对象：InfoPool

`InfoPool` 是系统的共享状态中心，贯穿所有 Agent。它统一保存：
- 任务输入与知识：`instruction`、`heuristics`、`skills`
- 感知状态：`perception_infos_pre/post`、`keyboard_pre/post`、分辨率
- 执行历史：`action_history`、`action_outcomes`、`error_descriptions`
- 规划状态：`plan`、`current_subgoal`、`progress_status`
- 记忆与收束：`important_notes`、`finish_thought`

这使系统形成“同一事实源 + 多角色决策”的协作模型。

## 4. 两类运行模式

`run.py` 支持两种知识生命周期：
- `individual`：任务间不共享经验。
- `evolution`：任务间共享 `persistent_heuristics.txt` 和 `persistent_skills.json`，每个任务结束后增量更新。

此外还有两种策略开关（当前代码状态）：
- `enable_experience_retriever`：任务开始前，从已有经验中筛选相关 heuristics/skills。
- `USE_DUAL_TRACK`：快轨/专家轨双轨调度开关（当前代码默认 `False`，即仅专家轨）。

## 5. 设计特点

- 强可观测性：每轮都落盘 `steps.json`，且保留截图、动作和模型输出。
- 强容错：动作 JSON 先走规则修复，再可选调用轻量模型修复。
- 可进化：任务完成后将成功经验沉淀为“技能”和“启发式规则”。
- 可降级：快轨失败会回落到专家轨，保证任务鲁棒性。
