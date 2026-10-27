# 成片时间轴与章节起点

## 为什么要映射

7 号粗剪 bot 只在共享电脑上留下 EDL（`/workspace/roughcut-*/artifacts/rough_cut_vN_edl.json`）和逐字稿（`transcripts/<素材号>.json`，词级时间戳），这些时间都是**相对各原始素材**的。导出的成片在用户电脑上。要拿到成片里的时间，必须按 EDL 换算。

## 公式

按 `order` 排好 EDL 段，对每一段：
`成片时间 = 前面所有段时长累加 + (源时间 − 段 start_seconds)`，源时间先夹到 [start, end] 范围内。
一个词的中点落在段里，才算这一段的词。素材号从 `input_path` 末尾的文件名里取（`D:\...\3.MOV` → `transcripts/3.json`），正则可以用 `--key-regex` 改。

```bash
python3 scripts/edl_to_timeline.py \
  --edl /workspace/roughcut-1026/artifacts/rough_cut_v4_edl.json \
  --transcripts /workspace/roughcut-1026/transcripts \
  --out /workspace/rail-MMDD/
```

输出 `final_transcript.txt`，每行是 `[mm:ss.s-mm:ss.s] 文本`，按成片时间；还有 `final_map.json`，里面有 total、lines、words。

## 章节起点和终点

- 用 `final_transcript.txt` 读内容结构，按「问题 → 原因 → 方法」切块。在 `final_map.json` 的 words 里找到每章第一个词，用它的 start 作为这一章的 start，保留两位小数。
- ASR 错字很多（备孕识别成被运、试纸识别成式子），找章节靠语义，时间只取时间戳。
- 每一章的 end 等于下一章的 start，保证连续、没有空档。
- 最后一章的 end 要用 ffprobe 量出的成片实际时长，比如 602.27。EDL 累加出来是 602.01，会比实际短，末栏到片尾就填不满。
- 先把分段表（mm:ss）和草拟标签发给用户确认，再写 `chapters.json`。
