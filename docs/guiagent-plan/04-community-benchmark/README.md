# 04 Community Benchmark

本目录用于沉淀对社区标杆项目的深度对标审计，目标是为 `guiagent_v2` 提供可复用模块清单、架构灵感与集成蓝图。

## 文件

1. [agent-browser-deep-analysis.md](./agent-browser-deep-analysis.md)
   - `agent-browser` 深度解析（CLI/daemon、协议、安全、快照、流式能力）。

2. [browser-use-deep-analysis.md](./browser-use-deep-analysis.md)
   - `browser-use` 深度解析（Agent 循环、工具注册、事件模型、watchdog、会话服务）。

3. [cross-project-tradeoff-and-patterns.md](./cross-project-tradeoff-and-patterns.md)
   - 两项目横向权衡与复用模式矩阵。

4. [reusable-module-catalog-for-unimind.md](./reusable-module-catalog-for-unimind.md)
   - 面向 Uni-Mind 的可执行复用模块目录（P0/P1/P2）。

5. [integration-blueprint-v1.md](./integration-blueprint-v1.md)
   - 从分析到改造实施的集成蓝图（接口草案、阶段计划、退出条件）。

## 推荐阅读顺序

1. 先读 `agent-browser-deep-analysis` + `browser-use-deep-analysis`，建立事实层认知。
2. 再读 `cross-project-tradeoff-and-patterns`，确定取舍原则。
3. 最后读 `reusable-module-catalog-for-unimind` + `integration-blueprint-v1`，进入改造实施。
