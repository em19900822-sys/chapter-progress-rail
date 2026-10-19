#!/usr/bin/env python3
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


def choose_font(custom: str | None, size: int) -> ImageFont.FreeTypeFont:
    for candidate in [
        custom, "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    ]:
        if candidate and Path(candidate).exists():
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


def draw_rail(width: int, height: int, seconds: float, chapters: list[dict[str, Any]], style: dict[str, Any]) -> Image.Image:
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    scale = height / 92.0
    track = parse_color(style.get("track_color", "#E8E2D7B8"))
    fill = parse_color(style.get("fill_color", "#FFE77A99"))
    text_color = parse_color(style.get("text_color", "#F1B928"))
    divider = parse_color(style.get("divider_color", "#9B6A00E6"))
    outline = parse_color(style.get("outline_color", "#4A3200E6"))
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=max(2, int(3 * scale)), fill=track)
    edges = [round(i * width / len(chapters)) for i in range(len(chapters) + 1)]
    for index, chapter in enumerate(chapters):
        start, end = chapter["start"], chapter["end"]
        fraction = 0.0 if seconds <= start else 1.0 if seconds >= end else (seconds - start) / (end - start)
        left, right = edges[index], edges[index + 1]
        fill_right = left + round((right - left) * max(0.0, min(1.0, fraction)))
        if fill_right > left:
            draw.rectangle((left, 0, fill_right, height - 1), fill=fill)
        if index:
            draw.line((left, int(8 * scale), left, height - int(8 * scale)), fill=divider, width=max(2, int(3 * scale)))
        label = chapter["label"]
        font = fit_font(draw, label, style.get("font"), max(20, right - left - int(24 * scale)), int(46 * scale))
        stroke = max(1, int(2 * scale))
        box = draw.textbbox((0, 0), label, font=font, stroke_width=stroke)
        x = left + ((right - left) - (box[2] - box[0])) / 2
        y = (height - (box[3] - box[1])) / 2 - box[1]
        draw.text((x, y), label, font=font, fill=text_color, stroke_width=stroke, stroke_fill=outline)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a time-driven segmented chapter progress rail.")
    parser.add_argument("input", type=Path)
    parser.add_argument("chapters", type=Path)
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
    if args.output and args.output.resolve() == args.input.resolve():
        parser.error("禁止覆盖原始视频")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        parser.error("需要 ffmpeg 和 ffprobe")
    info = probe_video(args.input)
    chapters, style = load_spec(args.chapters, info.duration)
    rail_height = args.height or max(48, round(92 * info.height / 1920))
    bottom = args.bottom if args.bottom is not None else max(0, round(320 * info.height / 1920))
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
