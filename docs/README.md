# Uni-Mind 项目技术文档

本目录包含 Uni-Mind 层次化智能体决策架构的技术文档，基于当前仓库代码（`run.py`、`orchestrator.py`、`UniMind/`、`guiagent_v2/`）整理。

## 文档索引

1. [project-overview.md](./project-overview.md)
   项目定位、核心能力、分层架构、关键对象。

2. [execution-flow.md](./execution-flow.md)
   从入口到任务结束的端到端执行流程。

3. [module-design.md](./module-design.md)
   各模块职责、输入输出、关键实现细节（Agent/感知/设备/API）。

4. [config-and-ops.md](./config-and-ops.md)
   配置项、运行模式、日志产物、常用启动方式。

5. [agent-architecture-deep-dive.md](./agent-architecture-deep-dive.md)
   Agent 架构深潜：职责边界、输入输出契约、协作协议。

## 推荐阅读顺序

1. `project-overview`（建立全局认知）
2. `execution-flow`（对齐系统主路径）
3. `agent-architecture-deep-dive` + `module-design`（深入设计细节）
4. `config-and-ops`（运行与配置）
