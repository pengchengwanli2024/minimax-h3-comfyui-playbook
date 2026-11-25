#!/usr/bin/env python3
"""跑一组任务，把耗时写成 Markdown 表格（复现 docs/benchmarks.md 用的就是它）。

用法:
  python scripts/bench.py prompts/examples.json --preset turbo8_sla --outdir ./outputs/bench
  python scripts/bench.py prompts/examples.json --markdown docs/benchmarks-run.md --append
  python scripts/bench.py prompts/examples.json --dry-run      # 只校验能否构建，不提交

输出表格列：任务 / 分辨率 / 帧数 / 时长(s) / 耗时(s) / 权重组合
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

_spec = importlib.util.spec_from_file_location("run_batch", HERE / "run_batch.py")
run_batch = importlib.util.module_from_spec(_spec)  # type: ignore[attr-defined]
_spec.loader.exec_module(run_batch)  # type: ignore[union-attr]


def server_info(server: str) -> dict:
    try:
        with urllib.request.urlopen(server.rstrip("/") + "/system_stats", timeout=10) as r:
            s = json.load(r)
        return {"version": s["system"].get("comfyui_version"),
                "device": s["devices"][0].get("name") if s.get("devices") else "unknown",
                "vram_gb": round(s["devices"][0]["vram_total"] / 1e9, 1) if s.get("devices") else 0}
    except Exception:  # noqa: BLE001
        return {"version": "?", "device": "?", "vram_gb": 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--outdir", default="./outputs/bench")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--preset", default="turbo8_sla", choices=sorted(run_batch.PRESETS))
    ap.add_argument("--markdown", default="docs/benchmarks-run.md")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    preset = run_batch.PRESETS[args.preset]
    outdir = Path(args.outdir)

    info = server_info(args.server)
    rows = []
    for job in jobs:
        wf = run_batch.build_prompt(preset, job)
        if args.dry_run:
            rows.append((job, None, wf))
            continue
        t0 = time.time()
        res = run_batch.run_one(args.server, preset, job, outdir)
        rows.append((job, (res[0] if res else None), wf))

    lines = []
    if args.dry_run:
        print(f"{len(rows)} 个任务均可构建（未提交）")
        return

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"\n### 实测（{stamp}，{info['device']} {info['vram_gb']}GB，ComfyUI {info['version']}）\n")
    lines.append("| 任务 | 分辨率 | 帧数 | 时长 | 耗时 | 预设 |")
    lines.append("|---|---|---|---|---|---|")
    for job, dur, _ in rows:
        secs = f"{job['length'] / 24:.2f}s"
        cost = f"{dur:.1f}s" if dur else "失败"
        lines.append(f"| {job['name']} | {job.get('width', 1152)}×{job.get('height', 640)} "
                     f"| {job['length']} | {secs} | {cost} | {args.preset} |")
    block = "\n".join(lines) + "\n"

    md = Path(args.markdown)
    if args.append and md.exists():
        md.write_text(md.read_text(encoding="utf-8") + block, encoding="utf-8")
    else:
        md.write_text("# 实测记录（自动生成）\n" + block, encoding="utf-8")
    print(block)
    print(f"已写入 {md}")


if __name__ == "__main__":
    main()
