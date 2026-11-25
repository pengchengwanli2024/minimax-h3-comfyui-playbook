# FAQ

### 8 GB 显存真的能跑吗？

能跑，但只能出「能看」的片子：Q2/Q3 GGUF + ≤0.4 MP 画布 + 3–5 秒时长，速度慢、细节糊。日常出片建议 16 GB 起（0.7 MP × 10–15 秒）。

### 24 GB 能到什么档位？

按显存线性推算，1344×768（1 MP）× 10 秒应该能开；364 帧的 15 秒在 0.7 MP 上也有余量。但本仓库没在 24 GB 上实测过，建议先用 `scripts/run_batch.py` 跑单条验证再批量。

### 为什么我跑 10 秒片要十几分钟？

按可能性排序：

1. 用了 `H3SLAAttention`（triton 缺失 → dense），或没开 `BlockSparseAttention`；
2. 用了 GGUF 权重（`sd.cpp` 兼容模式 + 权重卸载）；
3. 第一次运行要加载 20 GB 模型 + 15 GB 文本编码器；
4. 分辨率/时长超了（0.7 MP × 243 帧是 16 GB 的边界）；
5. 显存被别的程序占着（浏览器、LM Studio 之类），ComfyUI 反复搬运权重。

### 生成的视频没有声音 / 声音很糊？

H3 的音频是跟着视频一起生成的，检查三处：

- `VAEDecodeAudio` 是否接了 `minimax_h3_audio_vae_fp32`；
- `CreateVideo` 的 `audio` 输入是否接上；
- `BlockSparseAttention` 的 `sink_conditioning` 用 `exact_kv_and_rows`（它会额外把音频 query 行跑 dense，官方说明这是「保音频」的设置）。

### 提示词可以用中文吗？

可以，中英文都行。官方推荐的写法是「多模态描述契约」：`integrated_multimodal_description` 分镜 + `overall_soundscape` 环境声 + `non_diegetic_music` 配乐（见 `prompts/examples.json`）。分镜写法对 10 秒多镜头特别有效。

### 生成的画面有网格/块状伪影？

shift 配错了。官方 8 步 V2 权重用 **10/3**；本仓库的 4 步 V1 与 turbo8 用 **12/3**。两者不能互换。

### 可以商用吗？

分两层：

- 本仓库的代码/文档是 MIT，随便用；
- **模型权重**遵循 MiniMax H3 Community License（含地域限制等条款），商用需按官方要求获得授权。生成内容的合规、肖像权、平台政策由你负责。

### 能用 LoRA 微调吗？

可以，但不是本仓库的范围。官方路线是 `miles-diffusion` / SGLang 的 LoRA SFT 配方，训练完导出回 ComfyUI 用 `LoraLoaderModelOnly` 加载。本仓库的 turbo LoRA 是官方发布的推理加速 LoRA，不是可训练的适配器。

### 能出 2K 吗？

本地开源权重以 768p（约 1 MP）为主。官方宣传的 2K 依赖未随开源权重发布的 2K / Context-IR 模块，本地一般走「768p 生成 → 超分」的路线。

### 多卡 / 多机可以吗？

ComfyUI 单进程单卡；多卡需要跑多个实例或在外部框架（FastVideo/SGLang）里做并行。16 GB 单卡是本仓库的验证目标。

### 我想贡献一个模型组合/工作流，怎么加？

见 [CONTRIBUTING.md](../CONTRIBUTING.md)：往 `models.json` 加组合、往 `workflows/api/` 加工作流、往 `prompts/examples.json` 加提示词，跑一遍 `python -m unittest discover -s tests` 即可提 PR。
