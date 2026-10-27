#!/usr/bin/env python3
"""章节进度导航条 v2 渲染器（星姐风格引擎）。

与 render_chapter_rail.py 的区别：所有栏统一字号（按最长标签定）、可横向压窄文字（text_scale_x）、
粗描边+投影、粗分隔竖条带深色边与左右端条、超采样抗锯齿。支持 --preset 读取 assets/presets/<名>.json，
预设提供 style 与默认栏高/底距；chapters.json 里的 style 字段逐项覆盖预设。
"""
from __future__ import annotations

import argparse
import io
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    fps: float
    duration: float
    has_audio: bool


def probe_video(path: Path) -> VideoInfo:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    payload = json.loads(result.stdout)
    video = next((s for s in payload["streams"] if s.get("codec_type") == "video"), None)
    if not video:
        raise ValueError("输入文件没有视频流")
    rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "30/1"
    num, den = rate.split("/")
    duration = float(video.get("duration") or payload.get("format", {}).get("duration") or 0)
    rotation = 0
    for side_data in video.get("side_data_list", []):
        if side_data.get("side_data_type") == "Display Matrix":
            rotation = int(round(float(side_data.get("rotation", 0)))) % 360
            break
    display_width, display_height = int(video["width"]), int(video["height"])
    if rotation in (90, 270):
        display_width, display_height = display_height, display_width
    return VideoInfo(
        width=display_width, height=display_height, fps=float(num) / float(den),
        duration=duration, has_audio=any(s.get("codec_type") == "audio" for s in payload["streams"]),
    )


def parse_color(value: str, default_alpha: int = 255) -> tuple[int, int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) == 6:
        raw += f"{default_alpha:02x}"
    if len(raw) != 8:
        raise ValueError(f"颜色格式无效: {value}")
    return tuple(int(raw[i:i + 2], 16) for i in range(0, 8, 2))  # type: ignore[return-value]


_FONT_WARNED: set[str] = set()
BOLD_FALLBACKS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
]


def choose_font(custom: str | None, size: int) -> ImageFont.FreeTypeFont:
    """style.font first; if it is missing, fall back to a CJK Bold font and warn once (stderr)."""
    if custom and Path(custom).exists():
        return ImageFont.truetype(custom, size=size)
    for candidate in BOLD_FALLBACKS:
        if Path(candidate).exists():
            if custom and custom not in _FONT_WARNED:
                _FONT_WARNED.add(custom)
                print(f"WARNING: 字体 {custom} 不存在，已回退到 {candidate}（粗细会比 Black 弱，交付前请补装字体或告知用户）", file=sys.stderr)
            return ImageFont.truetype(candidate, size=size)
    raise FileNotFoundError("未找到中文字体，请在 style.font 中指定字体文件")


def load_spec(path: Path, duration: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    source = payload.get("chapters")
    if not isinstance(source, list) or not source:
        raise ValueError("chapters.json 必须包含非空 chapters 数组")
    chapters: list[dict[str, Any]] = []
    for index, item in enumerate(source):
        if not isinstance(item, dict) or not str(item.get("label", "")).strip():
            raise ValueError(f"第 {index + 1} 栏缺少 label")
        start = float(item.get("start", item.get("startSeconds", 0)))
        end_value = item.get("end", item.get("endSeconds"))
        if end_value is None:
            following = source[index + 1] if index + 1 < len(source) else None
            end_value = following.get("start", following.get("startSeconds")) if following else duration
        chapters.append({"label": str(item["label"]).strip(), "start": start, "end": float(end_value)})
    for index, chapter in enumerate(chapters):
        if chapter["start"] < 0 or chapter["end"] <= chapter["start"]:
            raise ValueError(f"栏目时间无效: {chapter}")
        if index and chapter["start"] < chapters[index - 1]["end"] - 0.001:
            raise ValueError("栏目时间不能重叠")
    if chapters[-1]["end"] > duration + 0.25:
        raise ValueError("最后一栏结束时间超过视频时长")
    return chapters, payload.get("style", {}) or {}


def fit_font(draw: ImageDraw.ImageDraw, label: str, font_path: str | None, max_width: int, target: int) -> ImageFont.FreeTypeFont:
    for size in range(target, max(15, target // 2), -2):
        font = choose_font(font_path, size)
        box = draw.textbbox((0, 0), label, font=font, stroke_width=max(1, size // 22))
        if box[2] - box[0] <= max_width:
            return font
    return choose_font(font_path, max(16, target // 2))


_FONT_CACHE: dict[tuple, ImageFont.FreeTypeFont] = {}
_STATIC_CACHE: dict[tuple, Any] = {}


def uniform_font(draw, labels, font_path, max_width, max_height, target, stroke_ratio):
    """v2: one font size for every cell, sized so the longest label fits (no per-cell shrinking)."""
    key = (tuple(labels), font_path, max_width, max_height, target, stroke_ratio)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    chosen = None
    for size in range(target, 14, -1):
        font = choose_font(font_path, size)
        stroke = max(1, round(size * stroke_ratio))
        ok = True
        for label in labels:
            box = draw.textbbox((0, 0), label, font=font, stroke_width=stroke)
            if box[2] - box[0] > max_width or box[3] - box[1] > max_height:
                ok = False
                break
        if ok:
            chosen = font
            break
    _FONT_CACHE[key] = chosen or choose_font(font_path, 16)
    return _FONT_CACHE[key]


def _text_layer(width, height, chapters, style, edges):
    """Static layer: shadow + outlined labels + thick outlined dividers (identical every frame)."""
    key = (width, height, json.dumps(chapters, ensure_ascii=False), json.dumps(style, sort_keys=True))
    if key in _STATIC_CACHE:
        return _STATIC_CACHE[key]
    from PIL import ImageFilter
    # v2: text_scale_x < 1 condenses glyphs horizontally. Text, stroke and shadow are drawn together on a
    # supersampled canvas that is wider by 1/scale_x, then resampled once to the rail size, so the outline
    # and shadow are condensed exactly like the glyphs (no separate blur/warp of the stroke).
    scale_x = float(style.get("text_scale_x", 1.0))
    ss = int(style.get("supersample", 3))
    cw, ch_ = max(1, round(width * ss / scale_x)), height * ss
    kx = cw / width
    layer = Image.new("RGBA", (cw, ch_), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (cw, ch_), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    sdraw = ImageDraw.Draw(shadow)
    text_color = parse_color(style.get("text_color", "#F2A51C"))
    outline = parse_color(style.get("outline_color", "#3A2208"))
    shadow_color = parse_color(style.get("shadow_color", "#00000099"))
    divider = parse_color(style.get("divider_color", "#E59A1A"))
    divider_outline = parse_color(style.get("divider_outline_color", "#3A2208"))
    stroke_ratio = float(style.get("stroke_ratio", 0.09))
    divider_w = int(style.get("divider_width", round(9 * width / 1080)))
    divider_ol = int(style.get("divider_outline_width", 2))
    divider_inset = float(style.get("divider_inset", 0.10))
    sx, sy = style.get("shadow_offset", [3, 4])
    blur = float(style.get("shadow_blur", 2.5))
    pad = int(style.get("cell_padding", round(18 * width / 1080)))
    cell_w = min(edges[i + 1] - edges[i] for i in range(len(chapters)))
    max_text_w = cell_w - divider_w - 2 * divider_ol - 2 * pad
    max_text_h = int(height * float(style.get("text_height_ratio", 0.62)))
    target = int(style.get("font_size", round(height * 0.62)))
    # fit at output scale (width budget widened by 1/scale_x), then draw at ss x that size
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    base = uniform_font(probe, [c["label"] for c in chapters], style.get("font"), int(max_text_w / scale_x), max_text_h, target, stroke_ratio)
    font = choose_font(style.get("font"), base.size * ss)
    stroke = max(1, round(base.size * stroke_ratio)) * ss
    ref = draw.textbbox((0, 0), "国", font=font, stroke_width=stroke)
    y = (ch_ - (ref[3] - ref[1])) / 2 - ref[1]
    for index, chapter in enumerate(chapters):
        left, right = edges[index] * kx, edges[index + 1] * kx
        label = chapter["label"]
        box = draw.textbbox((0, 0), label, font=font, stroke_width=stroke)
        x = left + ((right - left) - (box[2] - box[0])) / 2 - box[0]
        sdraw.text((x + sx * ss / scale_x, y + sy * ss), label, font=font, fill=shadow_color, stroke_width=stroke, stroke_fill=shadow_color)
        draw.text((x, y), label, font=font, fill=text_color, stroke_width=stroke, stroke_fill=outline)
    if blur > 0:
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur * ss))
    out = Image.alpha_composite(shadow, layer).resize((width, height), Image.LANCZOS)
    font_size_out, stroke_out = base.size, stroke // ss
    ddraw = ImageDraw.Draw(out)
    top, bot = int(height * divider_inset), height - 1 - int(height * divider_inset)
    end_caps = bool(style.get("end_caps", True))
    for index, ex in enumerate(edges):
        if index == len(edges) - 1 and not end_caps:
            continue
        if index == 0:
            l = 0
        elif index == len(edges) - 1:
            l = width - divider_w - 2 * divider_ol
        else:
            l = ex - divider_w // 2 - divider_ol
        r = l + divider_w + 2 * divider_ol - 1
        ddraw.rectangle((l, top, r, bot), fill=divider_outline)
        ddraw.rectangle((l + divider_ol, top + divider_ol, r - divider_ol, bot - divider_ol), fill=divider)
    _STATIC_CACHE[key] = (out, font_size_out, stroke_out)
    return _STATIC_CACHE[key]


def draw_rail(width: int, height: int, seconds: float, chapters: list[dict[str, Any]], style: dict[str, Any]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    track = parse_color(style.get("track_color", "#ECECE873"))
    fill = parse_color(style.get("fill_color", "#F3E9A6D9"))
    draw.rectangle((0, 0, width - 1, height - 1), fill=track)
    edges = [round(i * width / len(chapters)) for i in range(len(chapters) + 1)]
    for index, chapter in enumerate(chapters):
        start, end = chapter["start"], chapter["end"]
        fraction = 0.0 if seconds <= start else 1.0 if seconds >= end else (seconds - start) / (end - start)
        left, right = edges[index], edges[index + 1]
        fill_right = left + round((right - left) * max(0.0, min(1.0, fraction)))
        if fill_right > left:
            # paint fill over the track (replace, not stack, so the fill alpha is exact)
            image.paste(Image.new("RGBA", (fill_right - left, height), fill), (left, 0))
    static, _, _ = _text_layer(width, height, chapters, style, edges)
    image.alpha_composite(static)
    return image


def make_preview(video: Path, out: Path, seconds: float, info: VideoInfo, chapters: list[dict[str, Any]], style: dict[str, Any], rail_height: int, bottom: int) -> None:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"],
        check=True, capture_output=True,
    ).stdout
    frame = Image.open(io.BytesIO(raw)).convert("RGBA")
    y = info.height - bottom - rail_height
    if y < 0:
        raise ValueError("bottom 与栏高超出画面")
    frame.alpha_composite(draw_rail(info.width, rail_height, seconds, chapters, style), (0, y))
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.convert("RGB").save(out, quality=95)


def render(video: Path, out: Path, info: VideoInfo, chapters: list[dict[str, Any]], style: dict[str, Any], rail_height: int, bottom: int, overlay_only: bool) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    y = info.height - bottom - rail_height
    if y < 0:
        raise ValueError("bottom 与栏高超出画面")
    frames = max(1, round(info.duration * info.fps))
    raw_input = ["-f", "rawvideo", "-pixel_format", "rgba", "-video_size", f"{info.width}x{rail_height}", "-framerate", f"{info.fps:.8f}", "-i", "pipe:0"]
    if overlay_only:
        cmd = ["ffmpeg", "-y", "-v", "warning", *raw_input, "-frames:v", str(frames), "-c:v", "qtrle", "-pix_fmt", "argb", str(out)]
    else:
        cmd = ["ffmpeg", "-y", "-v", "warning", "-i", str(video), *raw_input, "-filter_complex", f"[0:v][1:v]overlay=0:{y}:format=auto[v]", "-map", "[v]"]
        if info.has_audio:
            cmd += ["-map", "0:a?", "-c:a", "copy"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-shortest", str(out)]
    process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame in range(frames):
            process.stdin.write(draw_rail(info.width, rail_height, frame / info.fps, chapters, style).tobytes())
    except BrokenPipeError as exc:
        raise RuntimeError("FFmpeg 渲染管道提前结束") from exc
    finally:
        process.stdin.close()
    code = process.wait()
    if code != 0 or not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"渲染失败，FFmpeg 返回 {code}")


PRESET_DIR = Path(__file__).resolve().parent.parent / "assets" / "presets"


def load_preset(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    path = Path(value)
    if not path.suffix:
        path = PRESET_DIR / f"{value}.json"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in PRESET_DIR.glob("*.json")))
        raise FileNotFoundError(f"预设不存在: {value}（可用: {available}）")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a time-driven segmented chapter progress rail (v2 engine, presets).")
    parser.add_argument("input", type=Path)
    parser.add_argument("chapters", type=Path)
    parser.add_argument("--preset", help="预设名（assets/presets/<名>.json，如 xingjie）或预设 JSON 路径")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overlay-only", type=Path, metavar="MOV")
    parser.add_argument("--preview-image", type=Path)
    parser.add_argument("--preview-time", type=float, default=0.0)
    parser.add_argument("--bottom", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    args = parser.parse_args()
    if not args.input.exists() or not args.chapters.exists():
        parser.error("输入视频或 chapters.json 不存在")
    if not any((args.output, args.overlay_only, args.preview_image)):
        parser.error("至少指定 --output、--overlay-only 或 --preview-image")
    for out in (args.output, args.overlay_only):
        if out and out.resolve() == args.input.resolve():
            parser.error("禁止覆盖原始视频")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        parser.error("需要 ffmpeg 和 ffprobe")
    preset = load_preset(args.preset)
    info = probe_video(args.input)
    chapters, chapter_style = load_spec(args.chapters, info.duration)
    style = {**(preset.get("style") or {}), **chapter_style}
    layout = preset.get("layout") or {}
    ref_h = float(layout.get("reference_height", 1920))
    if args.height:
        rail_height = args.height
    elif "height" in layout:
        rail_height = max(48, round(layout["height"] * info.height / ref_h))
    else:
        rail_height = max(48, round(92 * info.height / 1920))
    if args.bottom is not None:
        bottom = args.bottom
    elif "bottom" in layout:
        bottom = max(0, round(layout["bottom"] * info.height / ref_h))
    else:
        bottom = max(0, round(320 * info.height / 1920))
    print(json.dumps({"preset": preset.get("name"), "rail_height": rail_height, "bottom": bottom, "rail_top_y": info.height - bottom - rail_height}, ensure_ascii=False))
    if args.preview_image:
        preview_time = min(max(0.0, args.preview_time), max(0.0, info.duration - 0.01))
        make_preview(args.input, args.preview_image, preview_time, info, chapters, style, rail_height, bottom)
        print(json.dumps({"preview": str(args.preview_image), "time": preview_time}, ensure_ascii=False))
    if args.output:
        render(args.input, args.output, info, chapters, style, rail_height, bottom, False)
        print(json.dumps({"output": str(args.output)}, ensure_ascii=False))
    if args.overlay_only:
        render(args.input, args.overlay_only, info, chapters, style, rail_height, bottom, True)
        print(json.dumps({"overlay": str(args.overlay_only), "y": info.height - bottom - rail_height}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
