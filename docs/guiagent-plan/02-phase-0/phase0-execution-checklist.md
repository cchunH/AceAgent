# GUIAgent Phase 0 执行清单（契约与基线）

目标：在不破坏现有可运行链路的前提下，完成 GUIAgent 的“契约先行”与“度量先行”基础设施。

## 文档元信息

- 状态：`active`
- 版本：`v0.2`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0`

## 1. 范围定义

### In Scope
- Intent 契约草案与字段冻结（v0）
- Blueprint 核心对象 schema 草案（v0）
- 统一日志字段与指标定义
- 最小 PoC 场景验收标准

### Out of Scope
- 群智网络服务端
- 全量状态面/动作面算法实现
- 旧编排器大规模重构

## 2. 执行任务清单

1. 契约定义（必须）
- 定义 `IntentKey`（`domain:verb:object`）
- 定义 `IntentMetadata`（`aliases/risk/pre_conditions/post_expectations`）
- 定义 `ExecutionAssertion`（`expected_semantics/check_region/fail_policy`）
- 定义 `BlueprintPatch`（`target_state/version/delta/rollback`）

2. 日志与指标（必须）
- 在统一日志中增加：
- `intent_key`
- `assertion_result`（pass/fail + reason）
- `recovery_level`（L1/L2/L3）
- `s2_takeover`（bool）
- 指标口径冻结：
- Task Success Rate
- Step Latency（P50/P95）
- S2 Takeover Rate
- Retry Rate

3. PoC 场景（必须）
- 选择 1~2 个稳定页面流程（例如“打开应用 -> 搜索 -> 进入详情”）
- 定义“旧链路基线”与“新契约链路”对照指标
- 形成首份对照评估报告

4. 组织与评审（建议）
- 每周一次契约评审（字段是否可长期演进）
- 每周一次指标评审（口径是否可复现）

## 3. 验收标准（DoD）

- 契约文档评审通过，字段冻结为 `v0`
- 新旧链路都能产出同结构日志
- 至少 1 个 PoC 场景跑通，并给出对照结果
- Phase 1 输入材料完整：
- Intent 契约
- 日志样本
- 指标报告

## 4. 风险与防护

1. 风险：契约字段反复变动  
- 防护：设定每周冻结窗口，非阻断问题延后到 `v1`。

2. 风险：指标口径不一致  
- 防护：文档中固定统计口径与采样窗口。

3. 风险：PoC 选型过难  
- 防护：先选稳定链路，避免把状态面难题提前引爆。

## 5. 建议交付目录（示意）

```text
docs/guiagent-plan/
  02-phase-0/
    guiagent-v2-module-architecture-v0.md
    contract-v0.md
    logging-metrics-v0.md
    jsonl-log-samples-v0.md
    poc-scenarios-v0.md
    phase0-experiment-report-template.md
    phase0-execution-checklist.md
```
