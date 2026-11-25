#!/usr/bin/env python3
"""检查工作流能否在当前 ComfyUI 上跑：节点是否注册、模型文件是否存在。

用法:
  python verify_workflow.py --server http://127.0.0.1:8188 workflows/api/*.json
  python verify_workflow.py --workflow-copy      # 只做静态检查（不连服务器）
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
import urllib.request
from pathlib import Path

FRONTEND_ONLY = {"MarkdownNote", "Note", "PrimitiveNode", "Reroute", "PreviewAny"}

# 节点类型 -> (/object_info 里的节点名, 输入名)
MODEL_ENUM = {
    "UNETLoader": "unet_name",
    "UnetLoaderGGUF": "unet_name",
    "CLIPLoader": "clip_name",
    "VAELoader": "vae_name",
    "LoraLoaderModelOnly": "lora_name",
    "LoraLoader": "lora_name",
    "LoadImage": "image",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def node_types(wf: dict) -> set[str]:
    types: set[str] = set()
    if all(isinstance(v, dict) and "class_type" in v for v in wf.values()):
        types |= {v["class_type"] for v in wf.values()}
    for n in wf.get("nodes", []):
        types.add(n.get("type", ""))
    for sg in (wf.get("definitions") or {}).get("subgraphs", []):
        for n in sg.get("nodes", []):
            types.add(n.get("type", ""))
    return {t for t in types if t}


def model_refs(wf: dict) -> set[str]:
    refs: set[str] = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
        elif isinstance(o, str) and (o.endswith(".safetensors") or o.endswith(".gguf")):
            refs.add(o)

    walk(wf)
    return refs


def fetch_info(server: str) -> dict:
    with urllib.request.urlopen(server.rstrip("/") + "/object_info", timeout=180) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("workflows", nargs="+", help="工作流 json 文件或 glob")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    args = ap.parse_args()

    files: list[Path] = []
    for pattern in args.workflows:
        files += [Path(p) for p in glob.glob(pattern)]
    if not files:
        sys.exit("没有匹配到工作流文件")

    info = fetch_info(args.server)
    models_available: dict[str, set[str]] = {}
    for node, field in MODEL_ENUM.items():
        try:
            spec = info[node]["input"]["required"][field][0]
            if isinstance(spec, list):
                models_available[node] = set(map(str, spec))
        except (KeyError, TypeError, IndexError):
            pass

    bad = 0
    for f in files:
        wf = load_json(f)
        types = node_types(wf)
        missing_nodes = sorted(t for t in types if t not in info and t not in FRONTEND_ONLY)
        refs = model_refs(wf)
        all_models = set().union(*models_available.values()) if models_available else set()
        missing_models = sorted(r for r in refs if all_models and r not in all_models)

        status = "OK " if not missing_nodes and not missing_models else "BAD"
        if missing_nodes or missing_models:
            bad += 1
        print(f"[{status}] {f}")
        if missing_nodes:
            print("      缺节点:", ", ".join(missing_nodes))
        if missing_models:
            print("      缺模型:", ", ".join(missing_models))
    print(f"\n{len(files) - bad}/{len(files)} 个工作流可以跑")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
