# GUIAgent 代码与文档实践细节评估（v1）

目标：对当前 `Uni-Mind + docs/guiagent-plan` 进行一轮“可实施性”评估，识别从文档计划走向代码落地的关键阻塞点。

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-07`
- 适用阶段：`Phase 0 进入实施前`

## 1. 评估范围与方法

评估范围：
- 代码：`run.py`、`orchestrator.py`、`UniMind/agents/*`、`UniMind/device/*`、`UniMind/utils/*`
- 文档：`docs/guiagent-plan/*`

评估方式：
- 静态审计（不依赖真机运行）
- 一致性核对（文档契约 vs 代码实现）
- 规范核对（目录、命名、元信息、链接）

## 2. 结论摘要

- 结论：`有条件 Go（仅限 Phase 0 基建实现）`
- 不建议：直接进入 `Phase 1/2` 能力开发
- 核心原因：当前“契约与观测”仍主要停留在文档，运行时代码尚未完成最小闭环对齐

评分（10分制）：
- 文档可导航性：`9.0`
- 文档规范执行度：`6.5`
- 代码-契约一致性：`4.5`
- 实施就绪度（Phase 0）：`6.0`
- 综合：`6.5`

## 3. 关键核查结果

1. 正向结果
- `docs/` 内部链接完整（未发现 broken links）。
- `docs/guiagent-plan` 已按 `01-global-analysis / 02-phase-0 / 03-governance` 分层，结构清晰。
- 代码基础可编译（`python3 -m compileall` 通过）。

2. 量化结果（文档规范）
- `docs/guiagent-plan` 非 README 文档共 `14` 篇。
- 完整具备“文档元信息（状态/版本/更新时间）”的文档：`9` 篇。
- 不满足命名后缀规范（`*-vN.md`）的文档：`6` 篇。

## 4. 问题清单（按优先级）

### P0-1 契约与日志口径未落地到运行时代码

- 问题：`contract-v0` 与 `logging-metrics-v0` 已定义，但主链仍使用 `steps.json` 聚合日志，缺少 `intent_key/assertion_result/recovery_level/s2_takeover/chain_mode/event_type` 等关键字段。
- 证据模块：
  - 文档定义：[logging-metrics-v0.md](../02-phase-0/logging-metrics-v0.md)
  - 代码现状：[orchestrator.py](../../../orchestrator.py)（line 138）
  - 代码现状：[orchestrator.py](../../../orchestrator.py)（line 821）
- 影响：无法按冻结口径做 `legacy vs guiagent_v2` 对照，Phase 0 验收不可执行。
- 建议优先级：`P0`（第一周内完成最小 event logger）

### P0-2 `guiagent_v2` 代码骨架未创建

- 问题：文档已定义 `guiagent_v2` 模块分层，但仓库尚无对应目录与最小实现入口。
- 证据模块：
  - 架构草案：[guiagent-v2-module-architecture-v0.md](../02-phase-0/guiagent-v2-module-architecture-v0.md)
  - 现状：仓库根目录无 `guiagent_v2/`
- 影响：计划无法从“文档阶段”进入“代码验证阶段”，推荐结论缺乏落地抓手。
- 建议优先级：`P0`（先建空骨架 + 最小 `orchestrator_v2` 贯通）

### P0-3 异步记笔记存在一致性风险

- 问题：异步线程读取固定截图路径 `./screenshot/screenshot.jpg`，主循环会复写同一路径；异步线程未纳入生命周期管理。
- 证据模块：
  - 固定路径：[orchestrator.py](../../../orchestrator.py)（line 413）
  - 异步读取：[orchestrator.py](../../../orchestrator.py)（line 107）
  - 线程分派：[orchestrator.py](../../../orchestrator.py)（line 940）
- 影响：`important_notes` 可能与错误截图配对，降低回放和学习可靠性。
- 建议优先级：`P0`（异步前复制独立截图文件；增加线程池/任务回收机制）

### P1-1 默认可变参数风险

- 问题：`run_single_task` 使用 `future_tasks=[]` 默认参数。
- 证据模块：[orchestrator.py](../../../orchestrator.py)（line 84）
- 影响：跨调用共享状态风险，可能引入隐蔽行为。
- 建议优先级：`P1`（改为 `None` 并在函数内初始化）

### P1-2 运行时校验依赖 `assert`

- 问题：核心尺寸一致性检查使用 `assert`。
- 证据模块：[orchestrator.py](../../../orchestrator.py)（line 808）
- 影响：在优化模式下可能失效，异常路径不可控。
- 建议优先级：`P1`（替换为显式异常和结构化错误码）

### P1-3 特性开关治理不足

- 问题：`USE_DUAL_TRACK` 全局硬编码为 `False`，`FAST_TRACK_MODEL` 定义后未实际参与调度。
- 证据模块：
  - [orchestrator.py](../../../orchestrator.py)（line 54）
  - [orchestrator.py](../../../orchestrator.py)（line 55）
- 影响：无法做灰度切换与可重复实验，不利于 Phase 0 对照。
- 建议优先级：`P1`（接入 `config` 或 CLI flag，固化实验矩阵）

### P1-4 日志写入模型效率与健壮性一般

- 问题：循环中多次整文件覆盖写 `steps.json`。
- 证据模块：[orchestrator.py](../../../orchestrator.py)（line 234）
- 影响：I/O 放大，崩溃时可能造成日志不完整；不利于流式观测。
- 建议优先级：`P1`（引入 JSONL append logger，保留 `steps.json` 作为离线聚合产物）

### P2-1 文档规范执行尚未闭环

- 问题：部分全局分析文档缺少“文档元信息”与 `-vN` 后缀；治理文档本身缺元信息。
- 证据模块：
  - 规范要求：[documentation-standard-v1.md](../03-governance/documentation-standard-v1.md)
  - 待补文档：`01-global-analysis` 下多篇报告
- 影响：版本冻结与评审追踪成本升高。
- 建议优先级：`P2`（本周统一补齐元信息，下一轮再做批量重命名）

## 5. 建议的执行顺序（推荐前）

1. 先补 `P0`：`event logger + guiagent_v2 skeleton + async note consistency`
2. 再补 `P1`：参数与校验治理、feature flag、日志写入模型
3. 最后补 `P2`：文档元信息与命名规范收敛

## 6. 下一轮评估触发条件（v2）

满足以下条件后，进入 `code-doc-practice-assessment-v2`：

1. `guiagent_v2/runtime/orchestrator_v2.py` 可跑通最小一条 step
2. 输出 JSONL 且包含 `logging-metrics-v0` 最小关键字段
3. 至少 1 个 PoC 场景可形成 `legacy vs guiagent_v2` 对照报表
