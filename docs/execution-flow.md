# 任务执行流程（端到端）

## 1. 入口流程

`run.py` 负责参数解析与模式分发：
- 单任务：`--instruction`
- 多任务：`--tasks_json`
- 经验模式：`--setting individual|evolution`
- 其余控制：`max_itr`、失败阈值、是否检索经验、是否录屏等

最终都进入 `orchestrator.run_single_task(...)`。

## 2. 初始化阶段

`run_single_task` 初始化顺序：
1. 构建日志目录：`logs/<model>/unimind_agent/<run_name>/<task_id>/`
2. 读取初始知识（优先级）：
   - 显式 `skills_path / heuristics_path`
   - 否则持久化路径
   - 否则内置默认值
3. 可选经验检索：筛选与当前任务相关的 skills/heuristics
4. 初始化 `InfoPool`
5. 初始化 Agent 与感知器（若外部未传 Perceptor）
6. 写入 `steps.json` 的 `init` 记录

## 3. 主循环状态机

每轮迭代执行如下步骤：

1. 终止条件检查
   - 迭代数达到 `max_itr`
   - 最近 `max_consecutive_failures` 次结果均是 `B/C`
   - 最近 `max_repetitive_actions` 次动作完全重复（`Swipe/Back` 例外）

2. 主感知（Perception Pre）
   - 拉取截图
   - OCR + 图标检测 + 图标描述
   - 写入 `info_pool.perception_infos_pre`
   - 保存当前截图到日志目录

3. 轨道决策
   - 若 `USE_DUAL_TRACK=True`：先走快轨，失败再回退专家轨
   - 若 `False`：直接进入专家轨

4. 专家轨执行（默认路径）
   - Planner 产出：`plan/current_subgoal`
   - 若 `current_subgoal` 含 `Finished`：
     - 触发技能学习与启发式学习
     - 写回本地与持久化知识
     - `finish`
   - 否则 Executor 产出动作 JSON 并执行
   - 执行后再次感知（Perception Post）
   - VerifyCore 基于前后截图输出 `A/B/C + error/progress`
   - Notetaker 记录重要信息（High 同步 / Low 异步）
   - 休眠 `SLEEP_BETWEEN_STEPS` 后进入下一轮

## 4. 快轨（可选）流程

当 `USE_DUAL_TRACK=True` 时：
1. `PlannerExecutor` 一次性输出 `action_sequence`
2. 每个动作执行后用 `QuickVerifier` 快速验证：
   - 负向关键词检测
   - 成功检查点检测（文本/图标/屏幕变化）
   - 图像哈希差异兜底
3. 任一动作失败则切回专家轨
4. 快轨序列成功则继续下一轮；若命中终局检查点可直接完成任务

## 5. 结束与落盘

任务结束时统一记录：
- `finish_flag`（如 `expert_success/max_iteration/abnormal`）
- `final_info_pool`
- `task_duration`

并在需要时更新：
- `persistent_heuristics.txt`
- `persistent_skills.json`

