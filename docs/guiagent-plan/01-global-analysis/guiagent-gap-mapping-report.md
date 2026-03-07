# GUIAgent 蓝图与现有 Uni-Mind 差距映射报告

## 1. 映射总览

| 目标能力（GUIAgent） | 现有模块（Uni-Mind） | 现状判定 |
|---|---|---|
| System 2（意图决策） | `expert_track_agents.py` | 已有基础 |
| System 1（低延迟执行与校验） | `action_executor.py` + `controller.py` + `VerifyCore` | 部分具备 |
| Blueprint Hub（编译蓝图仓） | `skills.json` + `heuristics.txt` | 能力不等价 |
| Intent Library（脑-控-行契约） | `ATOMIC_ACTION_SIGNITURES` | 初级雏形 |
| 状态面（锚点拓扑） | `perceptor.py`（OCR+icon） | 缺核心算法 |
| 动作面（仿射投射） | 绝对坐标执行 | 缺 |
| 认知回灌与差分补丁 | `evolution_agents.py` | 缺补丁机制 |
| Swarm Hub（群智网络） | 无 | 缺 |

## 2. 差距拆解（按系统层）

### 2.1 协议层差距

- 当前：动作协议是 `{name, arguments}` 与自然语言 Prompt 约定混合。
- 目标：统一 Intent 协议，贯穿大脑授权、蓝图索引、小脑断言。
- 需要新增：
- `IntentKey`：`domain:verb:object`
- `IntentMetadata`：`aliases/risk/pre/post_conditions`
- `ExecutionAssertion`：执行前语义校验结构

### 2.2 状态面差距

- 当前：每帧输出可点击元素列表，缺“页面拓扑稳定性评分”。
- 目标：主辅锚点星群 + 容灾投票 + 页面身份置信度。
- 需要新增：
- `AnchorNode` 模型
- 锚点筛选与评分器
- 拓扑匹配器（含法定人数逻辑）

### 2.3 动作面差距

- 当前：主要依赖绝对坐标，跨分辨率泛化依赖模型临场推理。
- 目标：离线相对坐标 + 在线仿射投射 + 局部伴生锚点。
- 需要新增：
- `AffineRuntime`（坐标变换）
- `LocalSenseCheck`（动作前语义断言）
- `PostConditionMatcher`（动作后状态确认）

### 2.4 进化层差距

- 当前：学习输出为文本 heuristics 和技能 JSON。
- 目标：输出可热修复蓝图补丁（Delta Patch）。
- 需要新增：
- 多帧交集“幽灵骨架”提取
- 差分补丁生成器
- 补丁版本与回滚策略

### 2.5 群智网络差距

- 当前：无云端经验聚合与灰度验证链路。
- 目标：探路者上报 -> 共识验证 -> 全网热更新。
- 需要新增：
- `Swarm Hub` 服务
- 脱敏管线
- 金丝雀验证与补丁信任分级

## 3. 复用机会（避免重复造轮子）

1. 感知基础可复用  
- 复用 `perceptor.py` 的 OCR/icon 检测链路作为状态面输入层。

2. 执行基础可复用  
- 复用 `action_executor.py` 与 `controller.py` 的设备动作能力。

3. 学习闭环可复用  
- 复用 `evolution_agents.py` 的任务后反思入口，扩展为蓝图补丁生成。

4. 日志基础可复用  
- 复用 `steps.json` 作为离线进化的回放数据源。

## 4. 不建议直接复用的部分

1. `orchestrator.py` 大一统主循环  
- 与 GUIAgent 的“编译执行引擎”目标耦合度不足。

2. 纯字符串 Prompt/Parse 协议  
- 不利于构建高确定性契约体系。

3. 经验存储模型（skills/heuristics）  
- 可保留兼容层，但不能作为蓝图主数据模型。

## 5. 差距优先级

### P0（必须先补）
- Intent 契约 schema
- 执行前/后断言协议
- 状态面最小锚点匹配器

### P1（短期补）
- 仿射执行引擎
- 蓝图补丁化学习
- 分级自愈策略

### P2（中期补）
- Swarm Hub 群智网络
- 灰度分发与全网免疫

