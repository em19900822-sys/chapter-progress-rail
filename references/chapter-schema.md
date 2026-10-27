# chapters.json 格式

```json
{
  "chapters": [
    {"label": "没强阳别慌", "start": 0.0,    "end": 67.97},
    {"label": "黄金期时差", "start": 67.97,  "end": 271.36},
    {"label": "越饿越难怀", "start": 271.36, "end": 406.69},
    {"label": "教你抓排泡泡", "start": 406.69, "end": 513.53},
    {"label": "回去这样干", "start": 513.53, "end": 602.27}
  ]
}
```

- 单位都是秒。`end` 可以不写：没写时取下一栏的 `start`，最后一栏取视频时长。不过建议写全，末栏写 ffprobe 量出的实际时长。
- 栏目要按时间排序，不能重叠，并且 `end > start`。最后的结束时间比视频时长多出 0.25s 以上会报错。
- 也可以用 `startSeconds` 和 `endSeconds` 代替 start、end。

## style（可选）

**旧脚本** `render_chapter_rail.py` 支持：`fill_color`、`track_color`、`text_color`、`divider_color`、`outline_color`、`font`。

**v2 脚本** `render_chapter_rail_v2.py` 在上面这些之外还支持：
`shadow_color`、`shadow_offset` [x,y]、`shadow_blur`、`stroke_ratio`、`divider_outline_color`、`divider_width`、`divider_outline_width`、`divider_inset`、`end_caps`、`cell_padding`、`text_height_ratio`、`font_size`（目标字号上限）、`text_scale_x`、`supersample`。

颜色写成 `#RRGGBB` 或 `#RRGGBBAA`。

## 预设合并规则（v2）

`--preset xingjie` 会读取 `assets/presets/xingjie.json`，也可以直接给一个 JSON 路径。
- 最终样式 = 预设的 style，再用 chapters.json 里的 style 逐个键覆盖。
- 栏高和底距的优先级：命令行 `--height/--bottom` 最高，其次是预设 layout（按视频高度相对 reference_height 等比缩放），最后是默认的 92 和 320（以 1920 高为基准）。

建议存两份：交付用的 `chapters_vN.json` 带完整 style，方便以后复现；日常只写 chapters，配合 `--preset`。
