# R10 代码流程审查报告 v1（功能优先主链）

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-08`
- 范围：`guiagent_v2` 主流程（不含群智联邦分发）

## 1. 审查目标

1. 确认“用户可跑完整流程”的代码链路已闭环。
2. 确认执行链按蓝图流程 A/B/C 实现，不是模块拼接。
3. 确认异常/回退/确认流路径有可观测证据。

## 2. 审查方法

1. 静态流程审查：按入口到退出路径逐段复核。
2. 单元测试审查：基于 `test/test_*.py` 结果验证主行为。
3. 事件证据审查：检查 `event_type` 与 `runtime_summary` 生成链路。

说明：
- 本轮未完成本地实机冒烟，原因是当前环境缺少 `torch` 依赖（`run.py` 启动前置导入失败）。

## 3. 主链路定位（代码证据）

1. 运行入口：`run.py`
- 通过 `runtime_mode=guiagent_v2` + `--v2_skip_legacy` 进入 v2 纯链路。

2. 运行时编排：`guiagent_v2/runtime/orchestrator_v2.py`
- 负责 `task_start/task_end`、`run_probe_step` 调度、事件总线、summary 产出。

3. 执行主循环：`guiagent_v2/runtime/v2_executor.py`
- 负责 route -> guard -> execute(web/mobile) -> verify -> handover/complete。
- 当前已接入显式状态机：`guiagent_v2/runtime/executor_state_machine.py`。

4. 状态与复盘：`guiagent_v2/runtime/offline_replay.py`
- 负责离线回灌重建，现已接入质量门槛：`replay_quality.py`。

5. 运行后审查：`guiagent_v2/runtime/flow_audit.py`
- 在 `runtime_summary` 输出流程完整性判定（PASS/WARN/FAIL）。

## 4. 主流程一致性结论（A/B/C）

1. 流程 A（快路径执行）：
- 已具备：意图映射、路由、门禁、执行、断言、后检、结束。
- 证据事件：`step_start/skill_route/guard_decision/assertion/post_check/step_end`。

2. 流程 B（偏离与自愈）：
- 已具备：`web_replan`、`skill_fallback`、`handover`、`confirm_*`。
- 证据事件：`web_replan/web_replan_skipped/skill_fallback/fallback_action_selected/handover`。

3. 流程 C（离线复盘与回灌）：
- 已具备：`offline_replay` 重建 + `replay_quality` 过滤 + skeleton 快速匹配。
- 缺口：Delta patch 策略和自动回滚门禁仍需加强（R11）。

## 5. 状态机审查（A1 落地）

1. 当前状态枚举：
- `INIT -> ROUTED -> GUARDED -> (CONFIRM_PENDING) -> EXECUTING_WEB|EXECUTING_MOBILE -> (FALLBACK) -> VERIFYING -> HANDOVER|COMPLETED`

2. 状态可观测性：
- 新增事件：`executor_state`
- 关键字段：`executor_prev_state/executor_state/executor_reason/executor_transition_ok`

3. 审查结论：
- 状态机已从隐式逻辑转为显式建模，便于流程定位与审计追踪。

## 6. 测试与质量证据

1. 全量单元测试：
- `python3 -m unittest discover -s test -p 'test_*.py'`
- 结果：`Ran 130 tests ... OK`

2. 新增/强化覆盖：
- `test_executor_state_machine.py`
- `test_flow_audit.py`
- `test_replay_quality.py`
- `test_offline_replay.py`（低质量样本过滤）
- `test_v2_executor.py`（状态事件存在性）

## 7. 当前缺口（不阻塞可运行）

1. 环境冒烟缺口：
- 本机未安装 `torch`，导致 `run.py` 直接启动失败；需补齐运行依赖后做真实链路烟测。

2. 算法深水区缺口：
- 动态场景去噪和静态骨架在复杂噪声场景下仍缺压力回归基线。

3. 检索层缺口：
- 向量召回适配层（`VectorIndexAdapter`）仍未接入。

## 8. 下一步执行（R10 -> R11）

1. 先补可运行环境（安装 `torch`）并完成 2 条 smoke：
- 移动端等待流程
- web 子任务触发 fallback 流程

2. 启动 R11：
- 离线回灌 Delta 策略
- 回灌后在线再命中验证（闭环回归）

3. 保持范围收敛：
- 群智联邦分发继续后置，不进入当前迭代。

