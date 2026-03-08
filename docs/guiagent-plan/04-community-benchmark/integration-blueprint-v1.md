# GUIAgent 集成蓝图 v1（社区对标落地版）

## 文档元信息

- 状态：`active`
- 版本：`v1.34`
- 更新时间：`2026-03-08`
- 目标：把社区标杆能力映射为 `guiagent_v2` 的可实施改造路径
- 说明：当前文档同时包含“目标蓝图 + 已落地进展”
- 差距评估与后续推进详见：`implementation-gap-and-reuse-plan-v2.md`
- 蓝图流程一致性约束详见：`../01-global-analysis/guiagent-blueprint-fidelity-review-v1.md`
- 功能优先任务分配详见：`../02-phase-0/functional-first-task-allocation-r10-r13-v1.md`

## 实施进展（截至 2026-03-08）

已在代码中落地：
1. `WebSkillRouter` 已实现并接入 `orchestrator_v2` 的 legacy 事件翻译链路。
2. 新增路由审计事件：`skill_route`；web 通道失败时新增 `skill_fallback`。
3. `action_exec/assertion/post_check/handover/step_end` 事件已透传 `channel/route_reason/skill_name`。
4. `AgentBrowserCLIAdapter + AgentBrowserSkill` 已落地为外部进程适配层（`agent-browser --json` 调用模式）。
5. `ActionRegistry` 与 `GuardPolicy` 已实现，并接入 `guiagent_v2(_shadow)` 的 probe 执行路径。
6. 新增 `v2_executor`：可按指令推断 web/mobile probe，执行 `guard_decision -> dispatch -> fallback`。
7. 新增事件：`guard_decision`、`adapter_call`（在 web 分支触发），用于后续控制面与治理指标。
8. 新增启动参数：`--v2_skip_legacy`（仅 `runtime_mode=guiagent_v2` 生效）可跳过 legacy 代理链做纯 v2 探针执行。
9. 新增 `LoopDetector` 与 `ContextCompactor` 基础实现，并在 `v2_executor` 与 legacy 翻译链路产出 `loop_warning/context_compaction` 事件。
10. `GuardPolicy` 已支持文件化策略加载与手动重载（`policy_loader`），入口新增 `--guard_policy_path/--guard_policy_reload_interval`。
11. 提供策略样例文件：`guiagent_v2/runtime/policies/guard_policy.example.json`。
12. `SessionRuntime` 已落地进程内会话隔离调度（`submit/list/wait/status/timeline`），并把 `session_id` 贯穿到 `v2_executor + orchestrator_v2 + status_api`。
13. 新增 `event_schema`（`v1`）并接入 `JSONLEventBus`，事件写入时执行字段规范化与校验标记（`schema_valid/schema_error`）。
14. 新增 `WatchdogManager` 与 `crash/security` 插件骨架，接入 `orchestrator_v2` 事件链并派生 `watchdog_alert` 事件。
15. 新增 `watchdog_policy`，支持插件启停、最小严重级、告警去重与节流，并新增入口参数 `--watchdog_policy_path/--watchdog_policy_reload_interval`。
16. 提供策略样例文件：`guiagent_v2/runtime/policies/watchdog_policy.example.json`。
17. 新增 `session_runtime_server` 本地 HTTP IPC 服务（`/health /sessions /tasks /runtime/status /runtime/timeline /runtime/audit`），并支持 `run.py --start_session_runtime_server` 独立启动。
18. `SessionRuntime` 新增会话/任务索引持久化恢复（`--session_runtime_state_path`），支持服务重启后恢复 session/task 查询面。
19. `SessionRuntimeServer` 新增 token 鉴权（默认写接口，读接口可选），并发布 API 契约文档 `session-runtime-api-contract-v1.md`。
20. `v2_executor` 的 web 通道从单步 probe 升级为多步执行 v1：`web_plan -> web_step_start/adapter_call/web_step_end`，失败时统一 `skill_fallback` 回退移动端主链。
21. `SessionRuntimeServer` 新增 lockfile 多实例治理（实例 ID、僵尸锁清理、可选端口冲突回退）与实例标识响应头。
22. 控制面写操作新增审计事件 `control_plane_audit`（`actor/source/trace_id/control_action`），并支持独立审计 JSONL 文件输出。
23. 任务相关控制面审计事件已并入 `status_api`（按 `run_id/task_id` 关联），可通过 `/runtime/timeline/{run_id}/{task_id}` 与执行链事件联合查看。
24. `SessionRuntimeServer` 新增 `/runtime/audit` 查询接口，支持按 `session_id/actor/source/control_action` 过滤审计事件。
25. `/runtime/audit` 已支持 `cursor + since_ts/until_ts`，用于长周期审计分页与时间窗口查询。
26. `WatchdogPolicy` 已支持 `escalation_rules`，可按窗口与阈值将重复异常升级为更高严重级（如 `CRITICAL`）。
27. `WatchdogManager` 已支持 `cross_task_aggregation`，可按配置对跨任务重复异常输出聚合告警。
28. `JSONLEventBus` 新增 `strict_schema` 模式；`run.py` 新增 `--strict_event_schema`，可在治理阶段对 schema 无效事件 fail-fast。
29. `cross_task_aggregation` 新增独立去重/节流门控参数（`dedup_window_sec/throttle_window_sec/max_alerts_per_key/dedup_key_fields`），聚合告警纳入统一门禁。
30. `TaskStatusStore` 新增每任务时间线内存上限能力（`max_timeline_events_per_task`，CLI: `--status_timeline_max_events`）与 `timeline_dropped` 统计。
31. 新增轻量 `web_planner`，`v2_executor` 支持 `initial plan + failure local replan`（单次重规划）执行链。
32. `v2_executor` 的 web 步骤新增 `web_plan_id/web_trace_id/web_plan_revision/web_step_checkpoint` 证据字段，便于步骤级追溯。
33. `web_skill` 失败后的移动端回退从固定 `Wait` 升级为“上下文感知 fallback action”并产出 `fallback_action_selected` 事件。
34. `run.py` 新增 `--web_max_steps/--web_replan_max_attempts`；`v2_executor` 已支持按错误码分流重规划策略与多次重规划（可配置）。
35. `runtime metrics` 已补齐 web 执行链指标：`web_plan_count/web_replan_count/web_replan_recovery_rate/web_fallback_rate/web_step_success_rate`。
36. 新增 `WebReplanPolicy`（任务内反馈回灌）：根据失败/恢复历史动态调整同类错误的重规划预算，并输出策略决策事件。
37. `SessionRuntimeServer` 新增 `GET /runtime/metrics`，控制面可直接查询运行聚合指标（支持 `run_id/task_id/session_id/time-range` 过滤）。
38. `SessionRuntimeServer` 新增 `GET /runtime/metrics/timeseries`，支持按时间桶查询跨 run/session 的时序指标（`bucket_sec/max_buckets`）。
39. `GuardPolicy` 新增 web 域名门禁（`web_domain_allowlist/web_domain_denylist`），web_skill 执行前可按域名做 allow/deny/confirm 决策。
40. 确认流最小闭环已接入：`pending_confirm -> confirm_approved|confirm_rejected|confirm_timeout`，并新增控制面确认接口（`/runtime/confirm`）。
41. `state_engine` 新增动态场景去噪与静态骨架提取（`denoise_perception_frames/build_static_skeleton`），并接入 `assertion_guard/post_check/blueprint_sync`。
42. 新增离线复盘入口 `runtime.offline_replay.rebuild_blueprints_from_steps` 与 blueprint 在线快速匹配能力（`BlueprintRepository.match_by_skeleton`）。
43. 新增运行后主流程审查能力：`runtime.flow_audit`，`runtime_summary.json` 自动输出 `flow_audit`（按 task 给出 PASS/WARN/FAIL 与缺失事件定位）。
44. 新增离线复盘质量评分门槛：`runtime.replay_quality.score_replay_sample`，`offline_replay` 已支持低质量样本过滤（`min_quality_score`）。
45. `v2_executor` 已接入显式执行状态机（`executor_state_machine`），并输出 `executor_state` 迁移事件以支持流程级审查。
46. 新增向量检索抽象 `VectorIndexAdapter`（`InMemoryVectorIndex` v0），`BlueprintRepository` 已支持 `rebuild_vector_index/match_by_vector`。
47. `blueprint_sync` 已接入 Delta patch 策略（`blueprint_delta`），现按差分字段更新蓝图并记录 `rollback_to`，低稳定场景可抑制结构更新。
48. 已补“离线回灌 -> 在线检索”最小闭环回归样例（`test_offline_replay`），保证回灌产物可被检索层消费。
49. `state_engine` 的 `StaticSkeleton` 已补充 `dynamic_slots` 摘要，用于记录动态噪声槽位，增强后续回灌与匹配策略可解释性。
50. `topology_matcher` 已升级为角色/区域加权匹配（文本+距离+meta），并通过 `CORE` 锚点优先级降低复杂场景误匹配。
51. `fast_match` 已融合 `dynamic_slots`：新增动态一致性加分与动态污染惩罚，降低动态噪声导致的误召回。
52. 断言与后检链路已输出主辅锚点分路评分：`core_anchor_confidence/aux_anchor_confidence/geometry_confidence`，并纳入 `runtime metrics`。
53. `flow_audit` 增加低置信度审查：步骤成功但主锚点/几何置信度过低会输出 `WARN`，用于提前暴露潜在误触风险。
54. `v2_executor` 已增加锚点门控与辅锚点微重试（`anchor_gate/anchor_micro_retry`），并通过 `pipeline` 透传 `pre_assertion` 置信度避免后检场景误阻断。
55. `runtime metrics` 与 `runtime_summary` 已补锚点策略成效统计（`anchor_gate_*`、`anchor_micro_retry_*`、`anchor_strategy`），支持门控/微重试收益量化。
56. `v2_executor` 的移动端分支已接入 `MobileDeviceExecutor`（`auto|shadow|device`）：有 ADB 时执行真实设备动作，无 ADB 自动回退 shadow，入口新增 `--mobile_execution_mode/--mobile_wait_ms`。

尚未落地：
1. `watchdog` 深化生产化（下载/安全扩展插件、聚合统计导出）。
2. `SessionRuntime` 生产级进程化（当前已具备本地 HTTP IPC + 索引恢复 + token 鉴权 + 多实例治理 + 控制面审计，仍缺服务发现与跨节点协调）。
3. 真正的生产级 web 子任务执行闭环（当前已具备启发式 plan + 单次局部重规划 + fallback，仍缺复杂任务策略与学习反馈）。
4. `VectorIndexAdapter` 与向量召回层（意图对齐/蓝图候选检索）尚未接入主链。
5. 群智联邦分发（蓝图 06/11）不在当前迭代范围，明确后置到主流程稳定后。

## 0. 决策基线（先定方向）

1. 推荐模式：`模块拆解并入（主线） + AgentBrowserSkill（辅线）`。
2. 控制原则：`mobile_native` 是默认且唯一主链，`web_skill` 仅处理网页子任务。
3. 健康标准：任何阶段都不得出现“移动端系统动作改走 web_skill”的回归。
4. 决策依据：`skill-vs-modular-integration-decision.md`（本目录）。

## 1. 目标架构（从文档到代码）

## 1.1 目标分层

1. 决策层（Planner/Executor/Verify）
- 维持 `guiagent_v2/runtime/orchestrator_v2.py` 主编排。

2. 执行抽象层（新增建议）
- `WebAutomationAdapter`：统一对接外部浏览器执行后端（优先 agent-browser 外部进程）。
- `ActionRegistry`：统一动作注册、参数校验、分发。
- `GuardPolicy`：执行前 allow/deny/confirm 决策层。
- `SessionRuntime`：任务会话、IPC、状态查询、生命周期管理。

3. 观测与治理层
- 继续使用 `events.jsonl` + `status_api` + `runtime_summary`。
- 增加 loop/compaction/guard 决策事件。

## 1.2 移动端优先约束（关键补充）

1. `agent-browser` 不替代移动端主链：主执行仍是 `ADB + Perceptor + ActionExecutor`。
2. Web 能力以 Skill 方式旁路接入：仅在任务确认为 `web 子任务` 时调用。
3. 移动端系统级动作（App 切换、返回、权限弹窗、输入法、系统设置）一律留在原生主链。
4. Web Skill 失败必须可回退：失败后回到 `guiagent_v2` 主链并触发 `handover` 或重规划。
5. 运行时必须记录执行通道：`channel=mobile_native|web_skill`，避免观测混淆。

## 1.3 路由规则 v0（执行时强约束）

1. 默认路由：所有任务先进入 `mobile_native`。
2. 命中条件：仅当 `intent_key` 命中 `web:*` 或任务被明确标记为网页子流程时，允许进入 `web_skill`。
3. 禁止条件：`Open_App/Back/Home/Switch_App/Type/Enter/Swipe` 等设备系统动作禁止进入 `web_skill`。
4. 回退条件：`web_skill` 任一步失败、超时或响应不合法，立即 `fallback=mobile_native`。
5. 审计要求：每次路由决策必须产生日志事件 `skill_route`，回退必须产生日志事件 `skill_fallback`。

## 1.4 候选接口草案（冻结建议）

以下接口已完成 `v0` 骨架落地（`WebAutomationAdapter/ActionRegistry/GuardPolicy/SessionRuntime/WebSkillRouter/AgentBrowserSkill`），仍需按阶段继续增强：

```python
class WebAutomationAdapter:
    def start_session(self, session_id: str, options: dict) -> dict: ...
    def execute(self, request: dict) -> dict: ...
    def snapshot(self, session_id: str, mode: str = "interactive") -> dict: ...
    def diff(self, before: dict, after: dict, mode: str = "text+image") -> dict: ...
    def stop_session(self, session_id: str) -> None: ...

class ActionRegistry:
    def register(self, name: str, schema: dict, handler) -> None: ...
    def validate(self, name: str, payload: dict) -> tuple[bool, dict]: ...
    def dispatch(self, name: str, payload: dict, context: dict) -> dict: ...

class GuardPolicy:
    def decide(self, intent_key: str, action: dict, context: dict) -> dict: ...
    # return: {decision: "allow|deny|confirm", reason: str, category: str}

class SessionRuntime:
    def submit(self, task: dict) -> dict: ...
    def status(self, run_id: str, task_id: str) -> dict: ...
    def timeline(self, run_id: str, task_id: str) -> list[dict]: ...
    def list_tasks(self, filters: dict | None = None) -> list[dict]: ...

class WebSkillRouter:
    def route(self, intent_key: str, context: dict) -> str: ...
    # return: "mobile_native" | "web_skill"

class AgentBrowserSkill:
    def invoke(self, task: str, session: dict, constraints: dict) -> dict: ...
    # return: {success: bool, result: dict, trace: list[dict], error: str | None}
```

## 2. 分阶段实施序列（建议）

## Phase 1：执行治理最小闭环

目标：把 `GuardPolicy + LoopDetector + Compaction` 接入现有 runtime，不改变主执行入口。

实施要点：
1. `pre_assertion` 前加入 guard 决策。
2. `step_end` 后记录 action hash 与 page stagnation。
3. 长链路任务增加 history compaction。

退出条件：
- 新增事件字段稳定输出：`guard_decision`, `loop_warning`, `compaction_applied`
- 与当前基线相比成功率不下降。

## Phase 2：SessionRuntime 进程化

目标：从线程任务服务升级为会话化后台服务。

实施要点：
1. `RuntimeTaskService` 扩展为 server/session registry。
2. 支持单会话多任务串行、跨会话并行。
3. 前端控制面只读接入 status/timeline/list。

退出条件：
- server 重启后不影响新任务提交。
- run/task 查询接口稳定。

## Phase 3：WebAutomationAdapter（外接 agent-browser）

目标：把浏览器专项能力作为独立适配器接入，不污染核心 runtime。

实施要点：
1. 先做 adapter mock，统一请求/响应结构。
2. 再接真实 agent-browser 进程调用（snapshot/diff/policy/domain）。
3. 以 Skill 方式接入：`AgentBrowserSkill` 由 `WebSkillRouter` 按 intent 决定是否调用。
4. 失败时 fallback 到现有执行链。

退出条件：
- 可在单任务路径稳定调用 snapshot + diff。
- `web_skill` 仅在 web 子任务触发，不影响移动端原生动作链。
- adapter 失败不会导致 orchestrator 崩溃。

## Phase 4：ActionRegistry + Watchdog

目标：减少 if-else 动作分发，增强运行时守护。

实施要点：
1. 引入动作注册中心，统一动作参数校验。
2. 增加 watchdog 插件（crash/security/download）。

退出条件：
- 新动作接入不改主编排。
- watchdog 告警事件可追踪可统计。

## 3. 事件与状态面增强规范

建议新增事件类型：
- `guard_decision`
- `loop_warning`
- `context_compaction`
- `adapter_call`
- `watchdog_alert`
- `skill_route`
- `skill_fallback`
- `web_replan`
- `web_replan_skipped`
- `fallback_action_selected`
- `web_replan_policy_decision`
- `web_replan_policy_update`
- `pending_confirm`
- `confirm_approved`
- `confirm_rejected`
- `confirm_timeout`
- `control_plane_audit`

建议新增关键字段：
- `session_id`
- `adapter_backend`
- `policy_category`
- `policy_decision`
- `loop_score`
- `stagnation_steps`
- `channel`
- `skill_name`
- `route_reason`
- `web_plan_id`
- `web_trace_id`
- `web_plan_revision`
- `web_replan_strategy`

## 3.1 关键健康指标（用于判断方案是否跑偏）

1. `mobile_native_coverage`：移动端系统动作中走 `mobile_native` 的比例，目标 100%。
2. `web_skill_route_precision`：进入 `web_skill` 的任务中真实网页子任务占比，目标 >= 95%。
3. `web_skill_fallback_success_rate`：`web_skill` 失败后主链回退并完成任务比例，目标 >= 90%。
4. `core_success_non_regression`：对比改造前基线，移动端核心场景成功率不下降。

## 4. 风险清单与应对

1. 风险：接口先行但实现滞后，产生文档债。
- 应对：每阶段完成后同步更新接口文档版本号。

2. 风险：外部进程 adapter 引入稳定性问题。
- 应对：强制 fallback + 熔断策略 + 超时控制。

3. 风险：事件字段膨胀影响维护。
- 应对：核心字段冻结，扩展字段版本化管理。

4. 风险：把 Web 执行误用到移动端系统动作，导致能力错配。
- 应对：在 `WebSkillRouter` 固定移动端白名单/黑名单路由规则，系统动作禁止走 `web_skill`。

## 5. 结论

该蓝图遵循“移动端主链稳定优先，Web Skill 能力旁路增强”的顺序，能在不推倒现有 `guiagent_v2` 的前提下吸收社区项目成熟能力。短期建议聚焦 Phase 1~2，中期推进 Phase 3（skill 接入），后期再进入 Phase 4。
