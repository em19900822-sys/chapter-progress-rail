# Chapter JSON

最小格式：

```json
{
  "chapters": [
    {"label": "判断类型", "start": 0, "end": 45},
    {"label": "找根源", "start": 45, "end": 110},
    {"label": "怎么做", "start": 110, "end": 180}
  ]
}
```

`start` 和 `end` 的单位均为秒。`end` 可以省略：脚本会使用下一栏的 `start`，最后一栏使用视频结束时间。

可选 `style` 字段：`fill_color`、`track_color`、`text_color`、`divider_color`、`outline_color` 和本地中文字体文件 `font`。颜色使用 `#RRGGBB` 或 `#RRGGBBAA`。

要求：栏目按时间排序，时段不重叠，`end > start`，最后结束时间不能明显超过视频时长。
