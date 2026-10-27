# 预览与验证

## 合成前：预览

- 先出静帧，选“中间那栏正在进行”的时刻（例如 5 栏时选第 3 栏中段），一张图就能同时看到满、半、空三种状态：
  `python3 scripts/render_chapter_rail_v2.py 成片.mp4 chapters.json --preset xingjie --preview-image p_300.png --preview-time 300`
  脚本第一行会打印 `rail_top_y`，后面裁切、写说明都用它。
- 看：有没有挡脸，是不是紧贴字幕下方，最长标签放不放得下，字号有没有被压小，已讲和未讲能不能一眼分清。
- 改样式时出对比图（参考 / 旧版 / 新版），只裁导航条那一带：
  ```bash
  python3 scripts/compare_stack.py compare.png \
    --item assets/reference/rail_zoom.png 参考（星姐） \
    --item old_300.png 旧版 1490:1620 \
    --item new_300.png 新版 1295:1430
  ```
  裁切范围按 `y = H - bottom - height` 算，上下各留 10–20px。
- 用户确认之前先别合成整片；如果用户说“直接合成”，就把预览图和成片一起交。

## 合成后：verify_rail.py

```bash
python3 scripts/verify_rail.py 输出.mp4 chapters.json --preset xingjie --source 原片.mp4 --outdir check/
```

它做三件事，有问题就返回码 1，并把问题列在 `problems` 里：
1. **ffprobe**：分辨率和原片一致，有音频，时长差不超过 0.1s。
2. **抽帧**：每个换格点前 1s 和后 1s、每栏中点、片尾前 0.5s。只裁导航条区域（y 范围按 preset 或 --bottom/--height 算，和渲染时一致），竖拼成 `check_sheet.png`，每条上方标出时间和应有的填充比例。
3. **自动量填充**：取栏顶部几行（那里没有字，也没有竖条），把“偏黄并且够亮”的像素算作已填充，估出每栏的填充比例，和 chapters.json 推算的值比，容差 0.08。结果写进 `verify_report.json`。

局限：第 3 步是启发式，阈值按预设的 fill_color 算。像旧样式那种填充透明度低的（`#FFE77A99` 压在深色衣服上），它会大量报不符。这正好说明旧样式反差不够，不代表时间错了。背景很黄或很亮时也可能误判。所以 `problems` 为空也要亲眼看一遍 `check_sheet.png`：

- 当前栏在连续变长（中点大约到一半）；
- 换格前那一帧，当前栏差一点就满，下一栏还是空的；换格后那一帧，上一栏满了，下一栏刚开始；
- 片尾所有栏都满；
- 字、竖条、端条没有被裁掉，也没有错位。

2026-10-27 用 v2 成片跑过一次：14 个抽样点全部和预期一致，problems 为空。
