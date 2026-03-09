# GUIAgent v2 Readiness Gate 执行报告（2026-03-09）

## 1. 结论

当前版本已满足“进入实测阶段”条件。

- 基础门禁（preflight + targeted tests + v2 smoke）`PASS`
- 模型链路门禁（DashScope + qwen3.5-plus + intent_parse）`PASS`
- `agent-browser` 本地集成路径有效，`CLI_NOT_FOUND=0`

## 2. 执行命令

```bash
source scripts/use_guiagent_v2_env.sh
python3 scripts/guiagent_v2_readiness_gate.py --skip_setup --tests_scope targeted
```

```bash
source scripts/use_guiagent_v2_env.sh
python3 scripts/guiagent_v2_readiness_gate.py --skip_setup --skip_tests --smoke_use_models --smoke_timeout_sec 300
```

## 3. 产出报告

1. 基础门禁通过报告：
- `docs/guiagent-plan/02-phase-0/real-test-readiness-20260309_103636.json`

2. 模型链路门禁通过报告：
- `docs/guiagent-plan/02-phase-0/real-test-readiness-20260309_104009.json`

## 4. 本轮稳定性修正

1. `scripts/guiagent_v2_readiness_gate.py`
- smoke 默认切换到 `runtime_mode=guiagent_v2`（v2-only，避免 shadow 误入 legacy）
- 默认指令改为 `open about:blank and take snapshot`，去除外网依赖
- 新增硬门禁：`smoke_ok / task_end_ok`

2. `guiagent_v2/runtime/v2_executor.py`
- `infer_probe_action` 增加 `about:` URL 识别
- 增加中文“浏览器”提示词 web 路由识别

3. `guiagent_v2/runtime/model_*`
- 结构化模型节点默认禁用 `enable_thinking`
- 默认启用 `response_format={"type":"json_object"}`
- 增加节点级超时（默认 35 秒，可配）

4. `scripts/use_guiagent_v2_env.sh`
- 增加结构化节点相关默认环境变量导出

## 5. 建议的实测入口

先做 shadow：

```bash
python3 run.py \
  --tasks_json docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json \
  --runtime_mode guiagent_v2 \
  --v2_skip_legacy \
  --mobile_execution_mode shadow \
  --run_name stable_validation_shadow_v1
```

再做 device：

```bash
python3 run.py \
  --tasks_json docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json \
  --runtime_mode guiagent_v2 \
  --v2_skip_legacy \
  --mobile_execution_mode device \
  --v2_use_live_perception \
  --run_name stable_validation_device_v1
```
