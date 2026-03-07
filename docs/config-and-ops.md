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
  --setting evolution
```

### 2.2 多任务

```bash
python run.py \
  --tasks_json ./tasks.json \
  --run_name demo_batch \
  --setting evolution \
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

## 4. 日志与文件产物

单任务目录结构（典型）：

```text
logs/<model>/unimind_agent/<run_name>/<task_id>/
  steps.json
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

## 5. 关键参数建议

- `max_itr`：默认 40，探索型任务可适当提高
- `max_consecutive_failures`：默认 5（入口），可防止长时间错误循环
- `max_repetitive_actions`：默认 5，防止重复点击卡死
- `temperature`：默认 0，更稳定；如需探索可适当提高

## 6. 设备前置条件

- Android 设备开启 USB 调试并可被 `adb devices` 识别
- 建议安装并激活 ADB Keyboard（用于 `Type` 稳定输入）
- 首次运行会下载感知模型，需保证网络与磁盘空间
