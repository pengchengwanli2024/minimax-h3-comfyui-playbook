# MiniMax H3 · ComfyUI 本地部署实战手册（16GB 显存实测）

**中文** | [English](README.en.md)

[![CI](https://github.com/pengchengwanli2024/minimax-h3-comfyui-playbook/actions/workflows/ci.yml/badge.svg)](https://github.com/pengchengwanli2024/minimax-h3-comfyui-playbook/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-0.43%20%7C%200.46-blue)](docs/version-compat.md)

> 在一台 **RTX 4090 Laptop 16GB / 64GB RAM** 的 Windows 机器上，把 MiniMax H3（开源全模态视频模型，视频带原生立体声）跑通的完整记录：可用的参数组合、实测耗时、踩过的坑、批量出片脚本，以及和网上那篇「8GB 显存即可」教程的差异。
>
> **TL;DR** — 文生视频 10 秒（1152×640，带立体声）**约 100 秒**一条，15 秒 **约 167 秒**；图生视频 3 秒 **约 47 秒**。最快的组合是 **turbo8 权重 + ComfyUI 原生 `BlockSparseAttention`**，**别用**依赖 triton 的第三方 SLA 节点（Windows 上会退化成 dense，慢 5 倍）。

![夜市长镜头](samples/preview/nightmarket.jpg)

---

## 这个仓库是什么

网上的教程（例如 freedidi 那篇《MiniMax H3 最新加速模型！开源无审查，8GB 显存即可本地生成高质量 AI 视频》）给的是「怎么做」，但缺了一堆关键细节：模型文件名对不上、加速节点在 Windows 上不生效、shift/steps 配错会出网格伪影、GGUF 版本慢到没法用。

这个仓库是**实测之后的修正版**：

- ✅ 三套**验证过**的参数组合（4 步 VSA / 8 步 turbo LoRA / 原生 SLA），附实测耗时
- ✅ 4 个 API 工作流 + **3 个可直接编辑的 GUI 工作流**（4 步 VSA 文生视频 / turbo8+SLA 文生视频 / turbo8 图生视频）
- ✅ 批量出片脚本 + 基准测试脚本 + 工作流自检脚本
- ✅ 模型清单（`models.json`）与多线程下载器（断点续传 + hf-mirror）
- ✅ 踩坑清单：triton 缺失、GGUF `sd.cpp` 兼容模式、17k+5 帧网格、shift 10/3 vs 12/3、显存与内存实测
- ✅ 离线单元测试 + GitHub Actions CI（JSON、帧网格、工作流引用完整性）

**本仓库不包含任何模型权重**（体积太大且各有许可），只提供代码、工作流、文档和预览样片。

---

## 实测性能（RTX 4090 Laptop 16GB，1152×640，24fps，含原生立体声）

| 任务 | 权重组合 | 时长 | 帧数 | 耗时 |
|---|---|---|---|---|
| 文生视频 | FastH3 4 步 VSA（`fastvideo_vsa_..._4step_int8`） | 10.1s | 243 | **127.9s**（含首次加载） |
| 文生视频 | 同上（POV 多镜头） | 10.1s | 243 | **150.1s** |
| 文生视频 | turbo8 + 原生 SLA | 10.1s | 243 | **98.7s** |
| 文生视频 | turbo8 + 原生 SLA（海边） | 10.1s | 243 | **101.3s** |
| 文生视频 | turbo8 + 原生 SLA（书店） | 10.1s | 243 | **102.4s** |
| **文生视频** | turbo8 + 原生 SLA | **15.1s** | **362** | **167.4s** |
| 图生视频 | 官方 int8 基座 + turbo8 LoRA（8 步） | 3.04s | 73 | **47.4s** |
| 图生视频（**0.46 复测**） | `fl2va_pruned_int8` + turbo8 LoRA（8 步） | 3.04s | 73 | **47.1s** |
| 文生视频（**0.46 复测**） | 官方 `fl2va_pruned_int8`，20 步、无 LoRA | 3.04s | 73 | **34.6s** |
| 图生视频 | 基座 Q8 GGUF（20 步，不推荐） | 3.04s | 73 | 986.9s（16.5 分钟） |
| 对照：文章原版 `H3SLAAttention` 工作流 | triton 缺失 → dense 回退 | 10.1s | 243 | 510.6s |

生成时资源占用：显存约 **15.5 / 16 GB**，内存吃紧（可用内存最低约 3 GB）。因此 16GB 是「能跑 0.7MP×10~15 秒」的实际下限。

预览（压缩版，原片见 [samples/README.md](samples/README.md)）：

| 夜市长镜头 15s | 地铁 10s | 海边黄昏 10s |
|---|---|---|
| ![nightmarket](samples/preview/nightmarket.jpg) | ![subway](samples/preview/subway.jpg) | ![seaside](samples/preview/seaside.jpg) |

- 🎬 [夜市长镜头 15 秒（640px 预览）](samples/preview/sla_long_nightmarket_15s_preview.mp4)
- 🎬 [地铁 10 秒（640px 预览）](samples/preview/h3_sla_subway_10s_preview.mp4)
- 🎬 [海边黄昏 10 秒（640px 预览）](samples/preview/sla_seaside_sunset_10s_preview.mp4)

---

## 快速开始

### 1. 环境

- ComfyUI ≥ **0.43.0**（原生 H3 节点 + `BlockSparseAttention` 从这里开始稳定；0.46 也可用，注意模型命名变化 → [版本兼容](docs/version-compat.md)）
- PyTorch 2.12+ / cu130（官方 standalone 包即可）
- 实测显卡：RTX 4090 Laptop 16GB；显存 ≥ 16GB 体验最好，12GB 需要降分辨率/时长

### 2. 下载模型（清单模式）

`models.json` 里预置了四套组合：`turbo8_sla`（最快文生视频）、`fasth3_vsa`（官方 4 步蒸馏）、`i2v_turbo8`（图生视频）、`base20`（官方基座 20 步，质量基线）。

```bash
# 看有哪些组合、各占多少空间
python scripts/download_models.py --list-sets

# 下载最快的那套（12 线程分段 + hf-mirror + 断点续传）
python scripts/download_models.py --set turbo8_sla --dest "D:/models/comfyui"

# 只检查本地文件是否齐全（按 ±2% 大小校验）
python scripts/download_models.py --check --set turbo8_sla --dest "D:/models/comfyui"
```

各文件与来源：

| 文件 | 大小 | 放到 | 来源 |
|---|---|---|---|
| `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors` | 21.3 GB | `models/diffusion_models/` | [Kijai/MiniMax-H3-experimental](https://huggingface.co/Kijai/MiniMax-H3-experimental)（上游 [FastVideo FastH3 4-step](https://huggingface.co/FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree)） |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.5 GB | `models/diffusion_models/` | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) |
| `minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors` | 19.5 GB | `models/diffusion_models/` | [MATLOWAI/minimax-h3-fused-turbo-int8-convrot](https://huggingface.co/MATLOWAI/minimax-h3-fused-turbo-int8-convrot) |
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.8 GB | `models/loras/` | Comfy-Org/MiniMax-H3 |
| `minimax_h3_video_vae_int8_convrot.safetensors` | 2.95 GB | `models/vae/` | Comfy-Org/MiniMax-H3 |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.56 GB | `models/vae/` | Comfy-Org/MiniMax-H3 |
| 文本编码器：`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（官方）或社区微调版 | 14.6 GB | `models/text_encoders/` | Comfy-Org/MiniMax-H3 |

> 模型统一放别的盘（比如 `D:/models/comfyui`）时，在 ComfyUI 根目录建 `extra_model_paths.yaml`：
>
> ```yaml
> comfyui:
>     base_path: D:/models/comfyui
>     diffusion_models: diffusion_models
>     text_encoders: text_encoders
>     vae: vae
>     loras: loras
> ```

### 3. 跑起来（两种方式）

**A. 批量脚本（推荐）**

```bash
# 先自检：工作流里的节点/模型是否都在（需要 ComfyUI 在跑）
python scripts/verify_workflow.py --server http://127.0.0.1:8188 "workflows/api/*.json"

# 不想先启 ComfyUI 也可以只做结构检查（CI 同款，纯离线）
python scripts/verify_workflow.py --static "workflows/api/*.json" "workflows/gui/*.json"

# 批量出片（默认 turbo8_sla 预设；结果通过 /view 下载到 --outdir）
python scripts/run_batch.py prompts/examples.json --outdir ./outputs
```

`prompts/examples.json` 里每条任务就是 `name / prompt / length / width / height / steps / seed`。

**B. ComfyUI 界面（可编辑的 GUI 工作流）**

`workflows/gui/` 里是三个按 16 GB 实测调好的工作流，拖进 ComfyUI（或「工作流 → 打开」）就能用：

| 文件 | 任务 | 默认参数 |
|---|---|---|
| `H3_turbo8_sla_T2V_1152x640_10s.json` | 文生视频 · 最快 | turbo8 融合权重 + 原生 SLA，4 步，10 秒 |
| `H3_4step_VSA_T2V_1152x640_10s.json` | 文生视频 · 官方蒸馏版 | FastH3 4 步 VSA，10 秒 |
| `H3_turbo8_i2v_1152x640_3s.json` | **图生视频（首帧）** | 官方 int8 基座 + turbo8 LoRA，8 步，3 秒 |

打开后先检查子图里的模型下拉框是否指向你实际下载的文件，然后 Queue。三个文件都是**可直接编辑**的：双击中间的子图节点进入内部，可以改权重、步数、shift、采样器；画布上的 `ResolutionSelector` 改分辨率，`duration` 改时长（秒，帧数自动吸附到 17k+5 网格）。

**图生视频怎么用**：打开 `H3_turbo8_i2v_1152x640_3s.json`，在 `LoadImage` 节点上传首帧图片（默认文件名 `first_frame.png`），提示词里用 `<Picture 1>` 指代它；把子图上的 `turbo_mode` 关掉，就切换到官方 20 步基座做质量对照。另外子图还暴露了 `last_frame` 输入：再接一张尾帧图就是**首尾帧过渡**（flf2v）。

API 版工作流在 `workflows/api/`（批量脚本用）：

| 文件 | 用途 |
|---|---|
| `t2v_turbo8_sla.json` | turbo8 + 原生 SLA（本仓库最快，推荐） |
| `t2v_fasth3_4step_vsa.json` | FastH3 4 步 + 原生 VSA（T2VA） |
| `i2v_turbo8_lora.json` | 图生视频：官方 int8 基座 + turbo8 LoRA（8 步） |
| `t2v_smoke_3s.json` | 3 秒快速验证（省时间） |

```bash
# 提交任意一个 API 工作流
python - <<'PY'
import json, urllib.request
wf = json.load(open("workflows/api/t2v_turbo8_sla.json"))
req = urllib.request.Request("http://127.0.0.1:8188/prompt",
    data=json.dumps({"prompt": wf, "client_id": "me"}).encode(),
    headers={"Content-Type": "application/json"})
print(json.load(urllib.request.urlopen(req)))
PY
```

### 4. 记录你的实测数据

```bash
python scripts/bench.py prompts/examples.json --preset turbo8_sla \
    --outdir ./outputs/bench --markdown docs/benchmarks-run.md
```

会输出一张 Markdown 表格（任务 / 分辨率 / 帧数 / 耗时），直接贴进 issue 或 PR 就是可复现的数据。

---

## 参数速查（照抄就行）

### ① turbo8 + 原生 SLA —— 最快，推荐

| 节点 | 取值 |
|---|---|
| `UNETLoader` | `minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors` |
| `ModelAttentionBackend` | `comfy kitchen attention` |
| `BlockSparseAttention` | method=`sla`、keep_percent=**10**、start=0、end=1、min_tokens=**8192**、sink_conditioning=`exact_kv_and_rows` |
| `MiniMaxH3SigmaShift` | shift_video=**12**、shift_audio=**3** |
| `KSamplerSelect` / `BasicScheduler` | `res_multistep` / `simple`、steps=**4** |

### ② FastH3 4 步 VSA（官方蒸馏版，只支持 T2VA）

| 节点 | 取值 |
|---|---|
| `UNETLoader` | `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors` |
| `BlockSparseAttention` | method=**vsa**、keep_percent=**10**、start=**0.2**、end=1、min_tokens=**12288**、sink=`exact_kv_and_rows` |
| `MiniMaxH3SigmaShift` | shift_video=**12**、shift_audio=**3** |
| 采样 | `res_multistep` / `simple`、steps=**4** |

### ③ 图生视频（首帧/尾帧/参考图）

| 节点 | 取值 |
|---|---|
| `UNETLoader` | 官方 `minimax_h3_fl2va_pruned_int8_convrot` |
| `LoraLoaderModelOnly` | `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16`，强度 1.0 |
| 步数 | **8**（加 LoRA 后）；不加 LoRA 用 20 步 |
| shift | 12 / 3 |

### ④ 官方基座 20 步（质量基线，`base20` 预设 / 模型组合）

| 节点 | 取值 |
|---|---|
| `UNETLoader` | 官方 `minimax_h3_fl2va_pruned_int8_convrot`（不加 LoRA） |
| 步数 | **20**（shift 12 / 3，不开稀疏注意力） |
| 用途 | 判断「加速版是否掉质量」的对照；3 秒 640×352 实测 34.6 秒（0.46） |

**通用**：宽高取 **32 的倍数**；`length` 必须落在 **17k+5** 帧网格上（73≈3s、124≈5s、243≈10.1s、362≈15.1s），fps 固定 **24**；短边 ≤768，0.4–0.7 MP 是 16GB 卡的舒适区。

> ⚠️ **别混用**：ComfyUI 官方 FastH3 模板是给 **8 步 V2** 权重的（steps=8、shift **10/3**）；本仓库的 4 步 V1 / turbo8 必须 steps=4、shift **12/3**。配错会出网格状伪影、画面发灰。

---

## 踩坑清单

| 现象 | 原因 | 解决 |
|---|---|---|
| `H3SLAAttention` 报 `SLA patch failed ... attention will NOT be sparsified` | 该自定义节点依赖 `triton`，Windows 原生装不了 | 别用它，改用原生 `BlockSparseAttention`（Windows 上快 5 倍） |
| GGUF 模型加载显示 `compatibility mode 'sd.cpp'`，慢到 16 分钟/3 秒 | GGUF 走兼容路径 + 显存不够要卸载 9.9GB 到内存 | 换官方 `int8_convrot` 权重（原生 kernel），配 turbo LoRA |
| 画面出现网格/块状伪影、发灰 | shift 与权重不匹配（8 步权重配了 12/3，或 4 步配了 10/3） | 4 步/turbo8 → 12/3；8 步 V2 → 10/3 |
| `length` 不生效/报错 | 帧数不在 17k+5 网格 | 用 73 / 124 / 243 / 362，或用模板里的 Math Expression 自动吸附 |
| 10 秒 0.7MP OOM | 16GB 显存 + 长序列 | 降到 0.4–0.5 MP、缩短时长，或开 `BlockSparseAttention` |
| 第二次生成反而变慢 | 文本编码器/模型被卸载后重新加载 | 连续跑同一套模型时不要频繁切模型 |

更多见 [docs/troubleshooting.md](docs/troubleshooting.md)。

---

## 文档

| 文档 | 内容 |
|---|---|
| [docs/parameters.md](docs/parameters.md) | 参数速查：三套权重、稀疏注意力、采样、分辨率/帧网格、提示词结构 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 排错手册：triton、GGUF、OOM、子图控件、性能 |
| [docs/benchmarks.md](docs/benchmarks.md) | 实测记录与测试环境 |
| [docs/article-notes.md](docs/article-notes.md) | 与原文教程的 7 处差异，「8GB 显存」到底怎么理解 |
| [docs/version-compat.md](docs/version-compat.md) | ComfyUI 0.43 → 0.46 的模型命名变化与升级注意 |
| [docs/faq.md](docs/faq.md) | 常见问题（8GB？24GB？没声音？2K？商用？） |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南（加模型组合 / 工作流 / 实测数据） |

---

## 关于「无审查 / 越狱」模型

教程里常提的「越狱文本编码器」是社区在 Qwen3-VL 上做的微调版（例如 HuggingFace 上的 heretic 系列），放进 `models/text_encoders/`，`CLIPLoader` 的 `type` 仍选 `minimax` 即可用。**本仓库不提供也不推荐任何权重**，请自行评估其许可与合规性；生成内容的责任由使用者承担。

## 许可

- 本仓库的**代码、工作流与文档**：MIT（见 [LICENSE](LICENSE)）
- **模型权重**不在本仓库内，各自遵循其原始许可（MiniMax H3 Community License、Comfy-Org / FastVideo / Kijai / MATLOWAI 等），详见 [NOTICE.md](NOTICE.md)
- 样片仅用于展示生成效果

## 相关项目

- [minimax-music3-toolkit](https://github.com/pengchengwanli2024/minimax-music3-toolkit) —— 同一台 16 GB 机器上的 MiniMax Music 3 本地创作工作台：歌词 → API 工作流 → 批量生成 → 波形预览

## 致谢

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) · [MiniMax H3 官方文档](https://platform.minimax.io/docs/guides/local-deploy-h3) · [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) · [FastVideo](https://github.com/hao-ai-lab/FastVideo) · [Kijai](https://huggingface.co/Kijai/MiniMax-H3-experimental) · [MATLOWAI](https://huggingface.co/MATLOWAI/minimax-h3-fused-turbo-int8-convrot) · 以及 ComfyUI 社区早期的 H3 参数探索
