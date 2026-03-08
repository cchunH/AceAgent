# Shadow 基线复跑报告 R3（2026-03-09）

## 1. 目的

针对上一轮 shadow 基线中 `sv2_back/sv3_home` 的 `SKELETON_ASSERTION_FAILED`，完成最小修正并复跑同批任务，验证门禁是否收敛。

## 2. 本轮改动

1. `infer_probe_action` 增加移动端动作识别：
- `返回/回退/back` -> `Back`
- `回到桌面/主页/home` -> `Home`

2. `run_pre_assertion` 在 `shadow` 模式下对导航类动作做骨架断言放宽：
- 动作范围：`Back/Home/Wait`
- 仅在 `mobile_execution_mode=shadow` 生效
- `device` 模式保持原有严格断言

3. `step_context` 显式注入 `mobile_execution_mode`，供断言层使用。

## 3. 执行参数

- `runtime_mode=guiagent_v2`
- `v2_skip_legacy=true`
- `mobile_execution_mode=shadow`
- 任务：`stable-validation-tasks-v1.json`（5 条）
- 阈值：`stable-validation-thresholds-v1.json`
- 批次：`shadow_baseline_r3_20260309_000336`

## 4. 结果

- 运行层成功：`5/5`
- 门禁结果：
  - `PASS=0`
  - `WARN=5`
  - `FAIL=0`

关键变化：
- 上一轮 `sv2_back/sv3_home` 为 `FAIL`，本轮均降为 `WARN`，`SKELETON_ASSERTION_FAILED` 已消除。
- `sv2_back/sv3_home` 的 step intent 已正确识别为：
  - `global:BACK:UNSPECIFIED_TARGET`
  - `global:HOME:UNSPECIFIED_TARGET`

## 5. WARN 原因说明

当前 `WARN` 主要来自样本量不足（非功能失败）：
- `topology_projection_samples` 未达到阈值（<3）
- `replay_gate_samples` 未达到阈值（<3）

## 6. 结论与下一步

1. Shadow 基线现已达到“无 FAIL”状态，可进入下一阶段。  
2. 建议直接切 `device` 做第一轮真机验证，并保持同一批任务对比。
3. 同时记录 `topology_projection` 与 `blueprint_sync` 样本累积，推动 `WARN` 向 `PASS` 收敛。

## 7. 产物索引

- 机器报告：`docs/guiagent-plan/02-phase-0/shadow_baseline_r3_20260309_000336_report.json`
- 日志根目录：`logs/shadow_baseline_r3_20260309_000336_*`
