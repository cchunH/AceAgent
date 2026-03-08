# GUIAgent 蓝图执行现状与稳定实测版本计划 v1

## 文档元信息

- 状态：`active`
- 版本：`v1.0`
- 更新时间：`2026-03-08`
- 对齐基线：`R10-R13`（功能优先主线）
- 代码基线：`main@cb7c57a` 及之后增量

## 1. 结论摘要

1. 方向未跑偏。  
当前实现仍在蓝图主轴：`意图 -> 蓝图匹配 -> 执行校验 -> 回灌复盘 -> 再命中`。

2. 可用性已达“开发可用、受限实测可用”。  
单元/集成回归通过（`161` 个测试），但当前环境缺失 `torch`，本机 CLI 冒烟无法直接启动完整运行链。

3. 蓝图功能已进入“闭环雏形完成”阶段，但未到“稳定实测版”。  
核心链路已打通，算法鲁棒性、设备实测矩阵、发布门禁仍需补齐。

## 2. 与既定计划对齐（R10-R13）

1. `R10`（在线执行链）  
- 状态：`大部分完成`  
- 证据：`orchestrator_v2 -> v2_executor -> action_registry -> pipeline` 主链已稳定；`mobile_execution_mode`、多步执行、guard/handover 可用。

2. `R11`（状态面与回灌治理）  
- 状态：`部分完成`  
- 证据：`scene_denoise/static_skeleton/topology_matcher/fast_match` 已落地；`blueprint_sync + delta` 已落地。  
- 缺口：长窗口多帧鲁棒评估、回灌质量门禁仍偏轻量。

3. `R12`（稳定性与发布门禁）  
- 状态：`部分完成`  
- 证据：watchdog、status_api、metrics、runtime_summary 已具备。  
- 缺口：真实设备回归矩阵、版本冻结门禁、长期归档治理尚未完成。

4. `R13`（检索与算法强化）  
- 状态：`部分完成（推进中）`  
- 证据：`VectorIndexAdapter`、`match_by_vector`、骨架+向量融合匹配、可插拔向量后端、运行时配置链已完成。  
- 缺口：真实向量后端接入实测、召回质量 A/B 评估与阈值固化。

5. `S2`（几何执行强化）  
- 状态：`已启动并完成第一批落地`  
- 证据：`topology_matcher` 已输出 `affine_norm/transform_mode/transform_fit_error`；`StepPipeline` 已接入 `topology_result` 坐标投影；`v2_executor` 已输出 `topology_projection` 事件。  
- 缺口：真实设备多分辨率场景压测、仿射异常样本回滚策略、阈值固化。

## 3. 蓝图能力落地比例（评估）

说明：比例为工程落地成熟度估算（功能、可观测、可测试、可实测四维综合）。

1. 流程 A（编译导航快路径）：`75%`  
- 已有：意图映射、路由、执行、后验检查、事件链。  
- 缺口：真正“意图对齐网关”仍偏规则映射，尚非完整语义授权层。

2. 流程 B（偏离自愈）：`70%`  
- 已有：guard、fallback、handover、loop/watchdog。  
- 缺口：策略分层和失败分类细化仍需实测标定。

3. 流程 C（离线复盘回灌）：`68%`  
- 已有：去噪、骨架、delta patch、offline replay、再命中链路雏形。  
- 缺口：复盘质量评分、自动回滚门禁、长期数据治理。

4. 流程 D（群智联邦分发）：`0%`（明确后置）  
- 当前不纳入近期目标。

5. 全局落地度（不含 D）：约 `71%`  
6. 全局落地度（含 D）：约 `53%`

## 4. 程序可用性评估

1. 代码质量与回归  
- `python3 -m unittest discover -s test -p 'test_*.py'`：`161` tests `OK`。

2. 运行可用性  
- v2 主链逻辑可跑（从测试与模块链路角度）。  
- 当前机器缺少 `torch`，导致 `run.py` 启动时导入 `config.py` 失败（`ModuleNotFoundError: torch`）。

3. 实测结论  
- 当前属于：`工程可迭代版本`，非 `稳定实测交付版本`。  
- 进入真实设备稳定实测前，需先完成环境前置与门禁阶段。

## 5. 你当前任务在总规划中的位置

1. 当前工作属于：`R13 + R12 过渡段`  
- `R13`：检索层强化（向量适配、融合匹配、后端可配置）  
- `R12`：控制面可观测增强（runtime stats、summary 扩展）

2. 不属于：  
- 群智联邦分发（后置）  
- 前端完整产品化界面（当前仅接口与状态面预留）

## 6. 到“稳定蓝图实测版本”还差多少阶段

建议再走 `4` 个阶段后做冻结实测版（建议命名：`guiagent-v2-blueprint-beta1`）。

### Phase S1：环境与实测基线固化（1 阶段）

1. 目标  
- 打通可重复的实测启动链（依赖、设备、最小任务集）。

2. 退出条件  
- 设备实测可重复运行 10 次基础任务，无环境类失败。

### Phase S2：状态面与几何执行强化（1 阶段）

1. 目标  
- 提升动态场景去噪、主辅锚点匹配稳定性。  
- 将仿射从“缩放平移近似”升级为“基于锚点约束估计”。

2. 退出条件  
- 主链场景命中率、误触率达到门槛（由 R12 门禁定义）。

### Phase S3：复盘回灌质量门禁（1 阶段）

1. 目标  
- 增加 replay quality score 与 patch 回滚门禁。  
- 验证“失败->回灌->再命中”在固定场景可稳定复现。

2. 退出条件  
- 闭环回归通过率达标，且无明显回灌污染。

### Phase S4：候选发布冻结与实测版本（1 阶段）

1. 目标  
- 冻结配置、冻结测试集、产出实测包。

2. 退出条件  
- 通过发布门禁后打标签并锁定版本。

## 7. 稳定实测版本的长期计划（保存策略）

1. 分支策略  
- 继续在 `main` 小步提交。  
- 每阶段结束打 checkpoint tag。

2. 标签策略（建议）
- `checkpoint/S1-env-ready`  
- `checkpoint/S2-state-engine-hardened`  
- `checkpoint/S3-replay-gated`  
- `release/guiagent-v2-blueprint-beta1`（用于你实测）

3. 门禁策略（beta1 前必须全部满足）
- 全量回归测试通过。  
- 设备实测用例通过率达标。  
- 关键指标（fast-match、blueprint_sync、handover、retry）在阈值内。  
- 无 P0/P1 阻塞缺陷。

## 8. 下一步执行（立即）

1. 先完成 S1：  
- 固化依赖安装脚本与实测前置检查。  
- 建立最小设备实测任务集（5~10 条）。

2. 并行推进 S2 设计：  
- 增强锚点约束仿射估计。  
- 补多帧时序去噪与回归样本。

3. S2 当前增量（2026-03-08）
- 已新增锚点约束仿射估计器（`state_engine/anchor_transform.py`）并接入拓扑匹配结果。  
- 已将执行坐标投影从“仅屏幕缩放”升级为“优先 affine_norm，回退 scale”。  
- 已新增回归：`test_pipeline_projection.py`、`test_topology_matcher_weighted.py` 仿射断言、`test_v2_executor.py` 拓扑投影事件断言。
- 已新增投影质量门禁：当 `fit_error/锚点对数量/core_confidence` 不达标时，自动回退 `scale`，并输出 `projection_guard_reason`。
- 已新增投影观测指标：`topology_projection_affine_rate/guard_block_rate/fit_error_p50,p95`，用于 S2 阈值收敛。
- 已新增稳定验证门禁脚本：`scripts/blueprint_validation_gate.py`，支持基于 `runtime_summary.json` + 阈值模板输出 `PASS/WARN/FAIL`。

3. 完成 S1 后立即打第一个 checkpoint tag，作为“可运行实测起点”。

## 9. S1 当前落地产物（已执行）

1. 预检查脚本  
- `scripts/blueprint_preflight.py`
- 能输出 `PASS/WARN/FAIL` 与详细检查项，支持保存 JSON 报告。

2. 预检查核心模块  
- `guiagent_v2/runtime/preflight.py`
- 已覆盖：Python/torch/adb/目录可写/蓝图向量后端插件配置检查。

3. 稳定实测任务模板  
- `docs/guiagent-plan/02-phase-0/stable-validation-tasks-v1.json`

4. 稳定实测运行手册  
- `docs/guiagent-plan/02-phase-0/stable-validation-runbook-v1.md`

5. 回归保障  
- `test/test_runtime_preflight.py`

6. 本机预检查结果（2026-03-08）
- 结论：`overall_status=FAIL`
- 关键阻塞：`module:torch` 缺失
- 警告项：`adb`、`transformers` 缺失（当前机器）
