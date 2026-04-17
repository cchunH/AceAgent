# 第 5 章伪算法 LaTeX 版本（algorithm2e）

本文档将第 5 章中的核心算法统一改写为 `algorithm2e` 风格，展示效果参考你提供的示例图。该版本更适合中文论文排版，结构清晰，可读性高，也更接近正式论文中“算法 5-x”的常见呈现方式。

## 导言区建议

```latex
\usepackage[ruled,longend,linesnumbered]{algorithm2e}
\usepackage{xeCJK}
```

如需进一步控制中文显示，可在导言区增加：

```latex
\SetKwInput{KwIn}{输入}
\SetKwInput{KwOut}{输出}
\SetKwComment{tcc}{/* }{ */}
```

## 统一书写建议

1. 使用 `\KwIn`、`\KwOut` 表示输入输出。
2. 使用 `\Begin{ ... }` 包裹主体逻辑。
3. 使用 `\ForEach`、`\For`、`\While`、`\If`、`\eIf` 表示流程控制。
4. 每一条语句结尾保留 `\;`，以维持版式整齐。
5. 数学公式仍直接写在算法环境中，例如 `$S_i=\alpha F_i+\beta T_i+\gamma P_i$`。

---

## 算法 5-1 稀疏特征拓扑锚点识别算法

```latex
\begin{algorithm}[htbp]
\caption{稀疏特征拓扑锚点识别算法}
\label{alg:anchor_topology}
\KwIn{页面截图 $I$，OCR 节点集合 $O$，图标候选集合 $C$}
\KwOut{主锚点集合 $A_c$，辅锚点集合 $A_a$，拓扑图 $G$，页面拓扑指纹 $F_{\text{page}}$}
\Begin{
提取文本节点与图标节点，合并为候选集合 $N = O \cup C$\;
\ForEach{候选节点 $n_i \in N$}{
统计采样频率 $F_i$、文本一致性 $T_i$ 与位置稳定性 $P_i$\;
计算综合稳定度 $S_i = \alpha F_i + \beta T_i + \gamma P_i$\;
\eIf{$S_i \geq \tau_c$}{
将 $n_i$ 加入主锚点集合 $A_c$\;
}{
\If{$\tau_a \leq S_i < \tau_c$}{
将 $n_i$ 加入辅锚点集合 $A_a$\;
}
}
}
以 $A_c$ 为主骨架，连接相邻主锚点形成初始边集合 $E_c$\;
将 $A_a$ 按最近邻原则挂接至对应主锚点，形成局部修正边集合 $E_a$\;
构建拓扑图 $G = (A_c \cup A_a,\; E_c \cup E_a)$\;
基于锚点相对距离、方向角与局部邻接关系生成页面拓扑指纹 $F_{\text{page}}$\;
输出 $A_c$、$A_a$、$G$ 与 $F_{\text{page}}$\;
}
\end{algorithm}
```

---

## 算法 5-2 动态去噪与静态骨架提取算法

```latex
\begin{algorithm}[htbp]
\caption{动态去噪与静态骨架提取算法}
\label{alg:denoise_skeleton}
\KwIn{多帧页面序列 $I=\{I_1, I_2, \dots, I_k\}$}
\KwOut{静态骨架 $B$，动态掩模 $M$}
\Begin{
\ForEach{页面帧 $I_j \in I$}{
执行 OCR、图标检测与节点提取\;
}
对跨帧候选节点进行语义与位置对齐\;
\ForEach{对齐后的节点 $n_i$}{
统计频率 $f_i$、漂移量 $p_i$、一致性 $t_i$ 及区域波动率 $v_i$\;
计算骨架分值 $R_i = \lambda_1 f_i + \lambda_2 t_i - \lambda_3 p_i - \lambda_4 v_i$\;
\If{$R_i \geq \tau_s$}{
将节点 $n_i$ 加入静态骨架集合 $B$\;
}
}
\ForEach{页面区域 $q$}{
\If{$\operatorname{Var}(q) > \tau_v$}{
在动态掩模 $M$ 中标记区域 $q$ 为动态噪音区\;
}
}
基于静态骨架 $B$ 更新当前页面的拓扑指纹\;
输出静态骨架 $B$ 与动态掩模 $M$\;
}
\end{algorithm}
```

---

## 算法 5-4 跨设备仿射映射算法

```latex
\begin{algorithm}[htbp]
\caption{跨设备仿射映射算法}
\label{alg:affine_mapping}
\KwIn{参考锚点集合 $P$，实时锚点集合 $Q$，逻辑动作坐标 $c$}
\KwOut{物理动作坐标 $c'$}
\Begin{
对齐 $P$ 与 $Q$ 中的对应主锚点\;
\If{匹配的有效锚点数量 $< 3$}{
\tcc{无法构建可靠仿射映射，启动防御策略}
触发重定位流程或返回保守执行信号\;
输出空结果\;
}
利用最小二乘法求解最佳仿射变换矩阵 $A$\;
计算映射后的物理坐标 $c' = A c$\;
\If{$c'$ 超出目标区域的语义容忍边界}{
执行局部特征比对，进行落点微调\;
}
输出物理动作坐标 $c'$\;
}
\end{algorithm}
```

---

## 算法 5-3 认知回灌与蓝图热修复算法

```latex
\begin{algorithm}[htbp]
\caption{认知回灌与蓝图热修复算法}
\label{alg:blueprint_repair}
\KwIn{成功运行轨迹 $T$，已有蓝图集合 $\mathcal{B}$}
\KwOut{更新后的蓝图集合 $\mathcal{B}'$}
\Begin{
从轨迹 $T$ 中提取页面序列、动作序列与断言结果\;
对相邻状态执行差分分析，生成候选页面节点与动作边\;
\If{页面匹配度与后置校验结果均满足阈值}{
将候选页面节点、动作边及约束规则编译为候选蓝图 $B_{\text{cand}}$\;
\eIf{$\mathcal{B}$ 中存在相似旧蓝图 $B_{\text{old}}$}{
比较 $B_{\text{cand}}$ 与 $B_{\text{old}}$ 的节点指纹差异及边约束差异\;
\eIf{差异属于局部偏移且小于修复阈值}{
生成最小补丁 $P$，对 $B_{\text{old}}$ 执行热修复更新\;
}{
保留候选蓝图 $B_{\text{cand}}$，并将 $B_{\text{old}}$ 标记为待重建状态\;
}
}{
将候选蓝图 $B_{\text{cand}}$ 作为新蓝图写入蓝图集合 $\mathcal{B}$\;
}
}
输出更新后的蓝图集合 $\mathcal{B}'$\;
}
\end{algorithm}
```

---

## 更美观的中文论文增强版

如果你希望算法标题、输入输出与注释更接近中文论文风格，可以在导言区增加如下设置：

```latex
\usepackage[ruled,longend,linesnumbered]{algorithm2e}
\usepackage{xeCJK}

\SetKwInput{KwIn}{输入}
\SetKwInput{KwOut}{输出}
\SetKwComment{tcc}{/* }{ */}
\SetAlCapNameFnt{\bfseries}
\SetAlCapFnt{\bfseries}
\SetAlgoNlRelativeSize{0}
```

这样效果会更接近你给出的示例图：有顶部分隔线、行号、粗体流程关键字，以及更规整的中文显示。

## 使用建议

1. 如果学校模板支持 `algorithm2e`，优先使用本文档版本。
2. 如果学校模板与 `algorithm2e` 冲突，再退回到三线表版本。
3. 正文中建议统一写法，例如：
   - “其核心逻辑如算法 5-1 所示”
   - “动态去噪流程如算法 5-2 所示”
4. 不要在正文中混用“算法 5-x”和“表 5-x”指向同一内容，否则口径会乱。
