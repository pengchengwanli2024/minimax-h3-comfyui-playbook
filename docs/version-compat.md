# ComfyUI 版本兼容性

| ComfyUI | 状态 | 说明 |
|---|---|---|
| **0.43.0** | ✅ 全部实测 | 本仓库大部分耗时数据来自这个版本；原生 H3 节点 + `BlockSparseAttention` 稳定 |
| **0.46.0** | ✅ 复测通过 | 原生节点名未变；模型文件命名有变化（见下）。已复测：`i2v_turbo8` 图生视频 3 秒 **47.1s**（0.43 基线 47.4s）、`base20` 文生视频 3 秒 **34.6s** |

## 0.43 → 0.46 观察到的变化

在 0.46 的安装里能看到这些 H3 相关文件（0.43 时期的老文件名不一定还在）：

| 角色 | 0.46 里见到的文件 |
|---|---|
| 图生视频/首尾帧基座 | `diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors`（还有 `fl2va_bf16` / `fl2va_pruned_fp8_scaled` / `fl2va_pruned_w6a8` 等变体） |
| 图像条件（新） | `diffusion_models/minimax_h3_image_pruned_int8_convrot.safetensors` + `vae/minimax_h3_image_vae_fp16.safetensors`（具体用途以 ComfyUI 官方节点文档为准） |
| 参考图/编辑 | `diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors` 等 `ref2va` 系列 |
| 文本编码器 | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` 或 `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` |
| VAE | `vae/minimax_h3_video_vae_int8_convrot.safetensors` + `vae/minimax_h3_audio_vae_fp32.safetensors` |
| 加速 LoRA | `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors`、`minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors` |

> 上面仅记录「看到过这些文件」，不代表每个变体都经过本仓库实测。新手建议直接用 `models.json` 里的 `turbo8_sla` / `fasth3_vsa` / `i2v_turbo8` 组合，文件名与工作流严格对应。

## 文件名对不上怎么办

两种做法：

1. **改工作流**：在 ComfyUI 里把 UNETLoader / CLIPLoader / VAELoader / LoraLoader 的下拉框改成你实际下载的文件。
2. **改脚本**：`scripts/run_batch.py` 顶部的 `PRESETS` 字典里就是文件名常量，改完即可。

改完先跑：

```bash
python scripts/verify_workflow.py --server http://127.0.0.1:8188 "workflows/api/*.json"
```

全部 `[OK]` 再提交任务，能省掉很多「提交后才发现缺模型」的时间。

## 升级 ComfyUI 的注意事项

- 升级后**自定义节点要重装/更新**（尤其 `ComfyUI-GGUF` 与任何 H3 相关节点包）
- 官方模板会随版本更新（当前官方 FastH3 模板是 8 步 V2、shift 10/3），**不要**把它和本仓库的 4 步权重混用
- `BlockSparseAttention` 的参数含义（`selection` / `keep_percent` / `min_tokens` / `sink_conditioning`）目前稳定；若未来版本改名，`verify_workflow.py` 会报「缺节点」
