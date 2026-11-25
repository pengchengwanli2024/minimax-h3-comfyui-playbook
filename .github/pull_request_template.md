## 这个 PR 做了什么

<!-- 一两句话说清：解决什么问题，改成什么样 -->

## 类型

- [ ] 新增模型组合（`models.json`）
- [ ] 新增/修改工作流（`workflows/`）
- [ ] 新增提示词（`prompts/examples.json`）
- [ ] 实测数据（`docs/benchmarks.md`）
- [ ] 脚本 / 工具
- [ ] 文档
- [ ] 修 bug

## 实测数据（涉及生成/性能时必填）

| 项 | 值 |
|---|---|
| GPU / 显存 | |
| ComfyUI 版本 | |
| 权重 | |
| 稀疏注意力 / steps / shift | |
| 分辨率 / 帧数 | |
| 耗时 | |

## 自检

- [ ] `python -m unittest discover -s tests -v` 通过
- [ ] `python scripts/run_batch.py prompts/examples.json --dry-run --outdir /tmp/dryrun` 通过
- [ ] 新增工作流跑过 `python scripts/verify_workflow.py --server ... "workflows/api/*.json"`
- [ ] 没有提交模型权重 / 个人绝对路径 / 大体积样片
- [ ] 如果改了 README 结构，`README.en.md` 已同步
