# 稳定实测运行手册 v1（S1）

## 1. 目标

在真实设备实测前，先完成统一前置检查，避免因环境缺失导致误判“功能失败”。

## 2. 前置检查（必须）

```bash
python3 scripts/blueprint_preflight.py \
  --require_adb \
  --blueprint_vector_backend memory \
  --output_json /tmp/guiagent_preflight_report.json
```

判定标准：
- `overall_status=PASS`：可进入实测。
- `overall_status=WARN/FAIL`：先修复环境后再测。

## 3. Shadow 基线实测（建议先做）

```bash
python3 run.py \
  --tasks_json docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json \
  --runtime_mode guiagent_v2 \
  --v2_skip_legacy \
  --mobile_execution_mode shadow \
  --run_name stable_validation_shadow_v1
```

可选：保留默认动作截图（推荐）；如需关闭可加 `--v2_disable_action_screenshots`。

## 4. Device 模式实测（通过 Shadow 后）

```bash
python3 run.py \
  --tasks_json docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json \
  --runtime_mode guiagent_v2 \
  --v2_skip_legacy \
  --mobile_execution_mode device \
  --v2_use_live_perception \
  --run_name stable_validation_device_v1
```

一键入口（preflight + run + gate）：

```bash
python3 scripts/blueprint_stable_entry.py \
  --tasks_json docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json \
  --run_name stable_validation_entry_v1 \
  --runtime_mode guiagent_v2 \
  --mobile_execution_mode shadow
```

## 5. 结果检查

1. 日志目录：
- `logs/<model>/unimind_agent/<run_name>/<task_id>/`

2. 关键文件：
- `events.jsonl`
- `runtime_summary.json`
- `blueprints.json`
- `screenshots/`（动作与快照截图）

3. 关键指标：
- `task_success_rate`
- `s2_takeover_rate`
- `fast_match_*`
- `anchor_gate_*`
- `snapshot_*` / `mobile_action_screenshot_*`
- `blueprint_sync_*`（status API 统计）

## 6. 失败定位顺序

1. `preflight` 失败：先修环境（`torch/adb/权限`）。
2. `step_start -> step_end` 缺失：先查执行链。
3. `handover` 高：查断言阈值与锚点匹配。
4. `blueprint_sync` 失败：查回灌输入与 repo 写入路径。

## 7. 自动门禁评估（新增）

在 shadow/device 运行后，对 `runtime_summary.json` 执行门禁评估：

```bash
python3 scripts/blueprint_validation_gate.py \
  --summary_json logs/<model>/unimind_agent/<run_name>/<task_id>/runtime_summary.json \
  --thresholds_json docs/guiagent-plan/02-phase-0/stable-validation-thresholds-v1.json \
  --output_json /tmp/guiagent_validation_gate_report.json
```

判定标准：
- `overall_status=PASS`：可进入下一阶段或版本冻结候选。
- `overall_status=WARN`：允许继续测试，但需记录偏差并复核阈值。
- `overall_status=FAIL`：停止扩面，优先修复失败项后复测。

关键门禁项（v1）：
- `task_success_rate >= 0.7`
- `anchor_gate_deny_rate <= 0.25`
- `topology_projection_guard_block_rate <= 0.25`
- `topology_projection_fit_error_p95 <= 0.2`
