# 实现差距评估与复用推进计划 v2

## 文档元信息

- 状态：`active`
- 版本：`v2.1`
- 更新时间：`2026-03-08`
- 目的：对齐 `integration-blueprint-v1` 与当前代码实现，给出下一阶段可执行复用计划

## 1. 评估范围

本评估对齐三类内容：

1. 架构蓝图：`integration-blueprint-v1.md`
2. 复用目录：`reusable-module-catalog-for-unimind.md`
3. 代码现状：`guiagent_v2/runtime/*`, `run.py`, `test/*`

## 2. 当前实现距离（按模块）

### 2.1 已落地（可用）

1. `WebSkillRouter`
- 证据模块：`guiagent_v2/runtime/web_skill_router.py`
- 现状：已支持 `mobile_native|web_skill` 路由与系统动作保护。
- 距离评估：`完成（v0）`

2. `AgentBrowserSkill + WebAutomationAdapter`
- 证据模块：`guiagent_v2/runtime/agent_browser_skill.py`
- 现状：已支持外部进程调用 `agent-browser --json --session`，含基础命令映射与错误归一化。
- 距离评估：`完成（v0）`

3. `ActionRegistry`
- 证据模块：`guiagent_v2/runtime/action_registry.py`
- 现状：已支持 register/validate/dispatch，含基础 schema 校验。
- 距离评估：`完成（v0）`

4. `GuardPolicy`
- 证据模块：`guiagent_v2/runtime/guard_policy.py`
- 现状：已支持 `allow/deny/confirm`，并阻断 `web_skill` 执行移动端系统动作。
- 距离评估：`完成（v0）`

5. `v2_executor` 探针链路
- 证据模块：`guiagent_v2/runtime/v2_executor.py`
- 现状：已形成 `skill_route -> guard_decision -> dispatch -> adapter_call -> skill_fallback` 闭环。
- 距离评估：`部分完成（probe 级）`

6. 运行入口参数
- 证据模块：`run.py`, `guiagent_v2/runtime/orchestrator_v2.py`
- 现状：`runtime_mode=guiagent_v2` 支持 `--v2_skip_legacy` 仅运行 v2 探针路径。
- 距离评估：`完成（v0）`

7. `LoopDetector`
- 证据模块：`guiagent_v2/runtime/loop_detector.py`
- 现状：已支持重复动作/页面停滞检测，输出 `loop_score` 与告警判断。
- 距离评估：`完成（v0）`

8. `ContextCompactor`
- 证据模块：`guiagent_v2/runtime/context_compaction.py`
- 现状：已支持事件窗口压缩，并在 runtime 输出 `context_compaction` 事件。
- 距离评估：`完成（v0）`

9. `GuardPolicy` 文件化策略
- 证据模块：`guiagent_v2/runtime/policy_loader.py`, `guiagent_v2/runtime/guard_policy.py`
- 现状：支持 JSON 策略加载、缓存与手动 reload，运行入口支持策略路径与检查间隔参数。
- 距离评估：`完成（v0）`

10. `SessionRuntime`（进程内 v0）
- 证据模块：`guiagent_v2/runtime/session_runtime.py`, `guiagent_v2/runtime/task_service.py`
- 现状：已支持会话创建、会话级提交/查询/等待、跨会话任务隔离调度，并兼容旧任务服务。
- 距离评估：`完成（v0，非进程化）`

### 2.2 部分落地（需增强）

1. `SessionRuntime`
- 证据模块：`guiagent_v2/runtime/session_runtime.py`, `guiagent_v2/runtime/task_service.py`
- 现状：进程内会话隔离已落地，支持 `session_id` 注入执行链与状态查询过滤。
- 距离评估：`部分完成`
- 关键差距：无跨进程会话、无重启恢复、无 IPC 控制面协议。

2. 事件治理
- 证据模块：`guiagent_v2/runtime/event_bus.py`, `status_api.py`
- 现状：核心事件完整，状态查询可用，已支持 `session_id` 维度聚合。
- 距离评估：`部分完成`
- 关键差距：尚未类型化 schema 版本管理；缺少 watchdog 事件与统一校验层。

3. Web 子任务闭环
- 证据模块：`v2_executor.py`, `agent_browser_skill.py`
- 现状：可走 web probe 与 fallback。
- 距离评估：`部分完成`
- 关键差距：未接入真实多步任务编排与生产级会话生命周期管理。

### 2.3 未落地（待实施）

1. `Watchdog` 体系
- 目标来源：`browser-use`（watchdog 基座）
- 差距：无 crash/security/download 守护插件。

2. Domain Filter 与高级 Action Policy 治理
- 目标来源：`agent-browser`
- 差距：已具备基础文件化策略，但未实现域名级策略联动与动态策略分层（环境/任务级）。

## 3. 复用优先级重排（基于已实现状态）

## P0（下一迭代必须完成）

1. `LoopDetector`（来自 browser-use）
- 落位：`guiagent_v2/runtime/loop_detector.py`
- 事件：`loop_warning`
- 状态：`已落地 v0`
- 后续增强：引入分场景阈值与连续任务级统计。

2. `ContextCompaction`（来自 browser-use）
- 落位：`guiagent_v2/runtime/context_compaction.py`
- 事件：`context_compaction`
- 状态：`已落地 v0`
- 后续增强：增加 token 预算策略与摘要质量评估。

3. `GuardPolicy` 文件化 + 热加载（来自 agent-browser policy 思路）
- 落位：`guiagent_v2/runtime/policy_loader.py`
- 状态：`已落地 v0`
- 后续增强：增加分环境策略、域名策略联动、策略冲突检测。

## P1（P0 稳定后进入）

1. `SessionRuntime` 进程化
- 落位：`guiagent_v2/runtime/session_runtime.py`
- 能力：会话注册、跨会话并行、基础恢复策略。

2. Typed Event Schema
- 落位：`guiagent_v2/runtime/event_schema.py`
- 能力：关键事件字段版本冻结与校验。

3. Watchdog 插件化
- 落位：`guiagent_v2/runtime/watchdogs/*`
- 初始插件：`crash_watchdog.py`, `security_watchdog.py`。

## P2（后置）

1. SnapshotRef 深化与 diff 证据链
2. stream-server 控制通道对接
3. 更深层 browser-use agent 机制拆取

## 4. 建议实施序列（代码可直接开工）

### 阶段 R1：治理补齐（已完成第一步）

1. 已完成：引入 `LoopDetector` 与 `ContextCompaction`。
2. 已完成：在 `run_probe_step` 与 legacy 翻译链路统一产出 `loop_warning/context_compaction`。
3. 已完成：新增回归测试（重复动作、长事件链压缩）。
4. 待继续：将压缩策略与 prompt/token 预算真正联动到长任务主链。

退出条件：
- 新事件稳定输出。
- 测试通过且移动端主链成功率无明显回退。

### 阶段 R2：策略外置（2-3 天）

1. 已完成：`GuardPolicy` 改为“默认策略 + 文件策略”组合。
2. 已完成：支持策略 reload（`reload_policy()` + 入口参数检查间隔）。
3. 待继续：加入域名级策略与多层策略合并（全局/任务）。

退出条件：
- 至少 3 类策略可配置（高风险确认、web 路由阻断、黑名单动作）。

### 阶段 R3：会话进程化（4-7 天）

1. 已完成：在现有 `RuntimeTaskService` 上增量抽象 `SessionRuntime`（进程内 v0）。
2. 已完成：保留旧 API 兼容，新增 session 级提交与查询接口。
3. 待继续：抽离独立进程/IPC 通道，并补齐重启恢复策略。
4. 待继续：把 `session_id` 作为控制面一等键接入后续状态 API/前端适配层。

退出条件：
- 会话隔离可验证。
- server 重启后新任务可正常提交。

## 5. 风险与控制

1. 风险：复用过快导致主链不稳定。
- 控制：保持 `runtime_mode=legacy` 默认；新能力仅在 `guiagent_v2` 下启用。

2. 风险：web_skill 误扩散到移动系统动作。
- 控制：`GuardPolicy + WebSkillRouter` 双层阻断保持强约束。

3. 风险：事件字段快速膨胀不可维护。
- 控制：R2 同步落地 Typed Event Schema，冻结核心字段。

## 6. 本文档对应改造入口

1. 主编排入口：`guiagent_v2/runtime/orchestrator_v2.py`
2. v2 执行链入口：`guiagent_v2/runtime/v2_executor.py`
3. 门禁策略：`guiagent_v2/runtime/guard_policy.py`
4. 动作分发：`guiagent_v2/runtime/action_registry.py`
5. Web 旁路：`guiagent_v2/runtime/agent_browser_skill.py`
6. 任务状态面：`guiagent_v2/runtime/task_service.py`, `status_api.py`
7. 会话编排层：`guiagent_v2/runtime/session_runtime.py`

## 7. 结论

当前项目已经完成蓝图中的关键“骨架层”复用：路由、Skill 旁路、门禁、注册中心、可观测链路，以及会话隔离运行时 v0。下一步不建议继续扩展新模块面，而应优先补齐治理闭环（Policy 分层/Schema/Watchdog）与会话进程化，确保架构健康度和生产可控性同步提升。
