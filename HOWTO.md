# 章节进度导航条 (chapter-progress-rail)：本机用法

路径：`/home/box/skills/chapter-progress-rail`
上游：https://github.com/em19900822-sys/chapter-progress-rail（本机改动很多，未回推）

**只做一件事**：给剪好的成片叠加「随讲话时间连续推进」的分段章节导航条。
**不做**：粗剪、字幕、美颜、顶部提纲（另有 top-dynamic-outline 技能）、文案。

## 目录

```
SKILL.md                      流程、判断规则、质量门槛（按 skill-creator 规范写）
HOWTO.md                      本文件：本机命令和更新记录
references/
  style-standard.md           星姐风格拆解、预设参数、标签风格、字号取舍
  verification.md             预览、对比图、verify_rail 的原理和局限
  timeline.md                 EDL 到成片时间轴、章节起点和终点
  chapter-schema.md           chapters.json 格式、style 字段、预设合并规则
  delivery-tina.md            本机路径、分块传输、交付文件夹（私有，不随仓库发布）
scripts/
  render_chapter_rail.py      旧渲染器（原样保留，旧调用方式不变）
  render_chapter_rail_v2.py   新渲染器：统一字号、横向压窄、粗描边投影、粗分隔条、--preset
  edl_to_timeline.py          EDL 加逐字稿，生成 final_transcript.txt 和 final_map.json
  verify_rail.py              ffprobe 检查、抽帧拼成 check_sheet、自动量填充比例
  compare_stack.py            把参考、旧版、新版竖向拼成对比图
assets/
  presets/xingjie.json        默认预设（Tina 2026-10-27 认可）
  reference/                  星姐原图、导航条特写、参考/旧版/新版对比图
```

## 依赖

Python 3 + Pillow、ffmpeg/ffprobe；字体 `/home/box/fonts/NotoSansSC-Black.otf`。缺这个字体时回退到 `/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc`，并打印 WARNING。

## 常用命令

```bash
S=/home/box/skills/chapter-progress-rail/scripts
W=/workspace/rail-MMDD   # 当天的工作目录

# 1) 成片时间轴
python3 $S/edl_to_timeline.py --edl /workspace/roughcut-MMDD/artifacts/rough_cut_vN_edl.json \
  --transcripts /workspace/roughcut-MMDD/transcripts --out $W --quiet

# 2) 写 $W/chapters.json（每栏 start 取该章第一个词的开始时间，末栏 end 用 ffprobe 量的时长）
ffprobe -v error -show_entries format=duration -of csv=p=0 $W/粗剪第N版.mp4

# 3) 预览（选中间栏正在进行的时刻）
python3 $S/render_chapter_rail_v2.py $W/粗剪第N版.mp4 $W/chapters.json --preset xingjie \
  --preview-image $W/preview_300.png --preview-time 300

# 4) 合成（约 4 分钟/10 分钟片，放后台）
python3 $S/render_chapter_rail_v2.py $W/粗剪第N版.mp4 $W/chapters.json --preset xingjie \
  --output $W/粗剪第N版-chapter-rail.mp4

# 5) 验证（返回码 1 = 有问题；无论如何都要看 check_sheet.png）
python3 $S/verify_rail.py $W/粗剪第N版-chapter-rail.mp4 $W/chapters.json --preset xingjie \
  --source $W/粗剪第N版.mp4 --outdir $W/check

# 改样式时的对比图
python3 $S/compare_stack.py $W/compare.png --item ../assets/reference/rail_zoom.png 参考 \
  --item $W/old.png 旧版 1490:1620 --item $W/new.png 新版 1295:1430

# 旧渲染器（旧样式 / --overlay-only 透明层）
python3 $S/render_chapter_rail.py in.mp4 chapters.json --preview-image p.png --preview-time 12
```

预设默认值：1080×1920 下 `--height 106 --bottom 504`，栏顶边 y≈1310。在命令行写 `--height/--bottom` 会覆盖预设；chapters.json 里的 `style` 会逐个键覆盖预设的 style。

## 传输要点（本机细节见 references/delivery-tina.md，私有文件，不随仓库发布）

单文件上限 100MiB，按 5MB 分块，失败的块单独重试；CopyFromBox 只能写相对路径（落在用户目录下），之后在电脑上用 python 拼接并移动；两端都核 sha256，传完删临时块；PowerShell 里用 `python -c`。交付到 `<日期>视频\章节导航条\`，旧版不删。

## 更新记录

- **2026-10-27**：按 Anthropic skill-creator 规范重写 SKILL.md，frontmatter 写明了什么时候触发、不做什么，细节移到 references/。新增 v2 渲染器加 `--preset`，默认预设为 xingjie（星姐风格：Black 粗体、粗描边加投影、奶油黄和透明灰的强反差、粗橙分隔条加端条、统一字号、横向压窄 0.9、位置在字幕正下方）。新增 edl_to_timeline.py、verify_rail.py、compare_stack.py，新增参考图。来源是 10.26 视频「粗剪第四版」的实战：标签用 Tina 写的大白话版本，各栏起点 00:00/01:08/04:31/06:47/08:34。旧脚本原样保留。改动前的备份在 `/home/box/skills/.backup/chapter-progress-rail-20261027/`。
  烟雾测试：v2 加 xingjie 预设出的预览图，和当天交付用的 preview_300 逐像素一致；旧脚本的旧调用方式输出逐像素不变；edl_to_timeline 的输出和当天的 final_transcript.txt、final_map.json 逐字节一致；verify_rail 对 v2 成片检查 14 个抽样点，全部通过。
- **2026-10-19**：初次安装，补了 Linux 下的 Noto CJK 字体路径。用短竖屏测试片跑通了预览和合成。
