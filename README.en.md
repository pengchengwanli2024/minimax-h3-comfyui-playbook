# MiniMax H3 · ComfyUI Field Guide (16 GB VRAM)

[中文](README.md) | **English**

[![CI](https://github.com/pengchengwanli2024/minimax-h3-comfyui-playbook/actions/workflows/ci.yml/badge.svg)](https://github.com/pengchengwanli2024/minimax-h3-comfyui-playbook/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Field notes from running **MiniMax H3** — an open-weights omni-modal model that generates video *with native stereo audio* — locally in ComfyUI on an **RTX 4090 Laptop, 16 GB VRAM / 64 GB RAM (Windows 11)**.
>
> This is a *corrected* version of the popular “8 GB is enough” tutorials: it includes the parameter combinations that actually work, measured timings, the pitfalls that cost hours, a batch runner, and a model downloader.

![15s night-market shot](samples/preview/nightmarket.jpg)

## TL;DR

- **Text → video, 10 s @ 1152×640 with stereo audio: ~100 s** per clip. 15 s: **~167 s**. Image → video 3 s: **~47 s**.
- **Fastest recipe:** community **turbo8** int8 checkpoint + **native `BlockSparseAttention`** (`sla`, keep 10 %, shift 12/3, 4 steps).
- **Do not** use the third-party `H3SLAAttention` node for speed on Windows: it needs `triton`, silently falls back to dense attention and is ~5× slower (510 s vs 98.7 s for the same clip).
- **Do not** use GGUF checkpoints for image-to-video: ComfyUI loads them through a slow `sd.cpp` compatibility path (16.5 min vs 47 s).

## Measured performance

| Task | Weights | Duration | Frames | Cost |
|---|---|---|---|---|
| Text → video | FastH3 4-step VSA | 10.1 s | 243 | 127.9 s (incl. first load) |
| Text → video | turbo8 + native SLA | 10.1 s | 243 | **98.7 s** |
| Text → video | turbo8 + native SLA | **15.1 s** | **362** | **167.4 s** |
| Image → video | official int8 base + turbo8 LoRA (8 steps) | 3.04 s | 73 | **47.4 s** |
| Image → video (avoid) | base Q8 GGUF, 20 steps | 3.04 s | 73 | 986.9 s |
| Article’s original `H3SLAAttention` graph | triton missing → dense | 10.1 s | 243 | 510.6 s |

Full logs and per-run details: [docs/benchmarks.md](docs/benchmarks.md).

## What's in the box

| Path | Contents |
|---|---|
| `workflows/api/` | 4 runnable API workflows (`t2v_turbo8_sla`, `t2v_fasth3_4step_vsa`, `i2v_turbo8_lora`, `t2v_smoke_3s`) |
| `workflows/gui/` | A patched GUI workflow based on ComfyUI’s official FastH3 template |
| `scripts/run_batch.py` | Batch generation from a JSON job list (three presets, dry-run, downloads results via `/view`) |
| `scripts/download_models.py` | Multi-threaded ranged downloader with resume + hf-mirror; `--set` from `models.json`, `--check` to verify local files |
| `scripts/bench.py` | Runs a job set and writes a Markdown timing table |
| `scripts/verify_workflow.py` | Checks a workflow against a running ComfyUI: missing nodes / missing model files |
| `scripts/extract_frames.py`, `make_previews.py` | Frame extraction and preview sheets |
| `models.json` | Curated model sets with exact file paths and sizes |
| `prompts/examples.json` | Six prompts that were actually used (night market, subway, seaside, bookstore, rainy street, POV) |
| `docs/` | Parameters, troubleshooting, benchmarks, differences vs. the original tutorial |
| `samples/preview/` | Contact sheets + compressed MP4 previews |

**No model weights are redistributed** — see [NOTICE.md](NOTICE.md).

## Quick start

```bash
# 0) ComfyUI >= 0.43 (tested on 0.43.0; 0.46 works, model file names changed — see docs/version-compat.md)

# 1) see the curated model sets and download the fastest one
python scripts/download_models.py --list-sets
python scripts/download_models.py --set turbo8_sla --dest "D:/models/comfyui"
python scripts/download_models.py --check --set turbo8_sla --dest "D:/models/comfyui"

# 2) point ComfyUI at that folder (ComfyUI/extra_model_paths.yaml)
#    comfyui:
#        base_path: D:/models/comfyui
#        diffusion_models: diffusion_models
#        text_encoders: text_encoders
#        vae: vae
#        loras: loras

# 3) check a workflow against the running server, then generate
python scripts/verify_workflow.py --server http://127.0.0.1:8188 "workflows/api/*.json"
python scripts/run_batch.py prompts/examples.json --outdir ./outputs
```

Prefer the GUI? Drag `workflows/gui/H3_4step_VSA_T2V_1152x640_10s.json` into ComfyUI, fix the three model dropdowns, press Queue.

## Parameter cards

### ① turbo8 + native SLA — fastest

| Node | Value |
|---|---|
| `UNETLoader` | `minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors` |
| `ModelAttentionBackend` | `comfy kitchen attention` |
| `BlockSparseAttention` | method `sla`, keep_percent **10**, start 0, end 1, min_tokens **8192**, sink `exact_kv_and_rows` |
| `MiniMaxH3SigmaShift` | shift_video **12**, shift_audio **3** |
| Sampler | `res_multistep` / `simple`, steps **4** |

### ② FastH3 4-step VSA (official distillation, T2VA only)

`BlockSparseAttention` method **vsa**, keep 10, start **0.2**, min_tokens **12288**; steps 4; shift 12/3.

### ③ Image → video

Official `fl2va_pruned_int8` + `LoraLoaderModelOnly` turbo8 LoRA (strength 1.0), steps **8**, shift 12/3.

**Always:** width/height multiple of 32; `length` on the **17k+5** frame grid (73≈3 s, 124≈5 s, 243≈10.1 s, 362≈15.1 s); fps 24; short edge ≤ 768; 0.4–0.7 MP is the 16 GB sweet spot.

> ⚠️ ComfyUI’s official FastH3 template targets the **8-step V2** weights (steps 8, shift **10/3**). The 4-step V1 / turbo8 weights need steps 4 and shift **12/3** — mixing them produces grid artifacts.

## Pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `SLA patch failed ... attention will NOT be sparsified` | `H3SLAAttention` needs `triton` (no native Windows build) | Use native `BlockSparseAttention` instead |
| GGUF loads in `compatibility mode 'sd.cpp'`, extremely slow | Compatibility path + forced weight offload | Use `int8_convrot` checkpoint + turbo LoRA |
| Grid/block artifacts, washed-out image | shift mismatch (8-step weights with 12/3, or 4-step with 10/3) | 4-step/turbo8 → 12/3; 8-step V2 → 10/3 |
| `length` rejected | Frame count not on 17k+5 grid | 73 / 124 / 243 / 362 |
| OOM at 10 s / 0.7 MP | 16 GB limit | Lower to 0.4–0.5 MP, shorten, enable sparse attention |

More: [docs/troubleshooting.md](docs/troubleshooting.md).

## Documentation

- [docs/parameters.md](docs/parameters.md) — parameter reference
- [docs/troubleshooting.md](docs/troubleshooting.md) — error catalogue
- [docs/benchmarks.md](docs/benchmarks.md) — measured runs
- [docs/article-notes.md](docs/article-notes.md) — differences vs. the original tutorial, and what “8 GB VRAM” really means
- [docs/version-compat.md](docs/version-compat.md) — ComfyUI 0.43 → 0.46 model naming changes
- [docs/faq.md](docs/faq.md) — FAQ

## License

- Code, workflows and docs: **MIT** ([LICENSE](LICENSE))
- Model weights are **not** included; they follow their upstream licenses (MiniMax H3 Community License, Comfy-Org / FastVideo / Kijai / MATLOWAI) — see [NOTICE.md](NOTICE.md)
- Sample clips are generated outputs, shown for demonstration

## Related projects

- [minimax-music3-toolkit](https://github.com/pengchengwanli2024/minimax-music3-toolkit) — a local MiniMax Music 3 creation workbench on the same 16 GB machine: lyrics → API workflow → batch generation → waveform preview

## Credits

[ComfyUI](https://github.com/comfyanonymous/ComfyUI) · [MiniMax H3 docs](https://platform.minimax.io/docs/guides/local-deploy-h3) · [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) · [FastVideo](https://github.com/hao-ai-lab/FastVideo) · [Kijai](https://huggingface.co/Kijai/MiniMax-H3-experimental) · [MATLOWAI](https://huggingface.co/MATLOWAI/minimax-h3-fused-turbo-int8-convrot)
