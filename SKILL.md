---
name: chapter-progress-rail
description: 为任意成片按需生成并合成随讲话持续推进的分段章节导航条。用于章节进度条、栏目导航条、分段进度栏、当前栏目黄色填充等需求；不负责常规字幕或整条视频剪辑。
---

# 章节进度导航条

把栏目层作为独立衍生物处理，不修改用户的剪辑项目或原始视频。默认使用本 Skill 的本地 Pillow + FFmpeg 渲染器，不依赖 OpenMontage、Remotion 或付费服务。

## 工作流

1. 确认输入成片、输出位置、栏目名称与每栏起止时间。用户提供逐字稿或字幕时，可根据内容结构拟定栏目，再用真实字幕时间对齐边界；不要按字数估算时间。
2. 用 `references/chapter-schema.md` 的格式写出 `chapters.json`。栏目短而清楚，通常 2 至 5 个；保持时间连续、递增且不重叠。
3. 先运行 `scripts/render_chapter_rail.py --preview-image`，检查手机画面中的位置、字号、遮挡和中文显示。
4. 预览合格后再渲染视频。保留原始视频，输出新的 `*-chapter-rail.mp4`。只需要透明的栏高视频层时使用 `--overlay-only`，它适合放进已有剪辑时间线，位置按命令输出的 y 值摆放。
5. 用 `ffprobe` 检查尺寸、时长、帧率和音频流，并抽查每个章节的开始、中间、结束三处：已完成栏应填满，当前栏应连续增长，未来栏应为空。

## 默认视觉

- 横向等宽分栏，半透明暖灰底，浅暖黄色进度填充，深色描边文字和栏目分隔线。
- 当前栏从左向右线性填充；已经讲完的栏保持填满；未开始的栏不填充。
- 默认放在画面下部、字幕下方或上方的安全空位。若与人脸、字幕、免责声明重叠，调整 `--bottom`，不要缩到难以阅读。
- 1080×1920 竖屏默认栏高 92px。脚本会按视频高度缩放字号和线宽。

## 命令

```powershell
python scripts/render_chapter_rail.py input.mp4 chapters.json `
  --preview-image preview.png --preview-time 12

python scripts/render_chapter_rail.py input.mp4 chapters.json `
  --output input-chapter-rail.mp4

python scripts/render_chapter_rail.py input.mp4 chapters.json `
  --overlay-only chapter-rail.mov
```

## 必须遵守

- 原始视频只读，绝不覆盖。
- 进度由真实时间驱动，不能在章节结束时突然跳格。
- 首次使用新样式或新画幅时必须先做静帧或短片预览。
- 中文字体加载失败、时间段无效、FFmpeg 失败时停止交付，不生成假成功结果。
- 视频已有字幕时，栏目层必须避开字幕；后续另加字幕时，栏目层先合成，字幕最后合成。
