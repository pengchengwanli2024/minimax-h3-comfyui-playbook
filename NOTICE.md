# 第三方组件与许可说明

本仓库**不分发任何模型权重**。下面的清单记录了实测所用组件的来源与许可，仅供使用者自行下载时参考；请以各上游页面当时的许可条款为准。

## 模型权重

| 组件 | 来源 | 许可 |
|---|---|---|
| MiniMax H3 基座权重（`fl2va` 等） | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3)、[MiniMaxAI/MiniMax-H3](https://huggingface.co/MiniMaxAI/MiniMax-H3) | **MiniMax H3 Community License**（含地域限制等条款，商用需按官方要求授权） |
| FastH3 4 步 VSA-DataFree 蒸馏权重 | [FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree](https://huggingface.co/FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree) | 继承 MiniMax H3 Community License |
| int8_convrot 量化重打包 | [Kijai/MiniMax-H3-experimental](https://huggingface.co/Kijai/MiniMax-H3-experimental) | 继承上游权重许可 |
| 社区融合 turbo8 权重 | [MATLOWAI/minimax-h3-fused-turbo-int8-convrot](https://huggingface.co/MATLOWAI/minimax-h3-fused-turbo-int8-convrot) | 继承上游权重许可 |
| Qwen3-VL 文本编码器（官方/社区微调） | [Comfy-Org/MiniMax-H3](https://huggingface.co/Comfy-Org/MiniMax-H3) 等 | 继承 Qwen 相关许可 |

## 软件

| 组件 | 来源 | 许可 |
|---|---|---|
| ComfyUI | [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI) | GPL-3.0 |
| ComfyUI 官方工作流模板（本仓库 GUI 工作流由其修改而来） | [Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates) | 见上游仓库 |
| FastVideo（VSA 注意力实现上游） | [hao-ai-lab/FastVideo](https://github.com/hao-ai-lab/FastVideo) | Apache-2.0 |
| ComfyUI-GGUF | [city96/ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) | Apache-2.0 |
| ComfyUI-PlagueKind-Nodes（含 H3-SLA-Attention，需 triton） | [PlagueKind/ComfyUI-PlagueKind-Nodes](https://github.com/PlagueKind/ComfyUI-PlagueKind-Nodes) | MIT |
| ComfyUI-MAINodes（derope / 时间重映射节点） | [matlowai/ComfyUI-MAINodes](https://github.com/matlowai/ComfyUI-MAINodes) | 见上游仓库 |

## 文章 / 教程

实测参考了 [freedidi 的 MiniMax H3 教程](https://www.freedidi.com/25385.html)（中文）。本仓库不复制、不转售该教程随附的工作流文件；README 中关于差异的讨论属于事实性评论。若你是原作者并认为有不妥，请开 issue 联系。

## 生成内容

仓库内 `samples/` 下的预览拼图与压缩片段由上述模型在本机生成，仅用于展示效果。使用者对自己生成的内容负全部责任，包括但不限于肖像权、著作权、当地法律法规与平台政策。
