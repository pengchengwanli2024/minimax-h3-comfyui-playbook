# 实测记录（Benchmarks）

## 测试环境

| 项 | 值 |
|---|---|
| GPU | NVIDIA RTX 4090 Laptop，16 GB（16376 MiB） |
| CPU / RAM | i9-13980HX / 64 GB |
| 系统 | Windows 11 |
| ComfyUI | 0.43.0（Desktop 独立环境） |
| PyTorch | 2.12.1+cu130 |
| comfy-kitchen | 0.2.40（int8 / convrot 量化 kernel） |
| 输出 | 1152×640，24 fps，H.264 + AAC 32 kHz 立体声（`CreateVideo(fps=24)`） |

耗时取自 ComfyUI `/history` 的 `execution_start → execution_success`，**包含模型加载**（同一权重连续跑时会更快）。

## 文生视频

| # | 权重 | 稀疏注意力 | steps | 帧数/时长 | 耗时 |
|---|---|---|---|---|---|
| 1 | FastH3 4 步 VSA | vsa keep10 / start0.2 | 4 | 243 / 10.1s | 127.9s（首次含 21GB+14.6GB 加载） |
| 2 | FastH3 4 步 VSA | vsa | 4 | 243 / 10.1s | 150.1s（POV 多镜头） |
| 3 | turbo8 | sla keep10 | 4 | 243 / 10.1s | **98.7s** |
| 4 | turbo8 | sla keep10 | 4 | 243 / 10.1s | 101.3s（海边） |
| 5 | turbo8 | sla keep10 | 4 | 243 / 10.1s | 102.4s（书店） |
| 6 | turbo8 | sla keep10 | 4 | **362 / 15.1s** | **167.4s**（夜市） |
| 7 | turbo8 | **无（dense，跑文章原版节点）** | 4 | 243 / 10.1s | 510.6s |

结论：

- 10 秒 ≈ **100 秒**，15 秒 ≈ **167 秒**（长序列成本约 1.6×，不是线性 1.5× 以上）。
- 原生稀疏注意力比 dense 快 **~5×**；`H3SLAAttention`（triton）在 Windows 上等于 dense。
- 首次运行会把 21GB 扩散模型 + 14.6GB 文本编码器从磁盘「流式」载入显存，约 20–60 秒。

## 图生视频（首帧 → 视频，640×352×73 帧）

| 方案 | 步数 | 耗时 |
|---|---|---|
| 官方 `fl2va_pruned_int8` + turbo8 LoRA | 8 | **47.4s** |
| `fl2va_pruned-Q8_0.gguf`（sd.cpp 兼容模式） | 20 | 986.9s（16.5 分钟） |

GGUF 慢的主因不是步数，而是：`sd.cpp` 兼容路径 + 16GB 显存放不下导致 9938MB 卸载到内存。

## 资源占用（10 秒 / 0.7MP，VSA 权重）

| 指标 | 观测 |
|---|---|
| 显存峰值 | ≈ 15.5 GB / 16 GB |
| 可用内存最低 | ≈ 3 GB（64GB 总量） |
| 采样耗时 | 4 步 ≈ 75 秒（≈19 s/step），VSA 生效日志：`VSA: extra_tokens ignored` |

## 复现方式

```bash
# 1) 起 ComfyUI（8188）
# 2) 跑批量脚本，结果会打印每条耗时
python scripts/run_batch.py prompts/examples.json --outdir ./outputs

# 3) 需要精确到毫秒级的记录，直接查 /history/<prompt_id>
curl http://127.0.0.1:8188/history/<prompt_id>
```

> 注意：不同驱动/ComfyUI 版本、是否首次加载、磁盘是否缓存，都会显著影响数字；本表用于横向比较同一台机器上的权重/注意力方案，不是绝对性能承诺。
