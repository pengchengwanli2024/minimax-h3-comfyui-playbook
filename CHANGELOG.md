# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- **`verify_workflow.py --static`**：不连 ComfyUI 的离线结构检查（JSON 解析、节点引用完整性），配套 `tests/test_verify_workflow.py` 与 CI 步骤
- **ComfyUI 0.46.0 复测**：`i2v_turbo8` 图生视频 3 秒 **47.1s**（0.43 基线 47.4s）、`base20` 文生视频 3 秒 **34.6s**（测试时 LM Studio 常驻占 7.6 GB 显存）
- 新预设 / 模型组合 **`base20`**：官方 `fl2va_pruned_int8` 跑 20 步、不开加速 LoRA，作为质量基线
- 0.46 复测样片预览（`samples/preview/i2v_046_turbo8_3s*`、`t2v_046_base20_3s*`）
- Issue 模板（Bug / 建议）+ PR 模板 + 本 CHANGELOG

### 变更

- `docs/version-compat.md`：0.46 从「未重测」升级为「复测通过」，补充实测数字
- `docs/benchmarks.md`：新增「ComfyUI 0.46.0 复测」小节
- README（中/英）徽章与基准表补充 0.46 数据，参数卡新增「官方基座 20 步」

## [0.2.0] — 2026-11-25

### 新增

- 英文 README（`README.en.md`），中英互链
- `models.json` 模型清单 + `download_models.py --list-sets / --set / --check`
- `scripts/bench.py`：跑一组任务并输出 Markdown 耗时表
- `tests/`：15 项离线测试（预设构建、节点引用完整性、17k+5 帧网格、JSON、文档链接、README 语言切换）
- GitHub Actions CI：编译 + 单测 + dry-run + 全量 JSON 校验
- `docs/faq.md`、`docs/version-compat.md`、`CONTRIBUTING.md`

### 变更

- README 重写：徽章、语言切换、清单式下载、脚本与文档索引
- 下载器从「临时 `--patterns`」升级为「清单驱动」，保留临时模式
- 恢复「相关项目」链接（[minimax-music3-toolkit](https://github.com/pengchengwanli2024/minimax-music3-toolkit)）

## [0.1.0] — 2026-11-25

### 新增

- 三套实测参数组合：FastH3 4 步 VSA / turbo8 + 原生 SLA / 图生视频 8 步 turbo LoRA
- 4 个 API 工作流 + 1 个 GUI 工作流
- `scripts/run_batch.py`（批量出片）、`scripts/download_models.py`（多线程分段下载）、`scripts/verify_workflow.py`（工作流自检）
- `docs/parameters.md`、`docs/troubleshooting.md`、`docs/benchmarks.md`、`docs/article-notes.md`
- 6 条实测提示词 `prompts/examples.json` + 预览拼图/压缩片段
