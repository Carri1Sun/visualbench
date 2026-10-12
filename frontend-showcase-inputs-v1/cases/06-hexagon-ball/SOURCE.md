# 06 旋转六边形弹球

Source: https://www.reddit.com/r/LocalLLaMA/comments/1jwhp26/deepcoder_14b_vs_qwen25_coder_32b_vs_qwq_32b/

## 公开输入与原题环境
公开帖给出 HTML5 Canvas 弹球题，包含重力、边界碰撞及重置；没有图像或项目输入。

## 本包的处理
新增统一初始参数、暂停和转速滑块，让不同实现可以接受相同操作。

`prompt.en.txt` / `prompt.zh.txt` 是本包独立撰写的完整测试版，不是原文全文转载。
`short.en.txt` / `short.zh.txt` 是本包的一句版本，要求范围小于完整版本。
完整公开原题请通过上方来源链接查看；本目录不冒充原始项目或原文备份。

## 预置文件
assets/physics.json

本包新增的数据、文案和 SVG 输入素材均标为新增内容；它们不是原作者使用过的素材。
`starter` 是空白运行模板，没有题目答案、设计稿或已实现的交互。

## 验收观察
- 球始终位于容器内部
- 碰撞包含转动墙面影响
- 长时间运行不异常爆炸
- 重置可重复得到初始状态
