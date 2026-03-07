# GUIAgent 路线差距审查与下一阶段深度规划 v1

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-08`
- 范围：基于当前 `main` 代码，对 `R3(会话进程化) + R4(治理生产化)` 进行实装后差距审查

## 1. 当前实装基线（代码事实）

1. 会话运行时与本地 IPC
- 模块：`guiagent_v2/runtime/session_runtime.py`
- 模块：`guiagent_v2/runtime/session_runtime_server.py`
- 结论：已形成 `session/task/status/timeline` 的本地 HTTP 控制面闭环（v1）。

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

1. 会话恢复能力缺口
- 问题：IPC 服务重启后，任务索引与会话信息不可恢复。
- 证据模块：`session_runtime.py`, `session_runtime_server.py`
- 影响：控制面可见性中断，长任务/多会话场景恢复成本高。
- 建议：引入轻量持久化（`session_registry.jsonl` + `task_index.jsonl`）与启动恢复流程。

2. IPC 安全边界缺口
- 问题：本地 HTTP API 目前无鉴权。
- 证据模块：`session_runtime_server.py`
- 影响：同机进程可直接提交/查询任务，存在控制面滥用风险。
- 建议：增加 `api_token` 机制与可选 `origin/process` 白名单。

3. Web 子任务仍是 probe 级
- 问题：`v2_executor` 的 web 分支仍偏单步探针+回退。
- 证据模块：`v2_executor.py`
- 影响：网页多步任务成功率和可解释性仍受限。
- 建议：补“多步 web action 计划执行器”最小版本（3-5 步上限 + step watchdog）。

## P1（建议下一阶段并行）

1. 告警升级策略不足
- 问题：watchdog 有去重/节流，但无升级路径（重复失败升级 CRITICAL）。
- 证据模块：`watchdogs/manager.py`, `watchdog_policy.py`
- 影响：异常噪声可控但故障优先级不够明确。
- 建议：加入 `escalation_rules`（按窗口内次数提升严重级）。

2. Schema 严格化不足
- 问题：当前 schema 以“标记无效”为主，未 fail-fast。
- 证据模块：`event_schema.py`, `event_bus.py`
- 影响：下游消费需要二次兜底。
- 建议：新增严格模式开关（测试/CI 环境强校验失败即报错）。

3. 控制面 API 缺少契约文档
- 问题：接口已可用，但缺少独立 API contract 文档和示例。
- 证据模块：`session_runtime_server.py`
- 影响：后续前端和外部调度接入效率受限。
- 建议：新增 `session-runtime-api-contract-v1.md`（路径、请求、响应、错误码）。

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

## Iteration A（3-5 天）：控制面安全与恢复

1. IPC 鉴权
- 目标模块：`session_runtime_server.py`
- 验收：未携带 token 的写操作返回 `401`。

2. 会话/任务索引持久化
- 目标模块：`session_runtime.py`
- 验收：服务重启后可恢复 `session -> request_id` 映射。

3. API 契约文档
- 目标文档：`docs/guiagent-plan/02-phase-0/session-runtime-api-contract-v1.md`
- 验收：前端可据此直接联调。

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

当前路线已从“骨架期”进入“可运行治理期”：具备会话 IPC、事件 schema、策略化 watchdog。下一阶段应集中补齐 `安全 + 恢复 + 多步执行` 三个核心缺口，避免过早扩展模块面，保持主链稳定与迭代速度平衡。
