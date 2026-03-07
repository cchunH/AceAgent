# GUIAgent 路线差距审查与下一阶段深度规划 v1

## 文档元信息

- 状态：`active`
- 版本：`v1.8`
- 更新时间：`2026-03-08`
- 范围：基于当前 `main` 代码，对 `R3(会话进程化) + R4(治理生产化)` 进行实装后差距审查

## 1. 当前实装基线（代码事实）

1. 会话运行时与本地 IPC
- 模块：`guiagent_v2/runtime/session_runtime.py`
- 模块：`guiagent_v2/runtime/session_runtime_server.py`
- 结论：已形成 `session/task/status/timeline` 的本地 HTTP 控制面闭环（v1），并支持 session/task 索引恢复。

2. 事件治理与守护
- 模块：`guiagent_v2/runtime/event_schema.py`
- 模块：`guiagent_v2/runtime/watchdogs/manager.py`
- 模块：`guiagent_v2/runtime/watchdog_policy.py`
- 结论：已形成 schema 校验 + watchdog 告警 + 策略化去重节流的治理基线（v1）。

3. 主链兼容性
- 模块：`guiagent_v2/runtime/orchestrator_v2.py`
- 模块：`run.py`
- 结论：`legacy` 默认不变，`guiagent_v2(_shadow)` 可持续演进，无需切换入口。

## 2. 差距审查（按风险优先级）

## P0（建议立即推进）

1. Web 子任务仍是 v1 启发式级
- 问题：`v2_executor` 已支持多步 v1，但仍缺复杂任务规划与回溯。
- 证据模块：`v2_executor.py`
- 影响：网页多步任务成功率和可解释性仍受限。
- 建议：引入任务分解器（目标->步骤->检查点）与失败后重规划。

2. SessionRuntime 进程化的分布式缺口
- 问题：本地单机治理已完成，但缺服务发现/租约心跳与跨节点一致性。
- 证据模块：`session_runtime_server.py`, `session_runtime.py`
- 影响：多机部署时仍可能出现会话漂移与状态歧义。
- 建议：引入实例注册表（lease TTL）与 session ownership 协议。

## P1（建议下一阶段并行）

1. 告警聚合能力不足
- 问题：watchdog 已支持升级规则，但仍缺跨任务聚合视角。
- 证据模块：`watchdogs/manager.py`, `watchdog_policy.py`
- 影响：单任务内优先级可控，跨任务根因聚合仍弱。
- 建议：为 watchdog 增加跨任务聚合键与周期统计导出。

2. Schema 严格化不足
- 问题：当前 schema 以“标记无效”为主，未 fail-fast。
- 证据模块：`event_schema.py`, `event_bus.py`
- 影响：下游消费需要二次兜底。
- 建议：新增严格模式开关（测试/CI 环境强校验失败即报错）。

3. 审计聚合仍待增强
- 问题：已提供 `/runtime/audit` 的时间范围与分页游标，但缺跨文件归档与聚合查询。
- 证据模块：`session_runtime_server.py`, `status_api.py`
- 影响：高频任务场景下审计查询压力与结果截断风险上升。
- 建议：补齐归档层与统一聚合索引（按天/任务切分）。

## P2（中长期）

1. 多实例治理
- 问题：当前服务为单实例本地模式。
- 建议：引入服务发现/端口锁文件/实例标识，避免多实例争抢。

2. 下载/崩溃外更多 watchdog 插件
- 问题：仅 `crash/security` 两类。
- 建议：补 `download_watchdog`、`navigation_deadend_watchdog`。

3. 跨语言执行面统一
- 问题：`agent-browser` 仍为适配层调用，尚未形成统一执行编排协议。
- 建议：后续对齐 `WebAutomationAdapter` 契约 v2（stream + checkpoint）。

## 3. 下一阶段实施规划（建议 3 个迭代）

## Iteration A（3-5 天）：控制面安全与契约冻结

1. SessionRuntime 分布式治理
- 目标模块：`session_runtime_server.py`
- 验收：跨实例注册、租约续期和 ownership 冲突可观测。

2. 控制面与主链事件聚合
- 目标模块：`session_runtime_server.py`, `event_bus.py`
- 验收：单 run/task 视角下可同时看到执行链事件与控制面审计事件。

## Iteration B（4-6 天）：执行链增强

1. Web 多步执行器 v1
- 目标模块：`v2_executor.py`
- 验收：Web 子任务 3 步内完成率较 probe 基线提升。

2. Watchdog 升级规则
- 目标模块：`watchdog_policy.py`, `watchdogs/manager.py`
- 验收：重复异常触发严重级升级并可观测。

## Iteration C（3-5 天）：事件契约强化

1. Schema 严格模式
- 目标模块：`event_schema.py`, `event_bus.py`
- 验收：CI 中 schema 无效事件为 0。

2. 关键流程回归套件
- 目标目录：`test/`
- 验收：新增控制面/API/Web 多步场景回归。

## 4. 风险与控制

1. 风险：IPC 改造影响当前执行稳定性
- 控制：默认不启用 server；仅显式 `--start_session_runtime_server` 时运行。

2. 风险：恢复机制引入状态污染
- 控制：持久化仅保存最小索引，不持久化运行时线程对象。

3. 风险：Web 多步执行导致移动端主链被稀释
- 控制：继续保留 `WebSkillRouter + GuardPolicy` 双层约束，系统动作严格禁走 web 通道。

## 5. 结论

当前路线已从“骨架期”进入“可运行治理期”：具备会话 IPC、索引恢复、token 鉴权、API 契约、事件 schema、策略化 watchdog，以及多实例锁治理与控制面审计。下一阶段应集中补齐 `分布式会话治理 + 多步执行增强 + 统一聚合视图` 三个核心缺口，避免过早扩展模块面，保持主链稳定与迭代速度平衡。
