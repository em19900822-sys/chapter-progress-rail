---
name: chapter-progress-rail
description: 给已剪好的口播成片（尤其 7 号粗剪 bot 导出的粗剪第N版.mp4）加底部「章节进度导航条」：2–5 个等宽格子，当前栏随讲话时间从左往右连续填充，讲完的栏填满、没讲的栏空着。用户提到章节进度条、栏目导航条、分段进度条、章节导航、进度栏、像星姐那样的导航条、给粗剪/成片加栏目、按逐字稿时间分章，或要改导航条的位置/字号/颜色/标签时，都用这个技能，即使没说“技能”二字。负责：EDL+逐字稿换算成片时间轴、按真实词级时间分章、星姐风格预设渲染、预览与对比图、合成、抽帧验证、交付并给出抖音「章节要点」时间。不做：粗剪/剪辑、字幕、美颜调色、顶部动态提纲（另有技能）、写口播文案，也不改原片。
---

# 章节进度导航条

导航条是独立衍生层：原片只读，输出新文件 `*-chapter-rail(-vN).mp4`。默认用 `scripts/render_chapter_rail_v2.py --preset xingjie`（Tina 2026-10-27 认可的星姐风格）。旧脚本 `scripts/render_chapter_rail.py` 保留，用于旧样式或只要透明层的老流程。

## 标准流程

1. **取素材**：找到最新导出的成片，并确认它和最新 EDL 是同一版（版本号、导出时间、时长三者对得上）。拿不准就问，不要拿旧版做。素材位置和传输方法见 `references/delivery-tina.md`（本机私有文件，公开仓库里没有）。
2. **建成片时间轴**：逐字稿的时间戳是相对原始素材的，必须经 EDL 换算：
   `python3 scripts/edl_to_timeline.py --edl rough_cut_vN_edl.json --transcripts transcripts/ --out work/`
   得到 `final_transcript.txt` / `final_map.json`。ASR 错字多，只信时间戳。原理见 `references/timeline.md`。
3. **分段 + 标签**：按「问题 → 原因 → 方法」切大块，通常 3–5 栏。每栏 `start` 对齐该章第一个词的真实开始时间；最后一栏 `end` 用 ffprobe 量出的成片实际时长（EDL 累加值会比实际短零点几秒，末栏会填不满）。先给用户时间分段和草拟标签，**标签以用户写的为准**，改标签不动时间。标签风格见 `references/style-standard.md`「标签」。
4. **预览**：选中间栏正在进行的时刻出静帧：
   `python3 scripts/render_chapter_rail_v2.py 成片.mp4 chapters.json --preset xingjie --preview-image p.png --preview-time 300`
   改样式时再用 `scripts/compare_stack.py` 拼「参考 / 旧版 / 新版」竖向对比图给用户看。
5. **合成**：预览认可后 `--output 成片-chapter-rail-vN.mp4`。10 分钟的 1080×1920 成片约需 4 分钟，放后台跑。
6. **验证**：`python3 scripts/verify_rail.py 输出.mp4 chapters.json --preset xingjie --source 原片.mp4 --outdir check/`，再亲眼看 `check_sheet.png`。门槛见下文和 `references/verification.md`。
7. **交付**：放到用户指定位置，旧版不删，附 `chapters(_vN).json`。告诉用户每栏起点（mm:ss），让她发抖音时照填「章节要点」，这样导航条换格、章节要点、顶部提纲三处对齐。

## 关键判断

- **时间来自真实词级时间戳**，不按字数估算，也不按 EDL 段边界拍脑袋。
- **字号统一**：所有栏用同一字号（按最长标签算），不单栏缩小。栏多或标签长导致字号偏小时，把三个选项交给用户选：缩短最长标签 / 横向压窄文字（`text_scale_x`）/ 不等宽格。用户上次选的是横向压窄到 0.9，字号约 34px。
- **位置**：导航条紧贴字幕正下方，同时在抖音底部标题、话题区上方。1080×1920 默认 `--height 106 --bottom 504`（顶边 y≈1310）。放在画面 80% 左右会被抖音文案盖住。换画幅或字幕位置变了，先预览再定。
- **样式标准**（星姐 5 条）：栏少字少、字粗（橙金 Black + 深棕粗描边 + 投影）、已讲和未讲反差大、粗竖条形成格子感、位置在字幕下。详细参数和参考图见 `references/style-standard.md` 与 `assets/reference/`（本机私有，公开仓库里没有）。
- 用户否掉的东西别再拿出来：书面化标签（如「试纸假象」「读懂身体」），以及旧版的细线、半透明金黄填充。

## 质量门槛（不过不交付）

- ffprobe：分辨率和原片一致，有音频，时长和原片差不超过 0.1s。
- 抽帧（每个换格点前后各 1s、每栏中点、片尾）：当前栏在连续变长，前面的栏是满的，后面的栏是空的，换格就发生在 chapters.json 写的那一秒。片尾所有栏都满。
- 裁切验证区域时，y 范围按 `--bottom/--height` 计算。上次手动裁偏过一次，用 `verify_rail.py` 就不会。
- 字体回退（脚本打印 `WARNING: 字体…已回退`）、时间段无效、FFmpeg 报错：停下来说明情况，不要交一个看着成功的结果。
- 视频已经有字幕时，导航条要避开字幕。如果之后还要加字幕：先合导航条，最后合字幕。

## 参考文件（按需读）

- `references/style-standard.md`：星姐风格拆解、预设参数、标签风格、字号取舍。改样式或写标签前读。
- `references/verification.md`：预览、对比图、合成后验证的细节，以及 verify_rail.py 的原理和局限。
- `references/timeline.md`：EDL 映射公式、章节起点怎么找、末栏怎么处理。
- `references/chapter-schema.md`：chapters.json 格式、style 字段、预设合并规则。
- `references/delivery-tina.md`：本机环境（素材路径、分块传输、交付文件夹），私有文件，不随仓库发布。
- `assets/presets/xingjie.json`：默认预设。`assets/reference/`：参考图，本机私有，不随仓库发布。
