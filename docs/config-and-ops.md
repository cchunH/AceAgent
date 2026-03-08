# 配置、运行与产物

## 关联阅读

- 总览：[`project-overview.md`](./project-overview.md)
- 执行流程：[`execution-flow.md`](./execution-flow.md)
- 模块定位：[`module-locator-index.md`](./module-locator-index.md)

## 1. 配置入口

统一配置在 `config.py`，分为四类：
- `Paths`：`ADB_PATH`、`TEMP_DIR`、`SCREENSHOT_DIR`、`LOG_ROOT`
- `API`：`BACKBONE_TYPE`、API key、API URL
- `Models`：Planner/Executor/Verifier/Notetaker/Evolution/JSON Repair 模型
- `AgentSettings`：初始 heuristics、步间等待时间

建议通过环境变量覆盖，而不是改源码：
- `BACKBONE_TYPE`
- `OPENAI_API_KEY` / `SILICONFLOW_API_KEY`
- `PLANNER_MODEL`、`EXECUTOR_MODEL` 等
- `ADB_PATH`

## 2. 运行方式

### 2.1 单任务

```bash
python run.py \
  --instruction "打开地图并搜索最近的咖啡店" \
  --run_name demo_single \
  --setting evolution \
  --runtime_mode legacy
```

### 2.2 多任务

```bash
python run.py \
  --tasks_json ./tasks.json \
  --run_name demo_batch \
  --setting evolution \
  --runtime_mode guiagent_v2_shadow \
  --enable_experience_retriever
```

说明：
- 多任务模式下会复用同一个 `Perceptor` 实例，减少模型重复加载。
- 当前实现在每个任务后有 `Press Enter to continue` 人工确认步骤。

## 3. 模式差异

`--setting individual`：
- 不创建/不更新跨任务持久化知识文件。

`--setting evolution`：
- 在 `logs/.../<run_name>/` 下维护：
  - `persistent_heuristics.txt`
  - `persistent_skills.json`
- 每个任务完成后增量更新，后续任务直接继承。

`--runtime_mode legacy`：
- 原有执行主链。

`--runtime_mode guiagent_v2_shadow`：
- 启用 GUIAgent v2 运行时骨架（shadow），同时委托 legacy 执行。
- 会额外输出 `events.jsonl` 结构化事件。

`--runtime_mode guiagent_v2`：
- 与 `guiagent_v2_shadow` 共用当前骨架，预留后续真实 v2 执行逻辑接管。
- 可选开启 `--v2_use_live_perception`，将 `Perceptor` 的实时 pre/post 感知注入 v2 step pipeline。

## 4. 日志与文件产物

单任务目录结构（典型）：

```text
logs/<model>/unimind_agent/<run_name>/<task_id>/
  steps.json
  events.jsonl
  blueprints.json
  runtime_summary.json
  heuristics.txt
  skills.json
  screenshots/
  screenrecords/   (可选)
```

`steps.json` 中主要 `operation` 节点：
- `init`
- `experience_retrieval`（可选）
- `perception`
- `planning`
- `action`
- `action_reflection`
- `notetaking`
- `experience_reflection`（结束时）
- `finish`

`events.jsonl` 关键事件（用于 Phase 0 对照）：
- `step_start`
- `action_exec`
- `assertion`
- `handover`
- `step_end`
- `task_end`
- `blueprint_sync`（v2 mobile 分支）

社区对标后的规划补充（未落地代码）：
- 未来会增加执行通道字段：`channel=mobile_native|web_skill`
- Web Skill 旁路事件：`skill_route`、`skill_fallback`
- 该补充用于移动端主链 + Web 子任务旁路的统一观测

当前 v2 mobile 分支已支持蓝图快速匹配提示：
- `fast_match_hint.match_source`：`skeleton|vector|fused`
- 便于区分“结构命中”与“语义近邻命中”的来源

进程内状态 API：
- `guiagent_v2.runtime.get_task_status(run_id, task_id)`
- `guiagent_v2.runtime.get_task_timeline(run_id, task_id)`
- `guiagent_v2.runtime.list_tasks(run_id=None, status=None)`
- `guiagent_v2.runtime.list_run_ids()`
- `guiagent_v2.runtime.submit_task(instruction, runtime_mode, run_name, task_id, run_options)`
- `guiagent_v2.runtime.get_submitted_task(request_id)`
- `guiagent_v2.runtime.list_submitted_tasks(status=None)`

`get_task_status` / `list_tasks` 现包含 `runtime_stats` 聚合字段：
- `fast_match_hits`
- `fast_match_source_counts`（`skeleton|vector|fused|unknown`）
- `blueprint_sync_success`
- `blueprint_sync_failed`

指标计算工具：
- `guiagent_v2.runtime.compute_metrics_from_jsonl(jsonl_path)`
- `guiagent_v2.runtime.write_runtime_summary(log_dir, event_log_path, blueprint_repo)`

蓝图向量检索后端（当前默认内存索引）：
- `BlueprintRepository(file_path, vector_index=None, embedding_fn=None, embedding_dim=32)`
- 可通过 `configure_vector_backend(...)` 替换向量索引适配器或 embedding 函数
- 兼容默认行为：不传参数时仍使用内置 `InMemoryVectorIndex + deterministic_text_embedding`

## 5. 关键参数建议

- `max_itr`：默认 40，探索型任务可适当提高
- `max_consecutive_failures`：默认 5（入口），可防止长时间错误循环
- `max_repetitive_actions`：默认 5，防止重复点击卡死
- `temperature`：默认 0，更稳定；如需探索可适当提高

## 6. 设备前置条件

- Android 设备开启 USB 调试并可被 `adb devices` 识别
- 建议安装并激活 ADB Keyboard（用于 `Type` 稳定输入）
- 首次运行会下载感知模型，需保证网络与磁盘空间
