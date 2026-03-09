# Shadow 基线执行报告（2026-03-08）

## 1. 执行计划（本轮）

1. 预检查通过后执行 shadow 基线（5 条任务）。
2. 每条任务独立 run_name，保证日志可追溯。
3. 每条任务结束后执行 `blueprint_validation_gate`。
4. 汇总 `run return code` + `validation_gate` 结果，给出是否进入 device 的判断。

## 2. 固定参数

- `runtime_mode=guiagent_v2`
- `v2_skip_legacy=true`
- `mobile_execution_mode=shadow`
- 任务模板：`docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json`
- 门禁阈值：`docs/guiagent-plan/02-phase-0/stable-validation-thresholds-v1.json`
- 执行批次前缀：`shadow_baseline_20260308_235348`

## 3. 预检查结果

- 命令：`python3 scripts/blueprint_preflight.py --blueprint_vector_backend memory`
- 结果：`overall_status=PASS`

## 4. 运行结果汇总

- 批次 JSON 报告：`docs/guiagent-plan/02-phase-0/shadow_baseline_20260308_235348_report.json`
- 任务总数：`5`
- 运行层成功（`run.py rc=0`）：`5/5`
- 门禁结果：
  - `PASS`: `0`
  - `WARN`: `3`
  - `FAIL`: `2`

## 5. 逐任务结果

1. `sv1_wait`
- run: `OK`
- gate: `WARN`
- summary: `logs/shadow_baseline_20260308_235348_sv1_wait/20260308-235358/runtime_summary.json`

2. `sv2_back`
- run: `OK`
- gate: `FAIL`
- final status: `HANDOVER`
- handover reason: `SKELETON_ASSERTION_FAILED`
- summary: `logs/shadow_baseline_20260308_235348_sv2_back/20260308-235407/runtime_summary.json`

3. `sv3_home`
- run: `OK`
- gate: `FAIL`
- final status: `HANDOVER`
- handover reason: `SKELETON_ASSERTION_FAILED`
- summary: `logs/shadow_baseline_20260308_235348_sv3_home/20260308-235416/runtime_summary.json`

4. `sv4_open_settings`
- run: `OK`
- gate: `WARN`
- summary: `logs/shadow_baseline_20260308_235348_sv4_open_settings/20260308-235425/runtime_summary.json`

5. `sv5_search_settings`
- run: `OK`
- gate: `WARN`
- summary: `logs/shadow_baseline_20260308_235348_sv5_search_settings/20260308-235434/runtime_summary.json`

## 6. 结论

1. 系统当前已具备“可运行 shadow 全链路”能力（执行链、日志链、门禁链均跑通）。
2. 但基线任务中 `back/home` 触发了断言失败并导致 handover，说明状态面/骨架断言对该类导航动作仍偏严格。
3. 当前不建议直接扩大 device 覆盖面，建议先针对 `back/home` 做一轮策略修正后再进 device。

## 7. 下一步（建议顺序）

1. 为 `Back/Home` 增加更宽松的后验断言策略（或专门的 reason whitelist）。
2. 复跑同批 shadow，目标：`gate FAIL=0`。
3. 然后再切 `mobile_execution_mode=device` 做第一轮真机回归。
