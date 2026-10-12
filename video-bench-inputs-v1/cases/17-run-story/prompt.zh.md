# 17-run-story — GPX 跑步回放

读取 run.gpx 和 map.json，制作 20 秒竖屏回放，将完整模拟跑步过程压缩播放。在 local-map.svg 上绘制路线、移动跑者标记，并从 GPX 更新运动用时、累计距离和平均配速。明确区分运动时间与视频时间，结尾给出准确总结。

1080 × 1920 · 30 fps · 20 s · 600 frames

## 输入文件（相对于 public/input/）

- `local-map.svg`
- `map.json`
- `run.gpx`

初始化后，完整通用约定见 PROMPT.md。
