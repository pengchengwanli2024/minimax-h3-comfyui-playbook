# 与网上教程的差异（含「8GB 显存即可」怎么看）

参考教程：[freedidi《MiniMax H3 最新加速模型！开源无审查，8GB 显存即可本地生成高质量 AI 视频》](https://www.freedidi.com/25385.html)

本文只做事实性对照，不复制其文件；如果你按那篇教程卡住了，这里大概率有答案。

## 1. 「8GB 显存即可」是什么意思

那篇教程的说法成立，但需要附加条件：

- 8GB 只能走 **Q2/Q3 量化的 GGUF** + **更小画布（≤0.4MP）** + **更短时长**；
- 结果通常是「能出片，但慢、细节糊、动作容易崩」；
- 社区同档数据：768p×5s 在 12GB 卡上已是 20–30 分钟量级。

本仓库实测的 **16GB** 档位：0.7MP（1152×640）× 10 秒峰值显存 **≈15.5GB**，可用内存只剩 ~3GB。所以 16GB 是「0.7MP × 10~15 秒」的现实下限，8GB 属于「验证流程能跑通」的档位。

## 2. 文章那套工作流需要额外节点，而且在 Windows 上不会真加速

文章给的 `01_reference_4step_sla` … `05_ref2va_4step_sla` 依赖：

- `PlagueKind/ComfyUI-PlagueKind-Nodes` 的 `ComfyUI-H3-SLA-Attention`（`H3SLAAttention`）
- `matlowai/ComfyUI-MAINodes`（`H3DyRoPE` / `H3V2VInit` / `H3ClockRemap` / `H3AudioRecover` …，去抖动 derope 链）

装好后节点齐全、工作流能打开，但 `H3SLAAttention` 依赖 **triton**，Windows 原生环境装不上，节点会静默回退 dense —— 实测 10 秒片 **510.6 秒**。

**正确做法**：节点包可以装（为了 derope 链 / 打开工作流），但加速用 ComfyUI 原生 `BlockSparseAttention`（`vsa` 或 `sla`），同任务 **98.7 秒**。

## 3. 模型文件名对不上

文章里用的权重（`minimax_h3_fused_refdelta_..._turbo8_...`、`minimax_h3_fastvideo_vsa_..._4step_...`）是社区重打包版本，和 ComfyUI 官方模板里写的（`fastvideo_fasth3_8step_v2_pruned_int8_convrot`）**不是同一个**。直接套模板会报缺文件。本仓库的 `workflows/` 已按实际可下载的权重配好。

## 4. 「8 步模板」与「4 步权重」不能混用

ComfyUI 自带 FastH3 模板：**8 步 V2**，shift **10/3**，VSA 80% 稀疏（keep 20）。
本仓库的 FastH3 **4 步 V1** / turbo8：步数 **4**，shift **12/3**，稀疏 90%（keep 10）。

混用的症状是网格状伪影、画面发灰。这是最容易踩、也最难自己发现的坑。

## 5. 「无审查」= 换文本编码器

教程说的「越狱」是指把 H3 的 Qwen3-VL 文本编码器换成社区微调版（HuggingFace 上的 heretic 系列）。用法不变：`CLIPLoader` 的 `type` 仍选 `minimax`，只在 `clip_name` 处选那个文件。

本仓库不分发此类权重，也不对内容合规作背书；模型权重遵循 MiniMax H3 Community License（含地域限制），请自行评估。

## 6. 文章演示片是提示词产物

教程里那几条片子（开门 POV、图生视频、功夫熊猫）靠的是提示词 + 首帧图。你能复现的是「能力」（同样的模型、参数、音画同步），不是逐帧复刻；画面内容取决于你自己的提示词。

## 7. 图生视频不要用 GGUF

教程把「低显存 GGUF」当卖点。实测在 16GB 卡上，Q8 GGUF 图生视频 3 秒要 **16.5 分钟**（`sd.cpp` 兼容模式 + 9.9GB 卸载），而官方 int8 基座 + turbo8 LoRA 只要 **47 秒**。能装 int8 就别用 GGUF。
