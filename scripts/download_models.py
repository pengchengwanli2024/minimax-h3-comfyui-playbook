#!/usr/bin/env python3
"""多线程分段下载 HuggingFace 上的模型文件（国内默认走 hf-mirror，支持断点续传）。

例子:
  python download_models.py --dest "D:/models/comfyui" \
      --patterns "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors" \
                 "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors" \
                 "vae/minimax_h3_video_vae_int8_convrot.safetensors" \
                 "vae/minimax_h3_audio_vae_fp32.safetensors"

说明:
  - 先 HEAD 探测端点与大小，再按 16MB 分段、多线程 Range 下载
  - 已存在且大小一致的自动跳过；中断后重跑会从 .part 继续
  - 只依赖 requests
"""
from __future__ import annotations

import argparse
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def pick_endpoint(repo: str, rel_path: str, mirrors: list[str]) -> tuple[str, int]:
    for base in mirrors:
        url = f"{base}/{repo}/resolve/main/{rel_path}"
        try:
            r = requests.head(url, allow_redirects=True, timeout=20)
            if r.status_code == 200:
                size = int(r.headers.get("Content-Length") or 0)
                log(f"  端点 {base} 可用，{size/1e9:.2f} GB")
                return url, size
        except Exception as e:  # noqa: BLE001
            log(f"  端点 {base} 失败: {type(e).__name__}")
    return "", 0


def download(repo: str, rel_path: str, dest_root: Path, mirrors: list[str],
             workers: int, chunk_mb: int) -> bool:
    dest = dest_root / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    url, total = pick_endpoint(repo, rel_path, mirrors)
    if not url or total <= 0:
        log(f"FAIL 无法确定 {rel_path} 的大小")
        return False
    if dest.exists() and dest.stat().st_size == total:
        log(f"SKIP {dest.name} 已完整")
        return True

    chunk = chunk_mb * 1024 * 1024
    start = part.stat().st_size if part.exists() else 0
    if start > total:
        part.unlink()
        start = 0
    log(f"开始 {dest.name}: 已有 {start/1e9:.2f} / {total/1e9:.2f} GB")
    with open(part, "r+b" if part.exists() else "wb") as f:
        if start == 0:
            f.truncate(total)

    ranges = [(i, min(i + chunk, total) - 1) for i in range(start, total, chunk)]

    def fetch(rng: tuple[int, int], attempt: int = 0) -> int:
        lo, hi = rng
        try:
            r = requests.get(url, headers={"Range": f"bytes={lo}-{hi}"}, stream=True, timeout=(20, 120))
            r.raise_for_status()
            data = r.content
            if len(data) != hi - lo + 1:
                raise RuntimeError(f"短读 {len(data)} != {hi - lo + 1}")
            with open(part, "r+b") as fh:
                fh.seek(lo)
                fh.write(data)
            return len(data)
        except Exception:  # noqa: BLE001
            if attempt < 3:
                time.sleep(2 + attempt * 3)
                return fetch(rng, attempt + 1)
            raise

    done, t0 = 0, time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch, rg): rg for rg in ranges}
        for fut in as_completed(futs):
            done += fut.result()
            if done % (512 * 1024 * 1024) < chunk:
                log(f"  {dest.name}: {(start+done)/1e9:.2f} GB, {done/max(time.time()-t0, .1)/1e6:.1f} MB/s")

    if part.stat().st_size != total:
        log(f"FAIL 尺寸不符 {part.stat().st_size} != {total}")
        return False
    dest.unlink(missing_ok=True)
    part.rename(dest)
    log(f"DONE {dest.name} ({total/1e9:.2f} GB, {time.time()-t0:.0f}s)")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="Comfy-Org/MiniMax-H3")
    ap.add_argument("--patterns", nargs="+", required=True,
                    help="仓库内相对路径，如 diffusion_models/xxx.safetensors")
    ap.add_argument("--dest", required=True, help="本地模型根目录，例如 D:/models/comfyui")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--chunk-mb", type=int, default=16)
    ap.add_argument("--mirror", default="https://hf-mirror.com", help="国内镜像，留空则用官方")
    ap.add_argument("--fallback-official", action="store_true", help="镜像失败后回退 huggingface.co")
    args = ap.parse_args()

    mirrors = [m for m in (args.mirror, "https://huggingface.co" if args.fallback_official else "") if m]
    if not mirrors:
        mirrors = ["https://huggingface.co"]
    dest_root = Path(args.dest)
    ok = True
    for rel in args.patterns:
        ok = download(args.repo, rel, dest_root, mirrors, args.workers, args.chunk_mb) and ok
    print("全部完成" if ok else "有失败项", flush=True)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
