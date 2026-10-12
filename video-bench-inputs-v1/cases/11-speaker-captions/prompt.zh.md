# 11-speaker-captions — 人物后方关键词字幕

使用 source.mp4 与 transcript.json 制作 11.5 秒字幕视频，保留人物动作和原音频时序。将绿幕替换为简洁设计背景，利用提供的人物遮罩让至少一个巨大关键词出现在人物后方，普通字幕位于前方。强调词从实际转录选择。本题是绿幕合成版本，不考自然背景分割。

1280 × 720 · 30 fps · 11.5 s · 345 frames

## 输入文件（相对于 public/input/）

- `MEDIA_SOURCE.md`
- `TIMING_NOTES.md`
- `captions.srt`
- `foreground-mask.mp4`
- `foreground.webm`
- `source.mp4`
- `transcript.json`
- `transcript.txt`

初始化后，完整通用约定见 PROMPT.md。
