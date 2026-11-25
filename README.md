# MiniMax H3 · ComfyUI 本地部署实战手册（16GB 显存实测）

> 在一台 **RTX 4090 Laptop 16GB / 64GB RAM** 的 Windows 机器上，把 MiniMax H3（开源全模态视频模型）跑通的完整记录：可用的参数组合、实测耗时、踩过的坑、批量出片脚本，以及和网上那篇「8GB 显存即可」教程的差异。
>
> **TL;DR** — 文生视频 10 秒（1152×640，带立体声）**约 100 秒**一条，15 秒 **约 167 秒**；图生视频 3 秒 **约 47 秒**。最快的组合是 **turbo8 权重 + ComfyUI 原生 `BlockSparseAttention`**，**别用**依赖 triton 的第三方 SLA 节点（Windows 上会退化成 dense，慢 5 倍）。

<details>
<summary><b>English summary</b></summary>

Field notes from running **MiniMax H3** (open-weights omni-modal video model) locally on a **16 GB RTX 4090 Laptop** with ComfyUI:

- 10 s @ 1152×640 with native stereo audio: **~100 s** per clip; 15 s: **~167 s**; image-to-video 3 s: **~47 s**.
- Fastest recipe: community **turbo8** int8 checkpoint + **native `BlockSparseAttention` (SLA, keep 10%, shift 12/3, 4 steps)**. The third-party `H3SLAAttention` node needs **triton** (unavailable on native Windows) and silently falls back to dense attention — 5× slower.
- This repo ships verified API workflows, a patched GUI workflow, a batch runner, a multi-threaded model downloader, and a troubleshooting guide. **No model weights are redistributed.**

Docs are written in Chinese; code and workflows are language-agnostic.
</details>

![夜市长镜头](samples/preview/nightmarket.jpg)

---

## 这个仓库是什么

网上的教程（例如 freedidi 那篇《MiniMax H3 最新加速模型！开源无审查，8GB 显存即可本地生成高质量 AI 视频》）给的是「怎么做」，但缺了一堆关键细节：模型文件名对不上、加速节点在 Windows 上不生效、shift/steps 配错会出网格伪影、GGUF 版本慢到没法用。

这个仓库是**实测之后的修正版**：

- ✅ 三套**验证过**的参数组合（4 步 VSA / 8 步 turbo LoRA / 原生 SLA），附实测耗时
- ✅ 开箱可用的 API 工作流 + 一个改好的 GUI 工作流
- ✅ 批量出片脚本（改 JSON 就能排队跑）
- ✅ 模型下载脚本（多线程分段 + 断点续传，国内可用 hf-mirror）
- ✅ 踩坑清单：triton 缺失、GGUF `sd.cpp` 兼容模式、17k+5 帧网格、shift 10/3 vs 12/3、显存与内存实测

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
| 图生视频 | 基座 Q8 GGUF（20 步，不推荐） | 3.04s | 73 | 986.9s（16.5 分钟） |
| 对照：文章原版 `H3SLAAttention` 工作流 | triton 缺失 → dense 回退 | 10.1s | 243 | 510.6s |

生成时资源占用：显存约 **15.5 / 16 GB**，内存吃紧（可用内存最低约 3 GB）。因此 16GB 是「能跑 0.7MP×10~15 秒」的实际下限。

预览（压缩版，原片见 `samples/` 说明）：

| 夜市长镜头 15s | 地铁 10s | 海边黄昏 10s |
|---|---|---|
| ![nightmarket](samples/preview/nightmarket.jpg) | ![subway](samples/preview/subway.jpg) | ![seaside](samples/preview/seaside.jpg) |

- 🎬 [夜市长镜头 15 秒（640px 预览）](samples/preview/sla_long_nightmarket_15s_preview.mp4)
- 🎬 [地铁 10 秒（640px 预览）](samples/preview/h3_sla_subway_10s_preview.mp4)
- 🎬 [海边黄昏 10 秒（640px 预览）](samples/preview/sla_seaside_sunset_10s_preview.mp4)

---

## 快速开始

### 1. 环境

- ComfyUI ≥ **0.43.0**（原生 H3 节点 + `BlockSparseAttention` 从这里开始稳定；Desktop 或便携版都行）
- PyTorch 2.12+ / cu130（官方 standalone 包即可）
- 实测显卡：RTX 4090 Laptop 16GB；显存 ≥ 16GB 体验最好，12GB 需要降分辨率/时长

### 2. 下载模型（放到 ComfyUI 的模型目录）

| 文件 | 大小 | 放到 | 来源 |
|---|---|---|---|
| `minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors` | 21.3 GB | `models/diffusion_models/` | [Kijai/MiniMax-H3-experimental](https://huggingface.co/Kijai/MiniMax-H3-experimental)（上游 [FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree](https://huggingface.co/FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree)） |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.5 GB | `models/diffusion_models/` | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) |
| `minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors` | 19.5 GB | `models/diffusion_models/` | [MATLOWAI/minimax-h3-fused-turbo-int8-convrot](https://huggingface.co/MATLOWAI/minimax-h3-fused-turbo-int8-convrot)（社区融合 turbo8，本仓库最快的那套） |
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.8 GB | `models/loras/` | Comfy-Org/MiniMax-H3 |
| （可选）`minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors` | 1.8 GB | `models/loras/` | 同仓库的 4 步版 turbo LoRA，**未实测**，理论上还能再快一倍 |
| `minimax_h3_video_vae_int8_convrot.safetensors` | 2.95 GB | `models/vae/` | Comfy-Org/MiniMax-H3 |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.56 GB | `models/vae/` | Comfy-Org/MiniMax-H3 |
| 文本编码器：`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（官方）或社区微调版 | 14.6 GB | `models/text_encoders/` | Comfy-Org/MiniMax-H3 |

一键下载（多线程、断点续传、hf-mirror 加速）：

```bash
python scripts/download_models.py --dest "D:/models/comfyui" \
  --patterns "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" \
             "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors" \
             "vae/minimax_h3_video_vae_int8_convrot.safetensors" \
             "vae/minimax_h3_audio_vae_fp32.safetensors"
```

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

**A. API 脚本（推荐，可批量）**

```bash
python scripts/run_batch.py prompts/examples.json --outdir ./outputs
```

`prompts/examples.json` 里每条任务就是 `name / prompt / length / width / height / steps / seed`，脚本会提交到 `http://127.0.0.1:8188`、等结果、把成片复制到 `--outdir`。

**B. ComfyUI 界面**

把 `workflows/gui/H3_4step_VSA_T2V_1152x640_10s.json` 拖进 ComfyUI（或「工作流 → 打开」），检查三个下拉框指向你实际下载的模型文件，然后 Queue。这个文件基于 ComfyUI 官方 FastH3 模板修改：权重、文本编码器、步数、shift、分辨率、时长、提示词都已配好。

API 版工作流在 `workflows/api/`：

| 文件 | 用途 |
|---|---|
| `t2v_fasth3_4step_vsa.json` | FastH3 4 步 + 原生 VSA（T2VA） |
| `t2v_turbo8_sla.json` | turbo8 + 原生 SLA（本仓库最快，推荐） |
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

更多见 [docs/troubleshooting.md](docs/troubleshooting.md)，参数细节见 [docs/parameters.md](docs/parameters.md)，完整实测记录见 [docs/benchmarks.md](docs/benchmarks.md)。

---

## 关于「无审查 / 越狱」模型

教程里常提的「越狱文本编码器」是社区在 Qwen3-VL 上做的微调版（例如 HuggingFace 上的 heretic 系列），放进 `models/text_encoders/`，`CLIPLoader` 的 `type` 仍选 `minimax` 即可用。**本仓库不提供也不推荐任何权重**，请自行评估其许可与合规性；生成内容的责任由使用者承担。

## 许可

- 本仓库的**代码与文档**：MIT（见 [LICENSE](LICENSE)）
- **模型权重**不在本仓库内，各自遵循其原始许可（MiniMax H3 Community License、Comfy-Org / FastVideo / Kijai / MATLOWAI 等），详见 [NOTICE.md](NOTICE.md)
- 样片仅用于展示生成效果

## 致谢

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) · [MiniMax H3 官方文档](https://platform.minimax.io/docs/guides/local-deploy-h3) · [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) · [FastVideo](https://github.com/hao-ai-lab/FastVideo) · [Kijai](https://huggingface.co/Kijai/MiniMax-H3-experimental) · [MATLOWAI](https://huggingface.co/MATLOWAI/minimax-h3-fused-turbo-int8-convrot) · 以及 ComfyUI 社区早期的 H3 参数探索
