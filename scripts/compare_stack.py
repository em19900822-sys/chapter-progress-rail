#!/usr/bin/env python3
"""把「参考 / 旧版 / 新版」等多张图竖向拼成对比图（改样式时给用户看）。

每个 --item：图片路径、标签、可选裁切 y0:y1（只截导航条区域），统一缩放到 --width 宽。
例：
  python3 compare_stack.py compare.png \
    --item assets/reference/rail_zoom.png 参考 \
    --item old_300.png 旧版 1300:1420 \
    --item new_300.png 新版 1295:1430
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = ["/home/box/fonts/NotoSansSC-Black.otf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--item", nargs="+", action="append", required=True, metavar="PATH LABEL [Y0:Y1]")
    ap.add_argument("--width", type=int, default=1080)
    args = ap.parse_args()
    font = next((ImageFont.truetype(f, 30) for f in FONTS if Path(f).exists()), ImageFont.load_default())
    parts = []
    for item in args.item:
        if len(item) < 2:
            ap.error("--item 至少要 路径 和 标签")
        img = Image.open(item[0]).convert("RGB")
        if len(item) > 2:
            y0, y1 = (int(v) for v in item[2].split(":"))
            img = img.crop((0, y0, img.width, y1))
        img = img.resize((args.width, round(img.height * args.width / img.width)), Image.LANCZOS)
        head = Image.new("RGB", (args.width, 44), "white")
        ImageDraw.Draw(head).text((10, 4), item[1], fill=(200, 0, 0), font=font)
        parts += [head, img]
    sheet = Image.new("RGB", (args.width, sum(p.height for p in parts)), "white")
    y = 0
    for p in parts:
        sheet.paste(p, (0, y))
        y += p.height
    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
