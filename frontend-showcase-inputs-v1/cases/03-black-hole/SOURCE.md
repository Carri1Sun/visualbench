# 03 旋转黑洞

Source: https://github.com/jdmnk/design-benchmark/blob/main/config/examples/black-hole-spin.config.json

## 公开输入与原题环境
原仓库有 systemPrompt、长任务提示词、统一视口和渲染配置；Three.js 等库由运行环境提供。没有必需的输入照片或模型。

## 本包的处理
主测试版独立重写，提供固定 Three.js 本地文件。另存仓库原始配置（仓库 README 声明 MIT），用于查看原题环境差异。

`prompt.en.txt` / `prompt.zh.txt` 是本包独立撰写的完整测试版，不是原文全文转载。
`short.en.txt` / `short.zh.txt` 是本包的一句版本，要求范围小于完整版本。
完整公开原题请通过上方来源链接查看；本目录不冒充原始项目或原文备份。

## 预置文件
无题目专属素材。

本包新增的数据、文案和 SVG 输入素材均标为新增内容；它们不是原作者使用过的素材。
`starter` 是空白运行模板，没有题目答案、设计稿或已实现的交互。

## 验收观察
- 黑色中心和横向吸积盘清楚
- 上下亮弧构成空间层次
- 运动可辨认且稳定
- 不会仅有 HUD 而主体黑屏
