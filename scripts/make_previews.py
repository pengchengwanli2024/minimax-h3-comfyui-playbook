"""为仓库生成预览：视频四宫格拼图 + 小体积 mp4 预览。

用法:
  python make_previews.py <源视频目录> <输出目录>
"""
import sys
from pathlib import Path

import av
from PIL import Image, ImageDraw

SAMPLES = [
    ("sla_long_nightmarket_15s.mp4", "nightmarket", [1.5, 5.0, 9.0, 13.0]),
    ("h3_sla_subway_10s.mp4", "subway", [1.0, 3.5, 6.5, 9.0]),
    ("sla_seaside_sunset_10s.mp4", "seaside", [1.0, 4.0, 6.5, 9.0]),
    ("sla_bookstore_rain_10s.mp4", "bookstore", [1.0, 4.0, 6.5, 9.0]),
    ("h3_pov_10s_1152x640.mp4", "pov", [0.5, 3.0, 6.0, 9.0]),
    ("h3_10s_1152x640.mp4", "rainstreet", [1.0, 4.0, 7.0, 9.5]),
]
SMALL = ["sla_long_nightmarket_15s.mp4", "h3_sla_subway_10s.mp4", "sla_seaside_sunset_10s.mp4"]


def grab(path, times):
    frames = []
    with av.open(str(path)) as c:
        for frame in c.decode(video=0):
            t = float(frame.pts * frame.time_base)
            while times and t >= times[0]:
                frames.append(frame.to_image())
                times.pop(0)
            if not times:
                break
    return frames


def sheet(frames, out, cols=2):
    w, h = frames[0].size
    tw, th = 720, int(720 * h / w)
    rows = (len(frames) + cols - 1) // cols
    canvas = Image.new("RGB", (tw * cols, th * rows), "black")
    for i, f in enumerate(frames):
        canvas.paste(f.resize((tw, th), Image.LANCZOS), ((i % cols) * tw, (i // cols) * th))
    canvas.save(out, quality=85, optimize=True)
    print("拼图:", out, canvas.size)


def small_video(src, dst, width=640):
    with av.open(str(src)) as inp:
        vs = inp.streams.video[0]
        h = int(width * vs.codec_context.height / vs.codec_context.width) // 2 * 2
        out = av.open(str(dst), "w")
        st = out.add_stream("libx264", rate=vs.average_rate)
        st.width, st.height, st.pix_fmt = width, h, "yuv420p"
        st.options = {"crf": "30", "preset": "veryfast"}
        for frame in inp.decode(video=0):
            for pkt in st.encode(frame.reformat(width=width, height=h)):
                out.mux(pkt)
        for pkt in st.encode():
            out.mux(pkt)
        out.close()
    print("预览:", dst, f"{dst.stat().st_size/1e6:.2f} MB")


def main():
    src_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, slug, times in SAMPLES:
        p = src_dir / name
        if not p.exists():
            print("跳过（不存在）:", name)
            continue
        sheet(grab(p, list(times)), out_dir / f"{slug}.jpg")
    for name in SMALL:
        p = src_dir / name
        if p.exists():
            small_video(p, out_dir / f"{name[:-4]}_preview.mp4")


if __name__ == "__main__":
    main()
