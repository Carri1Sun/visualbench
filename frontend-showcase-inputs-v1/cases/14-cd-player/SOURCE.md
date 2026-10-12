# 14 PS1 风格 CD 播放器

Source: https://www.bridgebench.ai/prompts/a3a1f845-18a4-4f82-9865-e412949067f5

## 公开输入与原题环境
原题是短描述，要求低多边形播放器、CD 与封面交互，且每张唱片有完整 chiptune 音乐；未附音频或图片。

## 本包的处理
新增原创唱片名称、封面 SVG 和短音序；将完整乐曲缩小为循环短音序，不复用已有音乐。

`prompt.en.txt` / `prompt.zh.txt` 是本包独立撰写的完整测试版，不是原文全文转载。
`short.en.txt` / `short.zh.txt` 是本包的一句版本，要求范围小于完整版本。
完整公开原题请通过上方来源链接查看；本目录不冒充原始项目或原文备份。

## 预置文件
assets/albums.json; assets/cover-orbit.svg; assets/cover-afterglow.svg; assets/cover-tidal.svg

本包新增的数据、文案和 SVG 输入素材均标为新增内容；它们不是原作者使用过的素材。
`starter` 是空白运行模板，没有题目答案、设计稿或已实现的交互。

## 验收观察
- 选中、插入、播放、退出状态清楚
- 唱片堆随状态重排
- 不能同时播放两张 CD
- 音频仅在用户激活后运行，静音有效
