# GUIAgent 集成蓝图 v1（社区对标落地版）

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-07`
- 目标：把社区标杆能力映射为 `guiagent_v2` 的可实施改造路径
- 说明：本蓝图只定义接口与阶段计划，不包含本轮代码改造

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

## 1.3 候选接口草案（冻结建议）

以下为文档冻结草案，不在本轮实现：

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
