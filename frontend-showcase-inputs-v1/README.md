# 前端模型 Showcase 输入包 · 20 题

## 先回答：一句 prompt，还是有基础素材？

多数公开例子属于 text-to-code：用户给文本，模型自己绘图或写页面，没有必须提供的参考照片/设计稿。
但“一次提交任务”不等于“一句短话”，也不等于模型一次输出就一定成功。第 3 题原仓库带系统提示与渲染配置；第 4、9 题原说明很长，允许或要求工具验证；第 10 题公开作品有多轮迭代；第 18 题原输出是 React 组件，需要宿主；第 20 题原范围包含后端和数据来源。
Goldie Bench 的短原题运行于作者 Agent OS，完整系统模板未公开，本包不能声称精确复现那套环境。
第 16–18 题原仓库的 `assets/` 截图是生成结果，不是应提供给参赛模型的输入。

## 包含什么

- 20 个题目目录，保持上一条回复的编号与题目。
- 每题中文/英文完整测试 prompt、一句版 prompt、来源与改写说明、观察清单和操作建议。
- 固定 JSON 数据：机芯、禅意短句、弹球、布料、太阳系、排序、唱片、SaaS、定价、经营指标、咖啡订阅、关系图谱。
- 原创输入素材：3 张唱片封面 SVG 和 1 个咖啡袋 SVG。没有这些题目的最终页面答案。
- 空白 HTML / Three.js 模板、本地固定版本 Three.js；另附可选 React JSX 宿主。
- `manifest.json` 与 `cases.csv`，方便接入你的展示页或批量生成流程。
- `scripts/prepare_case.py`，把任意一题复制成独立的可生成工作目录。
- `ready-prompts/` 中的 20 份中英文完整输入，可以直接粘贴给聊天模型。

新增 JSON、文案与 SVG 是本包为可比较性编制的输入，均标为新增，不伪装成原作者素材。
长原题采用独立重写的可执行版本并保留出处；可引用的简短原题另存 original-short.en.txt。
第 3 题另有未修改 original-config.json 作为原题参考；它不等同于本包默认运行配置。

## 最省事的用法：直接复制 prompt

打开 `ready-prompts/01-pelican-bicycle.en.txt`（或 `.zh.txt`），整份复制给模型。
其中已经组合：统一交付要求 + 题目 prompt + 该题的全部文本/JSON/SVG 输入。
所有 20 题都这样提供，复杂题也只是一次任务提交，输入长度会更长。
模型应交付 `plan.json` 和 `artifact.html`。公开设计方案与实际结果一起展示，不需要私有推理。
聊天模型没有本地文件时，应根据内嵌素材重建相应 assets 文件；使用 Three.js 时还需把本包 vendor 目录放入运行目录。

## Coding agent 用法

在解压目录运行：
```bash
python3 scripts/prepare_case.py 19-coffee-subscription --dest runs/model-a/19/run-1
cd runs/model-a/19/run-1
python3 -m http.server 8000
```
把运行目录中的 `INPUT.en.txt` 发给 agent，或读取 `request.json` 的 system / user 字段作为模型输入。
让 agent 使用这个运行目录，完成后访问 http://localhost:8000/artifact.html。
初始 `index.html` 是空模板；没有模型结果时它为空白是正常的。
`INPUT.en.txt` 是便于复制的文本文件，不是可直接执行的程序。
准备脚本只复制 input，不调用任何模型、收费接口或第三方服务。

其他选项：
```bash
python3 scripts/prepare_case.py 06-hexagon-ball --lang zh --variant short --dest runs/model-b/06/run-1
python3 scripts/validate_pack.py
```
short 是本包一句版本，需求更少。full 和 short 要分成不同实验组；每一组所有模型使用相同语言、同一 input。

## 如何跑 5 次

每题每模型创建 5 个独立工作目录和新会话：run-1 到 run-5。不要把上次结果传给下一次。
保留五次全部结果，包括失败；记录 model id、参数、实际 prompt、时间、token（若提供）、工具权限和人工修复。
默认先比较一次输出结果。若允许 agent 反复调试，所有模型使用同样工具和预算，并另标 agent 模式。
所有桌面截图使用 1280×800。产品页再记录 390×844。动画录制相同 8 秒；按 case.json 的同一操作建议记录交互状态。
操作建议是人工/浏览器自动化脚本的语义清单，并不是已经验证过的 CSS 选择器或 Playwright 程序。
渲染随机性与模型生成随机性应分开记录；如固定随机种子或虚拟时钟，所有模型使用同一规则。

## 素材与运行范围

默认 HTML 赛道运行时无需互联网：字体用系统字体，图形程序化生成，音乐用 Web Audio，地图为本地示意图。
Three.js 0.180.0 已附本地文件，只附 OrbitControls 插件。运行通过 HTTP，不能依赖 file:// 下 fetch 正常工作。
可选 React 模板需要 npm 安装和兼容 Node；不包含 node_modules 或锁文件，也没有声称已验证其安装。默认赛道无需它。
太阳系数据是近似教学参数，显示尺度为示意，不能当作实时星历。
关系图谱完全虚构；无需个人数据、OSINT 账户、地图密钥或后端数据库。

## 交付前校验

已校验题目编号、JSON、SVG 语法、素材引用、解压与准备脚本、本地 Three.js 模块解析；空模板不含题目答案。
当前环境缺少浏览器可执行程序，未进行浏览器渲染验证。未实际调用 20 题的参赛模型，不保证任何模型一次完成或这些任务的通过率。
来源页面与未来依赖版本可能变化；本包是带来源记录的固定输入版本。
