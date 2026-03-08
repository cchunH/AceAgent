# GUIAgent 路线深度评估与推进计划 v3

## 文档元信息

- 状态：`active`
- 版本：`v3.1`
- 更新时间：`2026-03-08`
- 评估输入：
  - 代码：`guiagent_v2/runtime/*`, `run.py`, `test/*`
  - 文档：`integration-blueprint-v1.md`, `implementation-gap-and-reuse-plan-v2.md`, `session-runtime-api-contract-v1.md`
  - 补充：最新优先级重排见 `code-doc-alignment-priority-review-v3.md`

## 1. 当前实现结论（最新基线）

1. 主链运行时已形成可扩展骨架
- `orchestrator_v2 -> WebSkillRouter -> GuardPolicy -> ActionRegistry -> v2_executor` 已稳定串联。

2. Web 子任务闭环已进入“可用 v1.5”
- 已具备 `web_plan -> web_step -> adapter_call -> replan -> fallback`。
- 已落地 `WebReplanPolicy`（按失败/恢复反馈动态调节重规划预算）。

3. 控制面已具备查询与治理基础能力
- `SessionRuntimeServer` 提供 `status/timeline/audit/metrics/metrics-timeseries`。
- 已有 token 鉴权、审计、lockfile 多实例治理、会话索引恢复。

4. 策略治理已补齐关键门禁
- `GuardPolicy` 支持文件热加载 + web 域名 allow/deny（`web_domain_allowlist/web_domain_denylist`）。

5. 回归基线稳定
- 本地执行：`python3 -m unittest discover -s test -p 'test_*.py'`
- 结果：`Ran 122 tests ... OK`

## 2. 深度评估（多维）

## 2.1 架构维度

优点：
- 模块边界已经形成，复用点清晰。
- `runtime_mode` 与 `v2_skip_legacy` 保证了增量改造可控。

问题：
- `orchestrator_v2.py` 仍承担较多桥接职责（legacy 翻译 + 事件编排 + 守护接线）。
- `v2_executor.py` 已增强，但仍是执行器内聚合过多策略逻辑。

## 2.2 Agent 决策链维度

优点：
- 决策顺序明确：`route -> guard -> execute -> verify -> handover`。
- web 失败路径具备多层兜底（replan + fallback action）。

问题：
- `guard=confirm` 最小闭环已落地（pending/approve/reject/timeout），但仍缺批量确认与长期堆积治理。
- 缺统一的“前端确认队列模型 + 多步任务恢复协议”。

## 2.3 鲁棒性与治理维度

优点：
- 事件 schema、watchdog、control-plane audit、metrics 已贯通。
- timeseries 指标可以支持后续状态看板。

问题：
- watchdog 仍缺导出聚合统计的标准接口（仅事件层可查）。
- 状态查询仍依赖内存时间线，长期运行后的归档/冷热分层未完成。

## 2.4 运行与可观测维度

优点：
- 指标面已覆盖 web 关键链路，并支持时间窗口查询。
- 审计过滤与分页能力可用于运维排障。

问题：
- 尚未提供前端消费友好的“稳定字段面板模型”（当前主要是事件流视角）。
- 缺跨实例统一指标视图（当前为单进程内聚合）。

## 2.5 工程可演进维度

优点：
- 新能力均同步了测试与文档，工程节奏健康。
- 关键策略和门禁已外置，可持续迭代。

问题：
- 复用链路（agent-browser）与移动端主链之间仍缺“能力边界自动验证”。
- 端到端回归场景（真实任务脚本）还偏少。

## 3. 文档与代码一致性审查

一致：
1. `integration-blueprint-v1` 与代码状态基本一致（含 metrics-timeseries、WebReplanPolicy、域名门禁）。
2. `implementation-gap-and-reuse-plan-v2` 的“运行指标”与“domain policy”差距项已更新。

仍需补强：
1. 增加“确认流（confirm workflow）”专章与 API 合同。
2. 增加“长期数据治理（归档/分层/导出）”实施文档。

## 4. 更新后的推进计划（R10-R13）

## R9（已完成）：确认流最小闭环

已完成：
1. 新增确认态模型与事件：`pending_confirm/confirm_approved/confirm_rejected/confirm_timeout`。
2. 控制面新增确认接口：`/runtime/confirms`、`/runtime/confirm`。
3. 执行器支持“挂起 -> 决策 -> 继续/交接”最小闭环。

R9.1 待继续：
1. 批量确认与过期清理策略。
2. 多步任务恢复协议（不仅单步）。

## R10（P0，4-6 天）：Web 执行链 v2

目标：
- 从启发式重规划走向“证据驱动”的重规划。

任务：
1. 拆分 `web_planner` 与 `web_executor`，减少 `v2_executor` 职责。
2. 引入更稳定的失败分类（UI/网络/权限/后端）。
3. 把 `snapshot/diff` 证据纳入重规划输入。

退出条件：
- 复杂网页 3-5 步任务成功率和可解释性都高于当前基线。

## R11（P1，3-5 天）：状态面长期治理

目标：
- 让控制面从“可查询”升级到“可长期运行”。

任务：
1. 时间线归档与滚动切片（按 run/session）。
2. 内存索引 + 文件归档联合查询。
3. 输出 watchdog/metrics 聚合摘要接口。

退出条件：
- 长周期运行下内存增长可控，历史查询不退化。

## R12（P1，3-4 天）：回归矩阵与发布门禁

## R13（P1，3-5 天）：状态感知算法强化

目标：
- 将去噪/骨架/快速匹配从启发式 v0 提升到多帧鲁棒版本。

任务：
1. 引入更长窗口时序去噪与漂移补偿。
2. 建立骨架匹配误报样本集与阈值回归。
3. 离线复盘与在线匹配指标联动（命中率、误命中率）。

目标：
- 建立稳定的改造节奏门槛。

任务：
1. 固化 6-10 条端到端回归场景（移动主链 + web 子任务 + fallback）。
2. 增加“移动主链不被 web 侵入”的自动检查。
3. 在 README/运维文档补发布检查单。

退出条件：
- 每轮改造具备统一质量门禁，可快速判断是否可合入。

## 5. Git 推进规范（继续执行）

1. 每阶段打 checkpoint 标签（如 `checkpoint/R9-start`, `checkpoint/R9-done`）。
2. 每项能力按“代码+测试+文档”同提交，禁止只改其一。
3. 每次提交前固定执行：
- `python3 -m unittest discover -s test -p 'test_*.py'`
4. 保持 `legacy` 可回退，不做无回滚的跨阶段混改。

## 6. 执行建议

1. 下一步优先做 R10（Web 执行链 v2）与 R11（状态面治理）。
2. R9.1 与 R13 可并行设计，但建议按“执行链稳定 -> 算法强化 -> 数据治理”顺序落地。
3. R12 仍需在下一轮大改前完成，作为发布门禁。
