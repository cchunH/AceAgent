# Uni-Mind: Hierarchical GUI Agent with Compiled Execution

## 研究动机

现有移动端 GUI Agent 普遍采用"逐帧解释执行"范式——每一步都依赖视觉语言模型（VLM）对全屏截图进行推理，导致高延迟、高成本、且决策链路不可控。Uni-Mind 提出 **编译式执行（Compiled Execution）** 范式：将 System 2 的慢思考一次性编译为 System 1 的快反射，使后续执行仅需毫秒级拓扑匹配与仿射投影，无需重复调用大模型。

## 核心架构：三层协作

```
┌─────────────────────────────────────────────────────────────┐
│  System 2 — 战略推理层 (Brain)                               │
│  高层规划 · 意图授权 · 异常接管 · 仅在不确定时激活 VLM        │
└────────────────────────────┬────────────────────────────────┘
                             │ Intent Contract (意图契约)
┌────────────────────────────▼────────────────────────────────┐
│  Skill Blueprint — 知识沉淀层 (Navigation Library)           │
│  拓扑指纹 · 锚点星群 · 后置期望 · 版本化热修复               │
└────────────────────────────┬────────────────────────────────┘
                             │ Affine Projection (仿射投影)
┌────────────────────────────▼────────────────────────────────┐
│  System 1 — 反应执行层 (Cerebellum)                          │
│  锚点匹配 · 坐标变换 · 语义断言 · 亚秒级肌肉记忆             │
└─────────────────────────────────────────────────────────────┘
```

**设计哲学**：类比自动驾驶——System 2 是指挥中心（仅处理未知路况），Blueprint 是高精地图（预编译路径），System 1 是车载控制器（实时执行）。

## 关键算法

### 1. 星群锚点拓扑匹配 (Constellation Topology Matching)

受天文导航启发，将 UI 界面抽象为"锚点星群"：从屏幕中提取少量高稳定性特征点（文本/图标），构建稀疏拓扑图。状态识别不依赖全图像素比对，而是通过星群几何关系进行毫秒级匹配。

```
锚点提取 → 核心/辅助分级 → 空间拓扑编码 → 贪心最优匹配 → 置信度评估
```

- 核心锚点（CORE）：高权重，决定页面身份
- 辅助锚点（AUXILIARY）：低权重，辅助精度校正
- 匹配评分：文本相似度 55% + 空间距离 35% + 元数据 10%

### 2. 多帧交集去噪与幽灵骨架 (Multi-Frame Intersection & Ghost Skeleton)

解决"信噪比倒置"问题——移动端界面 90% 像素为动态内容（广告、直播流），仅 10% 为稳定结构。

```
多帧采样 → 空间聚类 → 跨帧投票 → 稳定节点提取 → SHA1 签名生成
```

产物为 **幽灵骨架（Ghost Skeleton）**：一组跨时间稳定的 UI 节点集合及其哈希指纹，支持 O(1) 页面身份判定。

### 3. 动态仿射变换 (Affine Transform Projection)

蓝图记录的坐标基于录制设备，执行设备分辨率/比例可能不同。系统通过已匹配锚点对求解仿射变换矩阵，将蓝图坐标实时投影到当前物理屏幕：

- 3+ 匹配对：完整 6 参数仿射（最小二乘求解）
- 不足时：退化为缩放+平移
- 输出 RMSE 拟合误差作为执行置信度

### 4. 认知回灌 (Cognitive Backfill)

System 2 的探索性推理成果通过"回灌"机制编译为 System 1 的确定性蓝图：

```
动作成功 → 采集前后帧 → 多帧去噪 → 骨架提取 → 质量门控 → 蓝图结构更新 → Delta 补丁
```

质量门控机制确保仅高置信度观测写入蓝图，防止噪声污染知识库。支持版本化 Delta 补丁与回滚。

### 5. 意图契约 (Intent Contract)

层间通信通过结构化契约实现，消除"逻辑漂移"：

| 契约 | 方向 | 内容 |
|------|------|------|
| `ExecutionRequest` | Brain → Cerebellum | 意图键 + 动作载荷 + 语义断言 + 超时策略 |
| `ExecutionResult` | Cerebellum → Brain | 断言结果 + 后置校验 + 恢复等级 + 延迟 |
| `ExecutionAssertion` | 嵌入 Request | 执行前语义预检条件 |

意图键格式：`domain:verb:object`（如 `wechat:tap:send_button`）

## 执行状态机

```
INIT → ROUTED → GUARDED → CONFIRM_PENDING → EXECUTING → VERIFYING → COMPLETED
                                                  │
                                             FALLBACK → EXECUTING_MOBILE
                                                  │
                                             HANDOVER (升级至 System 2)
```

- **GUARDED**: 安全策略红线检查
- **CONFIRM_PENDING**: 高风险动作人工确认
- **FALLBACK**: Web→Mobile 通道降级
- **HANDOVER**: 置信度不足时交还 System 2 重新规划

## 项目结构

```
Uni-Mind/
├── run.py                    # 主程序入口
├── orchestrator.py           # 核心协调器
├── config.py                 # 配置管理
├── UniMind/                  # 基础感知-决策-执行层
│   ├── agents/               # 多智能体（Planner/Executor/Verifier/Notetaker/Evolution）
│   ├── perception/           # 多模态感知（OCR + 图标检测 + VLM）
│   ├── device/               # ADB 设备控制与动作执行
│   └── utils/                # LLM 调用、JSON 修复等工具
├── guiagent_v2/              # 层次化决策架构 v2
│   ├── intent_contract/      # 意图契约 schema 与验证
│   ├── state_engine/         # 状态引擎（去噪/骨架/锚点/拓扑匹配/仿射变换）
│   ├── action_engine/        # 动作引擎（仿射投影/断言校验/后置检查）
│   ├── brain_adapter/        # 脑适配器（System 2 桥接）
│   ├── blueprint_hub/        # 蓝图中心（持久化/补丁/版本管理）
│   ├── retrieval/            # 向量检索（蓝图快速匹配）
│   └── runtime/              # 运行时（编排器/事件总线/状态机/看门狗/循环检测）
├── GUIAgent/                 # 架构设计白皮书（01-11）
├── docs/                     # 技术文档
├── test/                     # 测试套件
└── scripts/                  # 运行与验证脚本
```

## 运行方式

### 环境配置

```bash
# API 通道
export BACKBONE_TYPE="SiliconFlow"       # SiliconFlow / OpenAI / DashScope
export SILICONFLOW_API_KEY="your_key"

# 模型选择
export PLANNER_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
export EXECUTOR_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
export VERIFIER_MODEL="Qwen/Qwen2.5-VL-32B-Instruct"
```

### v2 全链路执行

```bash
python run.py \
  --runtime_mode guiagent_v2 \
  --v2_skip_legacy \
  --instruction "打开浏览器并搜索今天的天气" \
  --v2_enable_model_intent_parser \
  --v2_enable_model_web_replan \
  --v2_enable_model_assertion_repair
```

### v2 独立模型通道

```bash
export GUIAGENT_V2_API_TYPE="DashScope"
export GUIAGENT_V2_API_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
export GUIAGENT_V2_API_KEY="your_key"
export GUIAGENT_V2_INTENT_PARSER_MODEL="qwen3.5-plus"
```

### 运行模式

| 模式 | 说明 |
|------|------|
| `legacy` | 原有 VLM 逐帧推理链路 |
| `guiagent_v2_shadow` | v2 架构以影子模式运行，保留 legacy 作为对照基线 |
| `guiagent_v2` | 完整 v2 层次化决策架构 |

## 论文与代码对应

| 论文概念 | 代码实现 |
|----------|----------|
| 编译式执行范式 | Blueprint 预编译 + 运行时仿射投影 |
| 星群哲学 | `state_engine/anchor_extractor.py` + `topology_matcher.py` |
| 多帧交集去噪 | `state_engine/scene_denoise.py` |
| 幽灵骨架 | `state_engine/static_skeleton.py` |
| 橡皮布仿射变换 | `state_engine/anchor_transform.py` + `action_engine/affine_runtime.py` |
| 意图授权契约 | `intent_contract/schema.py` |
| 语义预断言 | `runtime/default_hooks.py` |
| 后置条件校验 | `action_engine/post_check.py` |
| 认知回灌 | `runtime/blueprint_sync.py` |
| Delta 修正 | `runtime/blueprint_delta.py` |
| 群智热修复 | `blueprint_hub/patch_model.py` |
| 导航偏离与自愈 | `runtime/executor_state_machine.py` HANDOVER/FALLBACK |
| 循环检测 | `runtime/loop_detector.py` |