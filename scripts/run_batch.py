#!/usr/bin/env python3
"""MiniMax H3 批量出片脚本（ComfyUI API）。

用法:
  python run_batch.py prompts/examples.json --outdir ./outputs
  python run_batch.py jobs.json --preset fasth3_vsa --server http://127.0.0.1:8188
  python run_batch.py jobs.json --dry-run --outdir ./outputs   # 只生成 API JSON 供检查

任务 JSON 是数组，每条:
  {"name": "...", "prompt": "...", "length": 243, "width": 1152, "height": 640,
   "steps": 4, "seed": 42}                       # 文生视频
  {..., "image": "first_frame.png"}              # 图生视频（可选，用 i2v_turbo8 预设）

预设（--preset）:
  turbo8_sla   最快的文生视频组合（推荐，4 步 + 原生 SLA 稀疏）
  fasth3_vsa   FastH3 4 步 VSA 蒸馏权重（只支持文生视频）
  i2v_turbo8   图生视频（官方 int8 基座 + turbo8 LoRA，8 步）
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PRESETS = {
    "turbo8_sla": {
        "unet": "minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors",
        "te": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
        "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
        "attention": ("sla", 10.0, 0.0, 1.0, 8192),
        "steps": 4, "shift": (12.0, 3.0), "lora": None, "i2v": False,
    },
    "fasth3_vsa": {
        "unet": "minimax_h3_fastvideo_vsa_datafree_1300step_4step_int8_convrot.safetensors",
        "te": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
        "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
        "attention": ("vsa", 10.0, 0.2, 1.0, 12288),
        "steps": 4, "shift": (12.0, 3.0), "lora": None, "i2v": False,
    },
    "i2v_turbo8": {
        "unet": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
        "te": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
        "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
        "attention": None,
        "steps": 8, "shift": (12.0, 3.0),
        "lora": "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", "i2v": True,
    },
    # 官方基座、不加加速 LoRA：质量基线，速度约为 turbo8 的 2.5 倍耗时
    "base20": {
        "unet": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
        "te": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
        "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
        "attention": None,
        "steps": 20, "shift": (12.0, 3.0), "lora": None, "i2v": False,
    },
}


def build_prompt(preset: dict, job: dict) -> dict:
    w, h = job.get("width", 1152), job.get("height", 640)
    steps = job.get("steps", preset["steps"])
    wf: dict[str, dict] = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": preset["unet"], "weight_dtype": "default"}},
        "5": {"class_type": "CLIPLoader", "inputs": {"clip_name": preset["te"], "type": "minimax", "device": "default"}},
        "6": {"class_type": "VAELoader", "inputs": {"vae_name": preset["vae"]}},
        "7": {"class_type": "VAELoader", "inputs": {"vae_name": preset["audio_vae"]}},
        "9": {"class_type": "RandomNoise", "inputs": {"noise_seed": job.get("seed", 42)}},
        "10": {"class_type": "BasicScheduler", "inputs": {"model": ["4", 0], "scheduler": "simple",
                                                         "steps": steps, "denoise": 1.0}},
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "12": {"class_type": "BasicGuider", "inputs": {"model": ["4", 0], "conditioning": ["8", 0]}},
        "13": {"class_type": "SamplerCustomAdvanced", "inputs": {
            "noise": ["9", 0], "guider": ["12", 0], "sampler": ["11", 0],
            "sigmas": ["10", 0], "latent_image": ["8", 1]}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["6", 0]}},
        "15": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["13", 0], "vae": ["7", 0]}},
        "16": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "audio": ["15", 0],
                                                       "fps": 24, "bit_depth": 8}},
        "17": {"class_type": "SaveVideo", "inputs": {"video": ["16", 0], "format": "auto",
                                                     "codec": "auto", "filename_prefix": f"video/{job['name']}"}},
    }
    # 模型链：UNET -> (Lora) -> (注意力后端) -> (稀疏注意力) -> SigmaShift
    src = "1"
    if preset["lora"]:
        wf["18"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": [src, 0], "lora_name": preset["lora"], "strength_model": 1.0}}
        src = "18"
    wf["2"] = {"class_type": "ModelAttentionBackend", "inputs": {"model": [src, 0],
                                                                 "attention": "comfy kitchen attention"}}
    src = "2"
    if preset["attention"]:
        method, keep, start, end, min_tokens = preset["attention"]
        wf["3"] = {"class_type": "BlockSparseAttention", "inputs": {
            "model": [src, 0], "selection": method, f"selection.keep_percent": keep,
            "start_percent": start, "end_percent": end, "dense_blocks": "",
            "min_tokens": min_tokens, "extra_tokens": 256,
            "sink_conditioning": "exact_kv_and_rows", "verbose": False}}
        src = "3"
    wf["4"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {
        "model": [src, 0], "shift_video": preset["shift"][0], "shift_audio": preset["shift"][1]}}

    # 条件节点：T2V 用 MiniMaxH3ImageToVideo（不接图）；I2V 接 first_frame
    cond_inputs = {"prompt": job["prompt"], "width": w, "height": h, "length": job["length"],
                   "clip": ["5", 0], "vae": ["6", 0]}
    if preset["i2v"]:
        if "image" not in job:
            raise SystemExit(f"任务 {job['name']} 用了 i2v 预设但没有 image 字段")
        wf["19"] = {"class_type": "LoadImage", "inputs": {"image": job["image"]}}
        cond_inputs["first_frame"] = ["19", 0]
    wf["8"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": cond_inputs}
    return wf


def post(server: str, path: str, payload: dict) -> dict:
    req = urllib.request.Request(server + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get(server: str, path: str) -> dict:
    with urllib.request.urlopen(server + path, timeout=60) as r:
        return json.load(r)


def run_one(server: str, preset: dict, job: dict, outdir: Path, poll: int = 10) -> tuple | None:
    print(f"\n=== {job['name']}: {job.get('width', 1152)}x{job.get('height', 640)} "
          f"x {job['length']} 帧 ===", flush=True)
    wf = build_prompt(preset, job)
    resp = post(server, "/prompt", {"prompt": wf, "client_id": f"batch-{job['name']}"})
    pid = resp["prompt_id"]
    if resp.get("node_errors"):
        print("提交校验失败:", json.dumps(resp["node_errors"], ensure_ascii=False)[:800], flush=True)
        return None
    t0 = time.time()
    while True:
        time.sleep(poll)
        hist = get(server, f"/history/{pid}")
        if pid not in hist:
            if time.time() - t0 > 2400:
                print("超时（40 分钟），放弃", flush=True)
                return None
            continue
        e = hist[pid]
        st = e["status"]
        dur = (st["messages"][-1][1]["timestamp"] - st["messages"][0][1]["timestamp"]) / 1000
        if st["status_str"] != "success":
            print(f"失败: {st['status_str']}", json.dumps(st, ensure_ascii=False)[:600], flush=True)
            return None
        for node in e.get("outputs", {}).values():
            for item in node.get("images", []):
                query = urllib.parse.urlencode({
                    "filename": item["filename"],
                    "subfolder": item.get("subfolder", ""),
                    "type": item.get("type", "output"),
                })
                outdir.mkdir(parents=True, exist_ok=True)
                dst = outdir / f"{job['name']}.mp4"
                with urllib.request.urlopen(f"{server}/view?{query}", timeout=300) as r, open(dst, "wb") as f:
                    shutil.copyfileobj(r, f)
                print(f"完成: {dur:.1f}s -> {dst}", flush=True)
                return dur, str(dst)
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--outdir", default="./outputs")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--preset", default="turbo8_sla", choices=sorted(PRESETS))
    ap.add_argument("--poll", type=int, default=10)
    ap.add_argument("--dry-run", action="store_true", help="只输出 API JSON，不提交")
    args = ap.parse_args()

    jobs = json.loads(Path(args.jobs).read_text(encoding="utf-8"))
    preset = PRESETS[args.preset]
    outdir = Path(args.outdir)
    results = []
    for job in jobs:
        wf = build_prompt(preset, job)
        if args.dry_run:
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / f"{job['name']}.api.json").write_text(json.dumps(wf, ensure_ascii=False, indent=1), encoding="utf-8")
            print("dry-run:", job["name"])
            continue
        results.append({"name": job["name"], "result": run_one(args.server, preset, job, outdir, args.poll)})

    if not args.dry_run:
        print("\n=== 汇总 ===")
        for r in results:
            print(f"{r['name']}: {r['result']}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.URLError as e:
        print(f"连不上 ComfyUI（{e}）；确认服务已启动，或改 --server", file=sys.stderr)
        sys.exit(1)
