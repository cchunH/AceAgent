# GUIAgentV2 分层运行机制实施 Backlog v1

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-04-14`
- 依据文档：
  - `../01-global-analysis/hierarchical-blueprint-runtime-proposal-v1.md`
  - `../01-global-analysis/code-doc-alignment-priority-review-v3.md`
  - `../04-community-benchmark/integration-blueprint-v1.md`
- 目标：把“页面指纹 + 图导航 + L1/L2/L3 + 渐进披露”转成可执行开发任务与验收标准。

## 1. 当前基线（简述）

1. 已有能力
- `state_engine`：去噪、静态骨架、拓扑匹配、快速匹配链路已存在。
- `runtime`：`orchestrator_v2 + v2_executor + blueprint_sync + flow_audit` 已形成最小闭环。
- `v2_skip_legacy`：已支持纯 v2 分支，并加入了 `model_task_plan` 与 `intent_parse_guard` 事件。

2. 当前阻断
- 复杂任务仍可能退化为单步 `Wait`，导致“看似成功但无业务完成”。
- L1/L2/L3 结构尚未完全进入执行主链，更多仍是“单步动作推断”。
- 页面指纹与子任务节点绑定关系不够强，图导航收益不足。

## 2. 实施原则

1. 功能优先：先保证复杂任务可稳定跑通，再做精细优化。
2. 增量改造：不重写 `guiagent_v2` 骨架，只做可回滚增量。
3. 三件套提交：每项任务必须含 `代码 + 测试 + 文档`。
4. 语义一致性优先：`task_end`、`flow_audit`、`validation_gate` 口径必须一致。

## 3. P0 任务（必须先完成）

## P0-1 复杂任务退化拦截（禁止 Wait 假成功）

- 目标
  - 复杂指令在未完成业务目标前，禁止以单步 `Wait` 结束为 SUCCESS。

- 代码落位
  - `guiagent_v2/runtime/v2_executor.py`
  - `guiagent_v2/runtime/flow_audit.py`
  - `guiagent_v2/runtime/validation_gate.py`

- 实施要点
  - 当 instruction 判定为复杂任务且 action=`Wait`：
    - 触发 `intent_parse_guard`。
    - `task_end.status` 只能是 `HANDOVER` 或 `FAILED`，不得 `SUCCESS`。
  - flow audit 增加硬规则：复杂任务单步 `Wait` => `FAIL`。

- 测试
  - 新增：`test/test_v2_executor_wait_guard.py`
  - 新增：`test/test_flow_audit_semantic_success.py`

- DoD
  - 复杂任务（如“给微信好友发消息”）无真实动作时不会成功结束。

## P0-2 L1->L2->L3 最小贯通（纯 v2 主链）

- 目标
  - 在 `--v2_skip_legacy` 下实现“复杂任务 -> 子任务 -> 原子动作”最小可运行闭环。

- 代码落位
  - `guiagent_v2/runtime/model_task_planner.py`（L1->L2）
  - `guiagent_v2/runtime/orchestrator_v2.py`（多步编排）
  - `guiagent_v2/runtime/model_intent_parser.py`（L2->L3 约束输出）

- 实施要点
  - `model_task_plan` 输出结构升级：
    - `task_level`: `L1|L2|L3`
    - `subtasks[]`: 每项含 `subtask_key/page_hint/goal_state`
    - `atomic_candidates[]`
  - orchestrator 按 `subtasks` 循环驱动，不是直接扁平字符串拆分。

- 测试
  - 新增：`test/test_orchestrator_v2_hierarchical_plan.py`
  - 新增：`test/test_model_task_planner_schema.py`

- DoD
  - 复杂指令至少产生 2 个以上子任务时，日志可见 L1/L2/L3 结构事件。

## P0-3 页面指纹与子任务绑定（最小图导航）

- 目标
  - 子任务执行必须带页面命中判定，不命中则重规划或回退。

- 代码落位
  - `guiagent_v2/state_engine/topology_matcher.py`
  - `guiagent_v2/runtime/blueprint_delta.py`
  - `guiagent_v2/runtime/orchestrator_v2.py`

- 实施要点
  - 子任务节点增加字段：`page_fingerprint_id`、`match_threshold`。
  - 执行前先做页面匹配；不满足阈值则禁止下发动作。
  - 事件中记录：`fingerprint_match_score`。

- 测试
  - 新增：`test/test_subtask_page_binding_gate.py`

- DoD
  - 错页场景不再误执行动作，能触发可观测的 replan/handover。

## P0-4 运行与环境一致性收敛（实测阻断清理）

- 目标
  - 保证实测环境下依赖一致，避免 `datasets/LargeList` 等动态崩溃。

- 代码落位
  - `requirements.txt`
  - `scripts/blueprint_preflight.py`
  - `scripts/guiagent_v2_readiness_gate.py`

- 实施要点
  - 固化兼容矩阵（建议记录到 preflight 输出）：
    - `python=3.10`
    - `datasets>=2.21.0`（含 `LargeList`）
    - `modelscope` 对应版本
  - preflight 增加“关键符号探针”：
    - `datasets.load.ALL_ALLOWED_EXTENSIONS`
    - `datasets.LargeList`

- 测试
  - 新增：`test/test_preflight_dependency_probe.py`

- DoD
  - readiness gate 在运行前即可发现并阻断版本不兼容。

## 4. P1 任务（P0 后立即推进）

## P1-1 渐进披露策略器

- 代码落位
  - `guiagent_v2/runtime/context_compactor.py`
  - `guiagent_v2/runtime/orchestrator_v2.py`

- 核心
  - L1 只给子任务导航信息；L2 给页面局部信息；L3 给动作局部信息。

- 验收
  - 长任务 token 成本下降，且成功率不下降。

## P1-2 图边置信度与离线复盘聚合

- 代码落位
  - `guiagent_v2/blueprint_hub/repository.py`
  - `guiagent_v2/runtime/blueprint_sync.py`

- 核心
  - 每次成功执行更新边权重；失败更新惩罚；支持离线聚合重算。

- 验收
  - 重复任务命中率与平均步骤数出现可量化改善。

## P1-3 统一语义成功定义

- 代码落位
  - `guiagent_v2/runtime/validation_gate.py`
  - `guiagent_v2/runtime/status_store.py`
  - `guiagent_v2/runtime/flow_audit.py`

- 核心
  - 定义统一 success contract：动作成功 != 任务成功；必须满足目标状态。

- 验收
  - 三套口径（summary/audit/gate）一致。

## 5. 里程碑建议

1. M1（2-3 天）
- 完成 P0-1、P0-2 基础贯通。

2. M2（2-3 天）
- 完成 P0-3、P0-4 与设备实测首轮。

3. M3（3-5 天）
- 完成 P1-1、P1-2，进入复杂任务稳定优化。

## 6. 实测任务集（建议）

1. 单应用任务
- “打开设置并进入 WLAN 页面”

2. 跨页面任务
- “进入微信指定联系人会话并发送固定文本”

3. 跨应用任务
- “从备忘录复制地址并在地图发起导航”

每个任务必须产出：
- `events.jsonl`
- `runtime_summary.json`
- `blueprints.json`
- 关键步骤截图（前/中/后三联）

## 7. 风险与回退

1. 风险
- 分层计划输出不稳定，可能造成任务抖动。

2. 回退策略
- 保留当前单步链路开关：`GUIAGENT_V2_HIER_PLAN_ENABLED=0/1`。
- 分阶段灰度：先 shadow，再实机执行。

## 8. 建议的立即执行顺序

1. 先做 P0-4（环境探针）避免反复被依赖阻断。
2. 再做 P0-1（防假成功）确保日志可信。
3. 然后做 P0-2（分层主链）+ P0-3（页面绑定）。
4. 通过首轮复杂任务实测后进入 P1。

## 9. 进度评估（2026-04-14）

## 9.1 与计划对比（P0）

1. P0-1 复杂任务退化拦截：`基本完成`
- 已落地：`intent_parse_guard`、`flow_audit` 对非语义成功拦截、`validation_gate` 接入 `flow_audit_status`。
- 剩余：补充“复杂任务目标态未达成”专项回归样例。

2. P0-2 L1->L2->L3 最小贯通：`部分完成`
- 已落地：`model_task_plan` 支持 `subtasks`，`orchestrator_v2` 已透传 `task_level/subtask_key/page_hint/goal_state`。
- 剩余：补 `subtask_planner(L2->L3)` 的独立约束化输出与回归测试。

3. P0-3 页面指纹与子任务绑定：`部分完成`
- 已落地：`page_hint_gate` + `fingerprint_match_score` + 错页 `handover`。
- 剩余：将 `topology_confidence + OCR + fast_match` 融合为统一 `page_fingerprint_score`，并把 `page_fingerprint_id` 挂接到子任务节点。

4. P0-4 环境一致性收敛：`基本完成`
- 已落地：`datasets_runtime_compat` 探针、`requirements` 升级到 `datasets>=2.21.0,<3`。
- 剩余：`readiness_gate` 输出中补“兼容矩阵摘要”并纳入 FAIL 判定。

## 9.2 现阶段还需要几步

结论：到“P0 阶段可收口并进入稳定实测”还需要 **1 步**（前两步已完成首版）。

1. 第一步：统一页面命中评分（已完成首版）
- 目标：`page_fingerprint_score = f(topology_confidence, ocr_hit, fast_match)`。
- 退出条件：错页误执行率下降，且 `events.jsonl` 有统一评分字段。

2. 第二步：子任务节点绑定页面指纹（已完成首版）
- 目标：在子任务元数据和蓝图回灌元数据保存 `page_fingerprint_id/match_threshold`，执行前强校验。
- 退出条件：子任务执行前均有页面绑定检查记录。

3. 第三步：首轮复杂任务实测回归
- 目标：实机跑 3 类任务（单应用、跨页面、跨应用），产出完整日志和截图证据。
- 退出条件：`flow_audit=PASS` 且 `validation_gate!=FAIL`，无“单步 Wait 假成功”。

## 9.3 进入 P1 的判定

满足以下条件即可转入 P1：

1. 复杂任务不再以 `Wait` 单步成功结束。
2. 页面门禁已使用统一评分，并在错页时稳定阻断。
3. 至少 1 轮实机复杂任务回归通过并有可复核证据（日志 + 截图 + summary）。
