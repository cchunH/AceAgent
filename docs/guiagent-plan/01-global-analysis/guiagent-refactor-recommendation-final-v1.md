# GUIAgent 改造正式推荐与迁移说明（v1）

目标：给出已落地改造的正式推荐方案，作为后续状态面/动作面增强与前端控制面的统一基线。

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0 -> Phase 1`

## 1. 当前推荐架构（已落地）

1. 运行模式分流：`legacy | guiagent_v2_shadow | guiagent_v2`
2. 契约层：`IntentKey + ExecutionRequest + ExecutionResult`，并保留 legacy action 映射
3. 运行时骨架：`map -> pre_assertion hook -> execute(shadow no-op) -> post_check hook`
4. 观测层：`events.jsonl` 统一字段，保留 `steps.json` 兼容
5. 控制面预留：进程内状态 API（任务状态与时间线查询）

## 2. 迁移要点

1. 启动方式保持 `run.py`，新增参数：
- `--runtime_mode legacy|guiagent_v2_shadow|guiagent_v2`

2. 兼容策略：
- `legacy`：继续走原专家轨执行链
- `guiagent_v2_shadow/guiagent_v2`：先写统一事件并委托 legacy 执行，确保可运行

3. 日志策略：
- 继续输出 `steps.json`
- 新增 `events.jsonl`（推荐后续评估以该文件为主）

## 3. 快轨下线结论

1. 已移除快轨调度入口与相关实现文件
2. 主链只保留统一专家轨执行路径
3. 后续优化应在 `guiagent_v2` 模块内演进，不再回填快轨分支

## 3.1 Hook 现状

1. 已接入默认 `semantic_pre_assertion_hook` 与 `post_state_check_hook`
2. legacy 回放时会基于 `perception_infos_pre/post` 生成 `assertion/post_check` 事件
3. 当前为规则型实现，后续可替换为模型判定或拓扑匹配判定

## 3.2 状态面/动作面进展

1. `state_engine` 已实现 `anchor_extractor + topology_matcher`（Top/Bottom 优先锚点策略）
2. `action_engine` 已实现 `run_pre_assertion + run_post_check`，并接入 runtime 事件翻译链
3. `affine_runtime` 已实现屏幕缩放投射（Tap/Long_press/Swipe）

## 3.3 复用桥接进展

1. 已新增 `brain_adapter/planner_bridge.py` 与 `executor_bridge.py`
2. 通过桥接层复用原项目 `Planner/Executor` 能力，避免重复建设

## 3.4 蓝图与报告进展

1. 已新增 `blueprint_hub` 本地仓（`blueprints.json`），支持增量 patch
2. 运行时已接入观测回灌：动作后会更新蓝图锚点和后置期望
3. 每次任务结束自动输出 `runtime_summary.json`（指标与蓝图计数）

## 4. 前端控制面接入点（预留）

1. 任务状态：`get_task_status(run_id, task_id)`
2. 任务时间线：`get_task_timeline(run_id, task_id)`
3. 运行中任务列表：`list_tasks(run_id=None, status=None)` + `list_run_ids()`
4. 任务提交与队列：`submit_task/get_submitted_task/list_submitted_tasks`
5. 事件数据源：`events.jsonl`

说明：当前仅提供进程内 API，不包含 Web 推送通道（SSE/WebSocket）。

## 5. 下一步推荐（进入 Phase 1）

1. 把规则型 hook 升级为“拓扑+语义”联合断言与后验检查
2. 在 `guiagent_v2` 中引入页面状态识别与拓扑匹配
3. 补齐基于 `events.jsonl` 的指标统计脚本与回归看板
