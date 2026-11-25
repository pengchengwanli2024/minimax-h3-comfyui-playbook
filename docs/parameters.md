# 参数速查（MiniMax H3 in ComfyUI）

> 所有数值均在 RTX 4090 Laptop 16GB / Windows / ComfyUI 0.43.0 上实测过。

## 1. 三套权重组合

| 组合 | 用途 | 步数 | shift | 稀疏注意力 | 备注 |
|---|---|---|---|---|---|
| `fastvideo_vsa_datafree_..._4step_int8` | 文生视频（T2VA） | 4 | 12 / 3 | 原生 `BlockSparseAttention` method=**vsa** | 官方蒸馏 4 步，画质稳 |
| `fused_refdelta_..._turbo8_int8` | 文生视频（T2VA） | 4 | 12 / 3 | 原生 method=**sla** keep 10 | **最快**，社区融合权重 |
| 官方 `fl2va_pruned_int8` + turbo8 LoRA | 图生视频（首帧/尾帧/参考） | 8 | 12 / 3 | 可选 | 不加 LoRA 时用 20 步 |

## 2. 稀疏注意力节点（`BlockSparseAttention`）

| 方法 | 参数 | 适用 |
|---|---|---|
| `vsa` | keep_percent=10，start=0.2，end=1，min_tokens=12288，sink=`exact_kv_and_rows` | 只配 **FastH3-VSA 权重**（带 `to_gate_compress` 层）。它在训练时就是 10% 稀疏 |
| `sla` | keep_percent=10，start=0，end=1，min_tokens=8192，sink=`exact_kv_and_rows` | 配按 SLA 模式训练/融合的权重（本仓库的 turbo8）。开启后约快 35–45% |
| `sol-attn` | tau=1.3（1.0 保留约 16% key 块，1.5 约 7%） | 训练无关，任意 H3 权重都能用，画质略有损失 |

> 序列短于 `min_tokens` 时自动走 dense，所以 3 秒/480p 这类小尺寸开不开稀疏差别不大。

## 3. 采样

| 项 | 取值 |
|---|---|
| sampler | `res_multistep` |
| scheduler | `simple` |
| denoise | 1.0 |
| shift_video / shift_audio | **12 / 3**（4 步、turbo8）；**10 / 3**（官方 8 步 V2） |
| cfg | 1.0（无 CFG，`BasicGuider`） |

## 4. 分辨率 / 时长

- 宽高必须是 **32 的倍数**；短边 ≤ **768**；原生画布约 **1 MP（1344×768）**，但 16GB 卡建议 **0.4–0.7 MP**（864×480 / 960×544 / 1152×640）。
- `length`（帧）必须落在 **17k+5** 网格：`5, 22, 39, …, 73, …, 124, …, 243, …, 362`
  - 73 ≈ 3.0s，124 ≈ 5.2s，**243 ≈ 10.1s**，**362 ≈ 15.1s**（fps 固定 24）
- 超过 362 帧没有充分验证；要做长片建议 5 秒分段 + 首尾帧续写。

## 5. 文本编码器

- `CLIPLoader` 的 `type` 必须选 **`minimax`**。
- 官方权重：`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（14.6GB）；社区微调（如 heretic 系列）文件名不同但用法一致。
- 32B 编码器本身就要 ~15GB 显存，ComfyUI 会动态卸载；内存紧张时生成会明显变慢，属正常。

## 6. 提示词结构（H3 官方推荐的「多模态描述契约」）

```
integrated_multimodal_description: [Shot 1] 镜头/主体/动作/光线…
[Shot 2] …
overall_soundscape: 环境声、对白、音效层次…
non_diegetic_music: 配乐氛围…
风格要求/限制: 不要闪烁、不要变形、不要手指畸形…
```

实测：分镜（Shot）写法对 10 秒多镜头非常有效；把音频描述写清楚，模型会原生生成 32kHz 立体声。
