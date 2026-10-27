#!/usr/bin/env python3
"""把粗剪 EDL + 原始素材逐字稿（词级时间戳）映射到成片时间轴。

成片时间 = 前面所有段时长累加 + (源时间 − 段 start)，源时间被夹在 [start, end] 内。
一个词的中点落在段内才算进该段。原始素材按 input_path 末尾文件名里的编号匹配逐字稿
（如 D:\\...\\3.MOV → transcripts/3.json）。

输出：
  <out>/final_transcript.txt  每行 "[mm:ss.s-mm:ss.s] 文本"（成片时间）
  <out>/final_map.json        {"total": 成片总长, "lines": [[st, en, 文本, order, 素材号]...],
                               "words": [[st, en, 词, order]...]}
ASR 错字多（备孕→被运、试纸→式子），只信时间戳，不信字面。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def source_key(input_path: str, pattern: str) -> str:
    name = re.split(r"[\\/]", input_path)[-1]
    m = re.search(pattern, name)
    if not m:
        raise ValueError(f"无法从素材文件名提取编号: {input_path}（--key-regex={pattern}）")
    return m.group(1)


def build(edl_path: Path, transcripts: Path, key_regex: str):
    payload = json.loads(edl_path.read_text(encoding="utf-8"))
    segments = sorted(payload["segments"], key=lambda s: s["order"])
    cache: dict[str, dict] = {}
    off = 0.0
    lines, words = [], []
    for s in segments:
        k = source_key(s["input_path"], key_regex)
        if k not in cache:
            tp = transcripts / f"{k}.json"
            if not tp.exists():
                raise FileNotFoundError(f"缺少逐字稿 {tp}（对应素材 {s['input_path']}）")
            cache[k] = json.loads(tp.read_text(encoding="utf-8"))
        a, b = s["start_seconds"], s["end_seconds"]

        def m(t: float, a=a, b=b, off=off) -> float:
            return off + min(max(t, a), b) - a

        for seg in cache[k]["segments"]:
            ws = [w for w in seg["words"] if a <= (w["start"] + w["end"]) / 2 <= b]
            if not ws:
                continue
            txt = "".join(w["word"] for w in ws)
            lines.append((m(ws[0]["start"]), m(ws[-1]["end"]), txt, s["order"], k))
            for w in ws:
                words.append((m(w["start"]), m(w["end"]), w["word"], s["order"]))
        off += b - a
    return off, lines, words


def main() -> int:
    ap = argparse.ArgumentParser(description="EDL + 逐字稿 → 成片时间轴（final_transcript.txt / final_map.json）")
    ap.add_argument("--edl", type=Path, required=True, help="如 /workspace/roughcut-1026/artifacts/rough_cut_v4_edl.json")
    ap.add_argument("--transcripts", type=Path, required=True, help="逐字稿目录，内含 <编号>.json")
    ap.add_argument("--out", type=Path, required=True, help="输出目录")
    ap.add_argument("--key-regex", default=r"(\d+)\.\w+$", help=r"从素材文件名提取编号的正则，默认 (\d+)\.\w+$")
    ap.add_argument("--quiet", action="store_true", help="不在终端逐行打印")
    args = ap.parse_args()
    total, lines, words = build(args.edl, args.transcripts, args.key_regex)
    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "final_transcript.txt", "w", encoding="utf-8") as f:
        for st, en, t, o, k in lines:
            f.write(f"[{fmt(st)}-{fmt(en)}] {t}\n")
    with open(args.out / "final_map.json", "w", encoding="utf-8") as f:
        json.dump({"total": total, "lines": lines, "words": words}, f, ensure_ascii=False)
    print("TOTAL", total)
    if not args.quiet:
        for st, en, t, o, k in lines:
            print(f"{st:7.2f} [{fmt(st)}] #{o} {t}")
    print(json.dumps({"total": round(total, 3), "lines": len(lines), "words": len(words), "out": str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
