# 章节进度导航条 / Chapter Progress Rail

一个独立的 Codex Skill：按需为视频添加随讲话连续推进的分段章节导航条。

## 能做什么

- 显示 2 至 5 个章节栏目
- 当前栏目随时间从左向右连续填充
- 已完成栏目保持填满，未开始栏目保持空白
- 支持中文字体、透明栏目层和直接合成 MP4
- 自动处理带旋转信息的手机视频

## 使用

把本目录安装到 Codex 的 Skills 目录，然后调用：

```text
$chapter-progress-rail
```

章节配置示例见 `references/chapter-schema.md`。

渲染脚本需要本机安装 Python、Pillow、FFmpeg 和 FFprobe。

## 目录

- `SKILL.md`：Skill 工作流与约束
- `agents/openai.yaml`：Codex UI 元数据
- `references/chapter-schema.md`：章节时间配置格式
- `scripts/render_chapter_rail.py`：旧版本地渲染器
- `scripts/render_chapter_rail_v2.py`：v2 渲染器（星姐风格，`--preset xingjie`）
- `scripts/edl_to_timeline.py`、`scripts/verify_rail.py`、`scripts/compare_stack.py`：时间轴、验证、对比图
- `assets/presets/`：预设（参考图 `assets/reference/` 为本机私有，不随仓库发布）
- 本机用法与更新记录见 `HOWTO.md`
