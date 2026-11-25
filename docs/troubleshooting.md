# 踩坑与排错

## A. 自定义节点 / 加速

### `H3SLAAttention` 打印 `SLA patch failed; passing the model through unchanged (attention will NOT be sparsified)`

```
ModuleNotFoundError: No module named 'triton'
```

该节点（`ComfyUI-PlagueKind-Nodes` 的 `ComfyUI-H3-SLA-Attention/`）依赖 triton 的 kernel。**Windows 原生 PyTorch 环境没有 triton**，于是节点吞掉异常、回退 dense。

- 后果：文章原版 `01_reference_4step_sla` 工作流能跑，但 10 秒片要 **510 秒**（dense）；同一模型改用原生 `BlockSparseAttention(sla)` 只要 **98.7 秒**。
- 建议：Windows 上**不要**用 `H3SLAAttention` 做加速；用原生节点。只有 Linux / WSL2 才有 triton 的完整路径。

### 装了节点包但界面里看不到

ComfyUI 在启动时加载 `custom_nodes/`，**装完必须重启**（Desktop 菜单 Restart，或关掉重开）。验证：

```bash
python scripts/verify_workflow.py --server http://127.0.0.1:8188
```

## B. 模型 / 显存

### GGUF 特别慢：`compatibility mode 'sd.cpp'`

Q8 GGUF 基座在 ComfyUI 里走 `sd.cpp` 兼容路径，16GB 显存还要卸载 ~9.9GB 到内存，实测 3 秒片 **16.5 分钟**。换成官方 `int8_convrot` + turbo8 LoRA 后同样任务 **47 秒**。**图生视频优先用 int8 权重，不要用 GGUF。**

### OOM / 系统变卡

- 16GB 卡跑 1152×640×243 帧时显存峰值 ≈15.5GB，可用内存可能只剩 3GB。
- 手段：降分辨率（0.4–0.5 MP）、缩短时长（124 帧）、开 `BlockSparseAttention`、关掉浏览器/其他占显存的程序。

## C. 参数

### 网格状伪影 / 画面发灰

shift 和权重不匹配。**8 步 V2 权重用 10/3；4 步 V1 与 turbo8 用 12/3。** ComfyUI 自带模板是给 8 步 V2 的，直接拿模板跑 4 步 V1 就会踩这个坑。

### 帧数被「四舍五入」

H3 的 `length` 只接受 17k+5 网格（73 / 124 / 243 / 362…）。模板里用 `ComfyMathExpression` 做吸附：

```
max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17
```

### `CLIPLoader` 报类型错误

`type` 必须选 **`minimax`**，不是 `qwen_image` 或 `wan`。

## D. 工作流

### 文章里的工作流打不开 / 缺文件

文章那套 `01–05` 依赖两个第三方节点包：

```bash
cd <ComfyUI>/custom_nodes
git clone https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes
git clone https://github.com/matlowai/ComfyUI-MAINodes
```

装完重启。其中 `03_derope_*` 还需要一个 `minimax_h3_temporal_expansion_step375_r16.safetensors` LoRA（放 `models/loras/`），`05_ref2va_*` 需要你在 `LoadImage` 里放自己的参考图。

### GUI 工作流的子图控件「改了不生效」

新版 ComfyUI 的子图（Subgraph）把部分控件「提升」到了实例节点上，同时内部节点还保留一份默认值。改模型/步数时，**先确认改的是实例节点上露出来的那个控件**（或直接改内部节点），两边不一致时以实例节点为准。

## E. 性能

### 第二条比第一条慢

模型/文本编码器被卸载又重载。连续出片时保持同一组权重，脚本批量跑（`scripts/run_batch.py`）会自动复用缓存。

### 想再快

- 用 turbo8 + SLA（本仓库最快：10 秒 ≈100 秒、15 秒 ≈167 秒）
- 分辨率降到 0.4 MP
- 时长 5 秒分段
- 确实需要 2K/更长：上 24GB 以上显卡，或走官方 API
