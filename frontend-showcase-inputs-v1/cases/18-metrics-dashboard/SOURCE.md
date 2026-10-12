# 18 经营指标面板

Source: https://github.com/dani-z/frontend-design-skill-benchmark

## 公开输入与原题环境
原题要求生成单个 React JSX 组件，提供四个指标数值；无预置项目，但渲染 JSX 需要 React 宿主。

## 本包的处理
统一版改为可独立渲染的 HTML 页面。新增固定趋势数据和时间范围；可选 React 空项目另附，需与 HTML 赛道分开比较。

`prompt.en.txt` / `prompt.zh.txt` 是本包独立撰写的完整测试版，不是原文全文转载。
`short.en.txt` / `short.zh.txt` 是本包的一句版本，要求范围小于完整版本。
完整公开原题请通过上方来源链接查看；本目录不冒充原始项目或原文备份。

## 预置文件
assets/metrics.json

本包新增的数据、文案和 SVG 输入素材均标为新增内容；它们不是原作者使用过的素材。
`starter` 是空白运行模板，没有题目答案、设计稿或已实现的交互。

## 验收观察
- 四个当前指标符合输入
- 折线使用实际给定数组
- 流失率下降呈改善方向
- 时期切换及变化单位正确
