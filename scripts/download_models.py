#!/usr/bin/env python3
"""多线程分段下载 MiniMax H3 相关权重（国内默认走 hf-mirror，支持断点续传）。

推荐用清单模式：
  # 看有哪些模型组合
  python download_models.py --list-sets

  # 下载「最快的文生视频组合」
  python download_models.py --set turbo8_sla --dest "D:/models/comfyui"

  # 只检查本地是否齐了（按 models.json 里的大小 ±2% 校验）
  python download_models.py --check --set turbo8_sla --dest "D:/models/comfyui"

也可以临时指定文件：
  python download_models.py --repo Comfy-Org/MiniMax-H3 \
      --patterns "vae/minimax_h3_video_vae_int8_convrot.safetensors" --dest "D:/models/comfyui"

说明：
  - 先 HEAD 探测端点与大小，再按 16MB 分段、多线程 Range 下载
  - 已存在且大小一致的自动跳过；中断后重跑会从 .part 继续
  - 只依赖 requests
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

_print_lock = threading.Lock()
HERE = Path(__file__).resolve().parent.parent


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("sets", {})


def human(n: float) -> str:
    return f"{n / 1e9:.2f} GB"


def pick_endpoint(repo: str, rel_path: str, mirrors: list[str]) -> tuple[str, int]:
    for base in mirrors:
        url = f"{base}/{repo}/resolve/main/{rel_path}"
        try:
            r = requests.head(url, allow_redirects=True, timeout=20)
            if r.status_code == 200:
                size = int(r.headers.get("Content-Length") or 0)
                log(f"  端点 {base} 可用，{human(size)}")
                return url, size
        except Exception as e:  # noqa: BLE001
            log(f"  端点 {base} 失败: {type(e).__name__}")
    return "", 0


def download(repo: str, rel_path: str, dest: Path, mirrors: list[str],
             workers: int, chunk_mb: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")

    url, total = pick_endpoint(repo, rel_path, mirrors)
    if not url or total <= 0:
        log(f"FAIL 无法确定 {repo}/{rel_path} 的大小")
        return False
    if dest.exists() and dest.stat().st_size == total:
        log(f"SKIP {dest.name} 已完整")
        return True

    chunk = chunk_mb * 1024 * 1024
    start = part.stat().st_size if part.exists() else 0
    if start > total:
        part.unlink()
        start = 0
    log(f"开始 {dest.name}: 已有 {human(start)} / {human(total)}")
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
                log(f"  {dest.name}: {human(start + done)}, "
                    f"{done / max(time.time() - t0, 0.1) / 1e6:.1f} MB/s")

    if part.stat().st_size != total:
        log(f"FAIL 尺寸不符 {part.stat().st_size} != {total}")
        return False
    dest.unlink(missing_ok=True)
    part.rename(dest)
    log(f"DONE {dest.name} ({human(total)}, {time.time() - t0:.0f}s)")
    return True


def check(entries: list[dict], dest_root: Path) -> bool:
    ok = True
    print(f"{'状态':4} {'大小':>10}  文件")
    for e in entries:
        dest = dest_root / e["dest"]
        expect = e.get("size_gb")
        if not dest.exists():
            ok = False
            print(f"{'缺失':4} {expect if expect else '-':>10}  {e['dest']}")
            continue
        size = dest.stat().st_size
        if expect:
            lo, hi = expect * 1e9 * 0.98, expect * 1e9 * 1.02
            if not (lo <= size <= hi):
                ok = False
                print(f"{'大小不符':4} {human(size):>10}  {e['dest']} (期望 {expect} GB)")
                continue
        print(f"{'OK':4} {human(size):>10}  {e['dest']}")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(HERE / "models.json"))
    ap.add_argument("--list-sets", action="store_true", help="列出 models.json 里的组合")
    ap.add_argument("--set", dest="which", help="按 models.json 里的组合下载/检查")
    ap.add_argument("--check", action="store_true", help="只检查本地文件，不下载")
    ap.add_argument("--dest", help="本地模型根目录，例如 D:/models/comfyui")
    ap.add_argument("--repo", default="Comfy-Org/MiniMax-H3", help="临时模式下使用的 HF 仓库")
    ap.add_argument("--patterns", nargs="+", help="临时模式：仓库内相对路径列表")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--chunk-mb", type=int, default=16)
    ap.add_argument("--mirror", default="https://hf-mirror.com", help="国内镜像；留空则用官方")
    ap.add_argument("--fallback-official", action="store_true", help="镜像失败后回退 huggingface.co")
    args = ap.parse_args()

    sets = load_manifest(Path(args.manifest))
    if args.list_sets:
        for name, spec in sets.items():
            total = sum(f.get("size_gb", 0) for f in spec["files"])
            print(f"{name:14} {total:5.1f} GB  {spec.get('description', '')}")
        return

    if not args.dest:
        ap.error("需要 --dest")
    dest_root = Path(args.dest)

    if args.which:
        if args.which not in sets:
            ap.error(f"没有组合 {args.which}；可选: {', '.join(sets)}")
        entries = sets[args.which]["files"]
        print(f"组合 {args.which}: {sets[args.which].get('description', '')}")
    elif args.patterns:
        entries = [{"repo": args.repo, "path": p, "dest": p} for p in args.patterns]
    else:
        ap.error("需要 --set 或 --patterns")

    if args.check:
        ok = check(entries, dest_root)
        raise SystemExit(0 if ok else 1)

    mirrors = [m for m in (args.mirror, "https://huggingface.co" if args.fallback_official else "") if m]
    if not mirrors:
        mirrors = ["https://huggingface.co"]

    ok = True
    for e in entries:
        ok = download(e["repo"], e["path"], dest_root / e["dest"], mirrors,
                      args.workers, args.chunk_mb) and ok
    print("全部完成" if ok else "有失败项", flush=True)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
