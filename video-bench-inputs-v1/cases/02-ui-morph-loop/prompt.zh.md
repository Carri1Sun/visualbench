# 02-ui-morph-loop — 单一形状 UI 变形循环

读取 states.json，制作 16 秒无缝循环。同一个外壳按顺序变成 8 种 UI，鼠标通过点击和拖拽触发变化。外壳保持空间连续，内部内容可以过渡切换。使用 120 BPM 的 beat.wav，让主要变化贴合节拍，结尾回到开头状态。

1080 × 1080 · 30 fps · 16 s · 480 frames

## 输入文件（相对于 public/input/）

- `beat.json`
- `beat.wav`
- `states.json`

初始化后，完整通用约定见 PROMPT.md。
