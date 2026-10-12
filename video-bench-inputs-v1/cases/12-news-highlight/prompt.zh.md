# 12-news-highlight — 新闻截图动态划重点

使用 article.png 原图制作 8 秒新闻插片：在白色背景上由模糊变清晰，文章缓慢推近并轻微三维旋转，随后手绘感荧光笔划过 highlights.json 中的准确词组。通过截图或 OCR 找到位置，标记不能遮挡字形。

1920 × 1080 · 30 fps · 8 s · 240 frames

## 输入文件（相对于 public/input/）

- `article.png`
- `fonts/DejaVuSans.ttf`
- `fonts/LICENSE.txt`
- `highlights.json`

初始化后，完整通用约定见 PROMPT.md。
