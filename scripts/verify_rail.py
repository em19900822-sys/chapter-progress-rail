#!/usr/bin/env python3
"""合成后验证章节导航条成片。

1) ffprobe：分辨率、音频流、时长（给 --source 时与原片逐项比对，时长差 ≤0.1s）。
2) 抽帧：每个换格点前后各 1s、每栏中点、片尾前 0.5s；只裁导航条区域（y 范围按 --bottom/--height
   或 --preset 计算，和渲染时一致），竖拼成 check_sheet.png，每条上方标注 t 和应有状态。
3) 自动量填充：在栏顶部无字无竖条的几行像素里，按"偏黄且够亮"判断已填充像素，
   估算每栏填充比例，与 chapters.json 推算的应有比例比对（容差 --tol，默认 0.08）。
   这是启发式（背景偏黄/偏亮时可能误判），最终仍要人眼看 check_sheet。
用法：
  python3 verify_rail.py out.mp4 chapters.json --preset xingjie --source 原片.mp4 --outdir check/
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_chapter_rail_v2 import load_preset, load_spec, parse_color, probe_video  # noqa: E402


def grab(video: Path, t: float) -> Image.Image:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "pipe:1"], check=True, capture_output=True).stdout
    return Image.open(io.BytesIO(raw)).convert("RGB")


def expected(chapters, t):
    out = []
    for c in chapters:
        out.append(0.0 if t <= c["start"] else 1.0 if t >= c["end"] else (t - c["start"]) / (c["end"] - c["start"]))
    return out


def measure(crop: Image.Image, n: int, rail_h: int, fill_rgba, margin_top: int) -> list[float]:
    w = crop.width
    fr, fg, fb, fa = fill_rgba
    a = fa / 255
    yellow_need = 0.5 * a * ((fr + fg) / 2 - fb)
    lum_need = 0.75 * a * (0.299 * fr + 0.587 * fg + 0.114 * fb)
    rows = range(margin_top + max(1, int(rail_h * 0.03)), margin_top + max(3, int(rail_h * 0.085)))
    px = crop.load()
    res = []
    for i in range(n):
        left, right = round(i * w / n), round((i + 1) * w / n)
        l2, r2 = left + 14, right - 14  # skip divider area
        filled_cols = 0
        for x in range(l2, r2):
            votes = 0
            for y in rows:
                r, g, b = px[x, y]
                if (r + g) / 2 - b >= yellow_need and 0.299 * r + 0.587 * g + 0.114 * b >= lum_need:
                    votes += 1
            if votes * 2 > len(rows):
                filled_cols += 1
        # convert inner-span count back to whole-cell fraction
        span = r2 - l2
        frac_inner = filled_cols / span if span else 0
        cell_w = right - left
        frac = (frac_inner * span + (14 if frac_inner > 0.02 else 0) + (14 if frac_inner > 0.98 else 0)) / cell_w
        res.append(round(min(1.0, frac), 3))
    return res


def ffprobe_summary(path: Path) -> dict:
    p = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                                  check=True, capture_output=True, text=True).stdout)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    return {"width": v["width"], "height": v["height"], "fps": v.get("avg_frame_rate"),
            "audio": any(s["codec_type"] == "audio" for s in p["streams"]),
            "duration": round(float(p["format"]["duration"]), 3)}


def main() -> int:
    ap = argparse.ArgumentParser(description="验证章节导航条成片")
    ap.add_argument("video", type=Path)
    ap.add_argument("chapters", type=Path)
    ap.add_argument("--preset")
    ap.add_argument("--height", type=int)
    ap.add_argument("--bottom", type=int)
    ap.add_argument("--source", type=Path, help="原片，用于比对分辨率/时长/音频")
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--tol", type=float, default=0.08)
    ap.add_argument("--margin", type=int, default=12, help="裁切时导航条上下各多留的像素")
    args = ap.parse_args()

    preset = load_preset(args.preset)
    info = probe_video(args.video)
    chapters, cstyle = load_spec(args.chapters, info.duration)
    style = {**(preset.get("style") or {}), **cstyle}
    layout = preset.get("layout") or {}
    ref_h = float(layout.get("reference_height", 1920))
    rail_h = args.height or (round(layout["height"] * info.height / ref_h) if "height" in layout else max(48, round(92 * info.height / 1920)))
    bottom = args.bottom if args.bottom is not None else (round(layout["bottom"] * info.height / ref_h) if "bottom" in layout else round(320 * info.height / 1920))
    top = info.height - bottom - rail_h
    fill = parse_color(style.get("fill_color", "#F3E9A6D9"))

    report: dict = {"video": str(args.video), "rail_y": [top, top + rail_h], "probe": ffprobe_summary(args.video), "problems": []}
    pr = report["probe"]
    if not pr["audio"]:
        report["problems"].append("成片没有音频流")
    if args.source:
        src = ffprobe_summary(args.source)
        report["source_probe"] = src
        if (src["width"], src["height"]) != (pr["width"], pr["height"]):
            report["problems"].append("分辨率与原片不一致")
        if abs(src["duration"] - pr["duration"]) > 0.1:
            report["problems"].append(f"时长与原片差 {abs(src['duration'] - pr['duration']):.3f}s")
        if src["audio"] and not pr["audio"]:
            report["problems"].append("原片有音频，成片丢了")

    times: list[tuple[float, str]] = []
    for i, c in enumerate(chapters):
        if i:
            times.append((max(0.0, c["start"] - 1.0), f"换格前 {c['start']:.2f}s"))
            times.append((c["start"] + 1.0, f"换格后 {c['start']:.2f}s"))
        times.append(((c["start"] + c["end"]) / 2, f"第{i + 1}栏中点"))
    times.append((max(0.0, info.duration - 0.5), "片尾"))
    times.sort()

    m = args.margin
    y0, y1 = max(0, top - m), min(info.height, top + rail_h + m)
    try:
        font = ImageFont.truetype(style.get("font") or "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 22)
    except OSError:
        font = ImageFont.load_default()
    strips, samples = [], []
    for t, why in times:
        crop = grab(args.video, t).crop((0, y0, info.width, y1))
        exp = expected(chapters, t)
        got = measure(crop, len(chapters), rail_h, fill, top - y0)
        bad = [i + 1 for i, (e, g) in enumerate(zip(exp, got)) if abs(e - g) > args.tol]
        samples.append({"t": round(t, 2), "why": why, "expected": [round(e, 3) for e in exp], "measured": got, "mismatch_cells": bad})
        label = Image.new("RGB", (info.width, 30), "white")
        ImageDraw.Draw(label).text((6, 2), f"t={t:.2f}s  {why}  应有={[round(e, 2) for e in exp]}  {'OK' if not bad else '偏差栏' + str(bad)}",
                                   fill=(200, 0, 0) if bad else (0, 120, 0), font=font)
        strips += [label, crop]
    report["samples"] = samples
    mism = [s for s in samples if s["mismatch_cells"]]
    if mism:
        report["problems"].append(f"{len(mism)} 个抽样时刻自动填充测量与预期不符（启发式，请看 check_sheet 人工确认）")

    args.outdir.mkdir(parents=True, exist_ok=True)
    sheet = Image.new("RGB", (info.width, sum(s.height for s in strips)), "white")
    y = 0
    for s in strips:
        sheet.paste(s, (0, y))
        y += s.height
    sheet.save(args.outdir / "check_sheet.png")
    report["check_sheet"] = str(args.outdir / "check_sheet.png")
    (args.outdir / "verify_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"problems": report["problems"], "probe": pr, "rail_y": report["rail_y"], "samples": len(samples),
                      "check_sheet": report["check_sheet"]}, ensure_ascii=False, indent=1))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
