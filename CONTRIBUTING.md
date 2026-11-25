# 贡献指南

欢迎 PR！这个仓库的目标很朴素：**把「在多少显存上、用什么参数、花多少时间」这件事说清楚**，所以最有价值的贡献是「可复现的实测数据」和「踩坑记录」。

## 可以贡献什么

| 类型 | 位置 | 要求 |
|---|---|---|
| 新的模型组合 | `models.json` | 给出 HF 仓库、仓库内路径、本地目标路径、参考大小；说明用途与实测耗时 |
| 新的工作流 | `workflows/api/`（或 `workflows/gui/`） | API 格式需通过 `scripts/verify_workflow.py`；GUI 工作流请基于官方模板修改 |
| 新的提示词 | `prompts/examples.json` | 用 `integrated_multimodal_description / overall_soundscape / non_diegetic_music` 结构；长度落在 17k+5 网格 |
| 新的实测数据 | `docs/benchmarks.md` | 注明 GPU、RAM、ComfyUI 版本、权重、分辨率、帧数、是否首次加载 |
| 排错条目 | `docs/troubleshooting.md` | 「现象 → 原因 → 解决」三段式，附关键日志行 |
| 脚本改进 | `scripts/` | 保持零第三方依赖（除 `requests`/`av`/`Pillow` 这些已声明的） |

## 不要提交

- ❌ 模型权重（`.safetensors` / `.gguf`）——仓库不打包权重，`.gitignore` 已排除
- ❌ 含个人路径的脚本（`C:\Users\xxx`、`D:\某个目录`）——请用 `--dest` / 环境变量参数化
- ❌ 含个人信息、API token、会话日志的文件
- ❌ 大体积样片（>2 MB）——请放 640px 压缩预览 + 四宫格拼图

## 本地自检

```bash
pip install requests av Pillow          # 只用得到 requests 跑单元测试
python -m compileall -q scripts tests
python -m unittest discover -s tests -v
python scripts/run_batch.py prompts/examples.json --dry-run --outdir /tmp/dryrun
python scripts/download_models.py --list-sets
python scripts/check_links.py            # Markdown 相对链接检查
```

CI（GitHub Actions）会跑上面这些离线检查；需要 GPU 的实测不会在 CI 里跑。

## PR 检查清单

- [ ] 离线测试通过
- [ ] 新增的 JSON 能被 `json.loads` 解析（CI 会全量校验）
- [ ] 工作流里的模型文件名与 `models.json` 一致（或明确说明是可选替代）
- [ ] 文档用中文写；英文 README 只在结构变化时同步
- [ ] 实测数据写明硬件与版本，不写「理论上」
- [ ] 没有提交权重、个人路径或大文件

## 代码风格

- Python 3.10+，标准库优先；脚本入口都带 `--help` 和 `--dry-run`（能离线验证的尽量离线）
- 不引入 README 里没写的新依赖
- 打印用 `print(..., flush=True)`，方便后台跑脚本时看进度

## 提交信息

中文/英文都可以，建议一行说清「改了什么 + 为什么」：

```
models: 增加 Kijai 4-step VSA 组合与 16GB 实测
troubleshooting: 补充 sd.cpp 兼容模式的日志特征
```
