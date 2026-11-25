#!/usr/bin/env python3
"""从 mp4 里按时间点抽帧，用于快速检查生成结果。

用法:
  python extract_frames.py video.mp4 out_prefix 0 3 6 9
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import av
except ImportError:
    sys.exit("需要 PyAV： pip install av")


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    path, prefix = Path(sys.argv[1]), sys.argv[2]
    times = [float(x) for x in sys.argv[3:]] or [0.0, 1.0, 2.0]

    with av.open(str(path)) as c:
        print(f"时长: {float(c.duration / av.time_base):.3f}s")
        for s in c.streams:
            if s.type == "video":
                print(f"视频: {s.codec_context.name} {s.width}x{s.height} "
                      f"fps={float(s.average_rate):.3f} frames={s.frames}")
            elif s.type == "audio":
                print(f"音频: {s.codec_context.name} {s.codec_context.sample_rate}Hz "
                      f"ch={s.codec_context.layout.name}")

        wanted = sorted(set(times))
        saved: set[float] = set()
        for frame in c.decode(video=0):
            t = float(frame.pts * frame.time_base) if frame.pts is not None else 0.0
            for w in wanted:
                if w not in saved and t + 1e-6 >= w:
                    out = f"{prefix}_{w:.1f}s.png"
                    frame.to_image().save(out)
                    print("保存:", out)
                    saved.add(w)
            if len(saved) == len(wanted):
                break


if __name__ == "__main__":
    main()
