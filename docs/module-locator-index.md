# 模块定位索引（Module Locator Index）

用于快速定位：入口、职责、上游依赖、下游影响、故障入口、观测信号。

## 1. 入口与编排

| 模块 | 入口职责 | 上游依赖 | 下游影响 | 故障入口 | 观测信号 |
|---|---|---|---|---|---|
| `run.py` | 参数解析、单/多任务分发、模式管理 | CLI 参数、`orchestrator.run_single_task` | 启动整个任务链与持久化策略 | 参数冲突、任务文件格式错误、多任务人工阻塞 | 控制台启动日志、`error_tasks.json` |
| `orchestrator.py` | 全流程编排、终止条件、日志写入、学习收束 | `InfoPool`、Perceptor、Agents、ActionExecutor | 决定任务生命周期与所有状态转移 | 解析失败、验证失败、并发笔记时序 | `steps.json`、截图/录屏产物 |

## 2. Agent 决策层

| 模块 | 入口职责 | 上游依赖 | 下游影响 | 故障入口 | 观测信号 |
|---|---|---|---|---|---|
| `UniMind/agents/base.py` | 定义 `InfoPool`、原子动作签名、初始技能 | 编排层初始化 | 约束全系统状态字段与动作接口 | 字段语义漂移、签名与执行不一致 | `final_info_pool` 快照 |
| `UniMind/agents/expert_track_agents.py` | Planner/Executor/VerifyCore/Notetaker | `InfoPool` + 截图/感知结果 | 输出计划、动作、验证、笔记 | Prompt 解析失败、动作协议偏差 | `steps.json` 的 planning/action/action_reflection/notetaking |
| `UniMind/agents/evolution_agents.py` | 技能学习、启发式学习、经验检索 | 历史动作与结果、未来任务 | 更新 `skills/heuristics` 并影响后续任务 | 学习结果质量不稳、检索裁剪偏差 | `experience_retrieval`、`experience_reflection` 记录 |
| `UniMind/agents/fast_track_agents.py` | 快轨一体化决策 + 快速验证 | `InfoPool`、OCR、图像哈希 | 快速执行或回退专家轨 | JSON 协议失败、checkpoint 校验偏差 | FastTrack debug 输出与步骤日志 |

## 3. 感知层

| 模块 | 入口职责 | 上游依赖 | 下游影响 | 故障入口 | 观测信号 |
|---|---|---|---|---|---|
| `UniMind/perception/perceptor.py` | 截图获取、OCR、icon 检测、icon 描述融合 | ADB、modelscope、VLM API | 提供 Executor/Planner 关键可操作信息 | 模型加载失败、识别噪声、临时目录异常 | 感知日志、`screenshots/*` |
| `UniMind/perception/text_localization.py` | OCR 检测后文字识别与框转换 | OCR pipeline、OpenCV | 影响文本点击与验证质量 | OCR 返回异常、框排序误差 | 感知文本列表 |
| `UniMind/perception/icon_localization.py` | 图标框检测与去重过滤 | GroundingDINO、IoU 策略 | 影响 icon 语义理解与点击点 | 误检/漏检、大框过滤误差 | icon 坐标列表 |
| `UniMind/perception/crop.py` | 图像透视裁剪与几何工具 | OpenCV、PIL | 影响 OCR 图块质量 | 几何变换边界问题 | 中间图块（temp） |

## 4. 执行层

| 模块 | 入口职责 | 上游依赖 | 下游影响 | 故障入口 | 观测信号 |
|---|---|---|---|---|---|
| `UniMind/device/action_executor.py` | 动作 JSON 解析、原子动作执行、技能展开 | `ATOMIC_ACTION_SIGNITURES`、controller | 直接改变设备状态 | JSON 修复失败、skill 子步骤失败 | 执行截图、错误打印 |
| `UniMind/device/controller.py` | ADB 原子能力封装、输入法治理、截图录屏 | adb 可执行环境、设备连接 | 支撑所有设备交互 | 设备离线、IME 切换失败、截图拉取失败 | 控制台输出、截图文件 |

## 5. API 与工具层

| 模块 | 入口职责 | 上游依赖 | 下游影响 | 故障入口 | 观测信号 |
|---|---|---|---|---|---|
| `UniMind/utils/api_client.py` | LLM/VLM 请求、重试、usage 跟踪、JSON 修复辅助 | API key/URL、网络 | 影响全部 Agent 推理稳定性 | 网络失败、响应结构变化、耗时统计异常 | 控制台耗时日志、usage jsonl |
| `UniMind/utils/image_utils.py` | 图像裁剪、坐标标注、base64 编码 | PIL、文件系统 | 支撑感知与多模态请求 | 文件路径/格式异常 | 输出图与编码数据 |
| `UniMind/agents/utils/json_utils.py` | 多层 JSON 修复与提取 | 正则、动作签名 | 提升动作协议鲁棒性 | 误修复导致语义错误 | 解析失败打印 |
| `UniMind/agents/utils/prompt_utils.py` | 统一拼装多模态消息 | 图像编码函数 | 影响所有 Agent 输入一致性 | 图像编码失败、消息格式异常 | API 请求体行为 |

## 6. 常见排障入口（按症状）

- 症状：动作不执行或异常终止  
  首查：`UniMind/device/action_executor.py`、`UniMind/agents/utils/json_utils.py`、`steps.json` 的 action 节点。

- 症状：能执行但总失败（B/C）  
  首查：`UniMind/perception/perceptor.py`、`UniMind/agents/expert_track_agents.py` 的 VerifyCore 输出。

- 症状：多任务跑不完、需要人工干预  
  首查：`run.py` 多任务循环与 `input` 阻塞点。

- 症状：耗时不稳定、吞吐低  
  首查：`controller.py`/`action_executor.py` 固定 sleep 与 `api_client.py` 调用耗时。

