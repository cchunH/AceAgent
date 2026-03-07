# GUIAgent 集成蓝图 v1（社区对标落地版）

## 文档元信息

- 状态：`active`
- 版本：`v1.8`
- 更新时间：`2026-03-08`
- 目标：把社区标杆能力映射为 `guiagent_v2` 的可实施改造路径
- 说明：当前文档同时包含“目标蓝图 + 已落地进展”
- 差距评估与后续推进详见：`implementation-gap-and-reuse-plan-v2.md`

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
17. 新增 `session_runtime_server` 本地 HTTP IPC 服务（`/health /sessions /tasks /runtime/status /runtime/timeline`），并支持 `run.py --start_session_runtime_server` 独立启动。
18. `SessionRuntime` 新增会话/任务索引持久化恢复（`--session_runtime_state_path`），支持服务重启后恢复 session/task 查询面。
19. `SessionRuntimeServer` 新增 token 鉴权（默认写接口，读接口可选），并发布 API 契约文档 `session-runtime-api-contract-v1.md`。

尚未落地：
1. `watchdog` 深化生产化（告警升级策略、跨任务聚合、下载/安全扩展插件）。
2. `SessionRuntime` 生产级进程化（当前已具备本地 HTTP IPC + 索引恢复 + token 鉴权，仍缺多实例治理）。
3. 真正的生产级 web 子任务执行闭环（当前是 probe + fallback 的可控最小实现）。

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
