#!/usr/bin/env python3
"""检查工作流能否在当前 ComfyUI 上跑：节点是否注册、模型文件是否存在。

用法:
  python verify_workflow.py --server http://127.0.0.1:8188 "workflows/api/*.json"   # 连服务器查节点/模型
  python verify_workflow.py --static "workflows/api/*.json" "workflows/gui/*.json"  # 离线结构检查

--static 不连 ComfyUI：校验 JSON 能解析、API 格式的节点引用是否指向存在的节点、
GUI 格式的 links 是否指向存在的节点，适合放进 CI 或提交前跑一遍。
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


def is_api_workflow(wf: dict) -> bool:
    return bool(wf) and all(isinstance(v, dict) and "class_type" in v for v in wf.values())


def _looks_like_link(value) -> bool:
    return (isinstance(value, list) and len(value) == 2
            and isinstance(value[0], str) and isinstance(value[1], int))


def api_problems(wf: dict) -> list[str]:
    """API 格式：节点输入里的 [node_id, slot] 引用必须指向存在的节点。"""
    problems: list[str] = []
    for node_id, node in wf.items():
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            problems.append(f"节点 {node_id} 的 inputs 不是对象")
            continue
        for name, value in inputs.items():
            if _looks_like_link(value) and value[0] not in wf:
                problems.append(f"节点 {node_id} 的输入 {name} 引用了不存在的节点 {value[0]}")
    return problems


SUBGRAPH_ENDS = {-10, -20}  # GUI 格式里子图的输入/输出伪节点 id
UUID_RE = __import__("re").compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _node_links_exist(nodes: list, link_ids: set, where: str) -> list[str]:
    problems: list[str] = []
    for node in nodes:
        node_id = node.get("id")
        for kind in ("inputs", "outputs"):
            for slot in node.get(kind) or []:
                for link_id in (slot.get("link"), *(slot.get("links") or [])):
                    if link_id is not None and link_id not in link_ids:
                        problems.append(f"{where}节点 {node_id} 引用了不存在的连线 {link_id}")
    return problems


def gui_problems(wf: dict) -> list[str]:
    """GUI 格式：nodes/links 与子图内部的引用都要自洽。"""
    problems: list[str] = []
    nodes = wf.get("nodes") or []
    if not nodes:
        return ["GUI 工作流没有 nodes"]
    ids: set = set()
    for node in nodes:
        node_id = node.get("id")
        if node_id in ids:
            problems.append(f"节点 id 重复: {node_id}")
        ids.add(node_id)
        if not node.get("type"):
            problems.append(f"节点 {node_id} 缺 type")
    link_ids: set = set()
    for link in wf.get("links") or []:
        if not isinstance(link, list) or len(link) < 5:
            problems.append(f"links 条目格式异常: {link!r}")
            continue
        link_id, src, _src_slot, dst, _dst_slot = link[:5]
        link_ids.add(link_id)
        if src not in ids:
            problems.append(f"links 条目 {link_id} 的起点节点 {src} 不存在")
        if dst not in ids:
            problems.append(f"links 条目 {link_id} 的终点节点 {dst} 不存在")
    problems += _node_links_exist(nodes, link_ids, "")

    subgraphs = (wf.get("definitions") or {}).get("subgraphs") or []
    subgraph_ids = {sg.get("id") for sg in subgraphs}
    for node in nodes:
        node_type = str(node.get("type") or "")
        if UUID_RE.match(node_type) and node_type not in subgraph_ids:
            problems.append(f"节点 {node.get('id')} 引用了不存在的子图 {node_type}")

    for sg in subgraphs:
        name = sg.get("name") or sg.get("id")
        sg_nodes = sg.get("nodes") or []
        sg_ids = {n.get("id") for n in sg_nodes}
        if not sg_nodes:
            problems.append(f"子图 {name} 没有 nodes")
            continue
        for node in sg_nodes:
            if not node.get("type"):
                problems.append(f"子图 {name} 的节点 {node.get('id')} 缺 type")
        sg_links = sg.get("links") or []
        sg_link_ids = set()
        for link in sg_links:
            if not isinstance(link, dict):
                problems.append(f"子图 {name} 的连线格式异常: {link!r}")
                continue
            sg_link_ids.add(link.get("id"))
            for key in ("origin_id", "target_id"):
                nid = link.get(key)
                if nid in SUBGRAPH_ENDS:
                    continue
                if nid not in sg_ids:
                    problems.append(f"子图 {name} 的连线 {link.get('id')} {key}={nid} 不存在")
        problems += _node_links_exist(sg_nodes, sg_link_ids, f"子图 {name} 的")
    return problems


def static_problems(wf: dict) -> list[str]:
    """不连服务器的结构检查。"""
    if is_api_workflow(wf):
        return api_problems(wf)
    if isinstance(wf, dict) and "nodes" in wf:
        return gui_problems(wf)
    return ["既不是 API 工作流（节点表）也不是 GUI 工作流（nodes/links）"]


def main() -> None:
    ap = argparse.ArgumentParser(description="校验 ComfyUI 工作流（可离线，也可连服务器比对节点/模型）")
    ap.add_argument("workflows", nargs="*",
                    help="工作流 json 文件或 glob；缺省检查 workflows/api/*.json 与 workflows/gui/*.json")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--static", "--workflow-copy", dest="static", action="store_true",
                    help="只做离线结构检查，不连接 ComfyUI")
    args = ap.parse_args()

    patterns = args.workflows or ["workflows/api/*.json", "workflows/gui/*.json"]
    files: list[Path] = []
    for pattern in patterns:
        files += [Path(p) for p in glob.glob(pattern, recursive=True)]
    if not files:
        sys.exit("没有匹配到工作流文件")

    if args.static:
        bad = 0
        for f in files:
            try:
                wf = load_json(f)
            except json.JSONDecodeError as exc:
                print(f"[BAD] {f}")
                print(f"      JSON 解析失败: {exc}")
                bad += 1
                continue
            problems = static_problems(wf)
            status = "OK " if not problems else "BAD"
            if problems:
                bad += 1
            print(f"[{status}] {f}")
            for problem in problems[:10]:
                print("      " + problem)
        print(f"\n{len(files) - bad}/{len(files)} 个工作流结构检查通过")
        raise SystemExit(1 if bad else 0)

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
