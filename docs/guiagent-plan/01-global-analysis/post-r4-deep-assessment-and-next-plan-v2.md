# GUIAgent 路线深度评估与推进计划 v2

## 文档元信息

- 状态：`active`
- 版本：`v2.0`
- 更新时间：`2026-03-08`
- 评估输入：
  - 代码：`guiagent_v2/runtime/*`, `run.py`, `test/*`
  - 文档：`integration-blueprint-v1.md`, `implementation-gap-and-reuse-plan-v2.md`, `post-r3-gap-review-and-next-plan-v1.md`

## 1. 当前实现结论（基线）

1. 主链骨架已成型  
- `orchestrator_v2 -> WebSkillRouter -> GuardPolicy -> ActionRegistry -> EventBus/StatusAPI/Watchdog` 已形成闭环。

2. 控制面已达“本地生产可用”级别  
- `SessionRuntime + SessionRuntimeServer` 已具备本地 HTTP IPC、token 鉴权、lockfile 多实例治理、控制面审计、基础持久化恢复。

3. 社区复用主线已落地到位  
- `agent-browser` 以 `AgentBrowserSkill` 旁路接入，且移动端主链约束仍保持。

4. 测试覆盖稳定  
- 本地执行：`python3 -m unittest discover -s test -p 'test_*.py'`
- 结果：`Ran 93 tests ... OK`

## 2. 深度评估（多维）

## 2.1 架构维度

优点：
- 模块边界相对清晰：`router/policy/registry/executor/watchdog/session-runtime` 分层成立。
- `runtime_mode` 保留 legacy 回退，重构风险可控。

问题：
- `orchestrator_v2.py` 同时承担 legacy 翻译、事件发射、watchdog 接线、任务主流程，职责过重。
- `v2_executor.py` 仍以启发式动作推断为核心，尚未形成真正的任务级规划与重规划。

## 2.2 Agent 决策链维度

优点：
- 决策链顺序明确：`route -> guard -> dispatch -> assert/post_check -> handover`。
- `GuardPolicy` 已支持文件化策略与热加载。

问题：
- `guard=confirm` 目前仅触发 `handover`，未形成“待确认 -> 继续执行”的闭环协议。
- `web_plan` 生成规则偏静态（open/snapshot 组合），缺少失败后重规划机制。

## 2.3 鲁棒性与治理维度

优点：
- `event_schema + watchdog_policy(escalation + cross_task_aggregation)` 已建立治理基线。
- 控制面写操作审计完整，便于追责与排障。

问题：
- `event_schema` 当前仅“标记无效”，缺 strict fail-fast 模式（CI/测试环境）。
- `watchdogs/manager.py` 中跨任务聚合告警未走统一 `_allow_alert` 门控，聚合告警风暴风险仍在。

## 2.4 可观测性与运维维度

优点：
- `status/timeline/audit` 查询链路可用，支持分页与时间范围过滤。
- `session_id` 已贯穿主链与控制面。

问题：
- `status_api.py` 时间线全内存累计，缺 TTL/分段归档策略。
- `/runtime/audit` 依赖内存聚合视图，长期运行下查询成本与内存占用风险上升。

## 2.5 工程可演进维度

优点：
- 单测覆盖面较完整，核心模块基本都有测试。
- 策略文件化与可热加载为后续前端控制面打下基础。

问题：
- Web 侧能力仍是“可用 v1”，与蓝图中的“复杂任务闭环执行”存在能力差距。
- 还未形成稳定的“阶段性 DoD 指标板”，跨迭代质量判断依赖人工阅读日志。

## 3. 文档与代码一致性审查

一致：
1. `integration-blueprint-v1` 中已落地项与代码基本一致（路由、门禁、事件、会话 IPC、审计）。
2. `implementation-gap-and-reuse-plan-v2` 对“已落地/部分落地/未落地”划分总体准确。

需更新：
1. 下一阶段计划需把“聚合告警节流一致性”和“状态面内存治理”提升到 P0/P1，不应只放在泛化治理项中。
2. 计划文档应从 `R3/R4` 过渡到新的 `R5+` 序列，避免迭代编号断层与目标漂移。

## 4. 更新后的推进计划（R5-R8）

## R5（P0，2-3 天）：治理硬化冲刺

目标：
- 先把“可跑”提升到“可长期跑”。

任务：
1. 事件契约 strict 模式  
- 模块：`event_bus.py`, `event_schema.py`
- 动作：新增 `strict_schema` 开关；测试/CI 开启后遇无效事件直接失败。

2. 聚合告警统一门控  
- 模块：`watchdogs/manager.py`
- 动作：`cross_task_aggregation` 产物也走 `_allow_alert` 或等价门控。

3. 状态面内存治理 v1  
- 模块：`status_api.py`
- 动作：加入可配置时间线上限或 TTL 淘汰。

验收：
1. schema 无效事件在 strict 模式下为 0。
2. 聚合告警无重复风暴。
3. 长任务压测后内存增长可控。

## R6（P0，4-6 天）：Web 执行链升级

目标：
- 从启发式多步 v1 升级到“可重规划”执行器。

任务：
1. 引入轻量 WebPlanner  
- 模块：`v2_executor.py`（或拆分 `web_planner.py`）
- 动作：目标 -> 步骤 -> 检查点；失败后局部重规划。

2. 回退策略升级  
- 模块：`v2_executor.py`
- 动作：从固定 `Wait` 回退改为“保留上下文的 mobile_native 恢复动作”。

3. 步骤级证据链  
- 模块：`v2_executor.py`, `agent_browser_skill.py`
- 动作：统一输出 step-level trace id 与最小证据字段。

验收：
1. Web 子任务 3-5 步场景完成率高于当前基线。
2. 失败可解释性（原因码+步骤位点）显著提升。

## R7（P1，3-5 天）：控制面数据面增强

目标：
- 让控制面面向长期运行。

任务：
1. 审计归档与滚动切片  
- 模块：`session_runtime_server.py`, `status_api.py`

2. 查询聚合索引（按 run/session/task）  
- 模块：`status_api.py`

3. 前端接入友好字段冻结 v1.1  
- 模块：`event_schema.py`, 文档 `session-runtime-api-contract-v1.md`

验收：
1. 长周期查询延迟稳定。
2. 归档后历史数据可追溯。

## R8（P1-P2，5-7 天）：跨节点会话治理

目标：
- 从单机可控走向多实例协同。

任务：
1. 会话 ownership 与租约心跳  
- 模块：`session_runtime.py`, `session_runtime_server.py`

2. 服务发现/实例注册  
- 模块：`session_runtime_server.py`（先本地 registry，再外部化）

3. 冲突恢复协议  
- 模块：同上

验收：
1. 多实例下不出现 session 漂移。
2. 故障实例退出后可自动接管。

## 5. Git 推进规范（本轮更新）

1. 每个迭代单独 checkpoint 标签  
- 示例：`checkpoint/R5-start`, `checkpoint/R5-done`

2. 提交粒度  
- 每项能力按“代码 + 测试 + 文档”单独 commit，避免混改。

3. 提交前固定检查  
- `python3 -m unittest discover -s test -p 'test_*.py'`
- 关键路径 smoke（`legacy` 与 `guiagent_v2 --v2_skip_legacy`）

4. 回滚策略  
- 禁止跨迭代混合提交；异常时按最近 checkpoint 回退。

## 6. 执行建议

1. 先做 `R5`，再进入 `R6`。  
2. 在 `R5` 完成前，不建议继续扩大新模块面。  
3. `R6` 完成后再启动下一轮社区复用扩展，避免“能力先增、治理滞后”。
