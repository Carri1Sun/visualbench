# 07 布料覆盖球体

Source: https://goldiebench.com/tasks/cloth

## 公开输入与原题环境
公开页面给出一句布料模拟任务并称输出单 HTML；在 Agent Operating System 内运行，完整隐藏系统提示未公开。没有要求用户提供布料图片。

## 本包的处理
使用本包统一系统说明，并新增可重复初始配置和拖拽、风力操作。不是对原站隐藏运行环境的精确复现。

`prompt.en.txt` / `prompt.zh.txt` 是本包独立撰写的完整测试版，不是原文全文转载。
`short.en.txt` / `short.zh.txt` 是本包的一句版本，要求范围小于完整版本。
`original-short.en.txt` 仅保留公开页面中的简短原题。

## 预置文件
assets/cloth-demo.json

本包新增的数据、文案和 SVG 输入素材均标为新增内容；它们不是原作者使用过的素材。
`starter` 是空白运行模板，没有题目答案、设计稿或已实现的交互。

## 验收观察
- 布料实际变形并形成褶皱
- 不明显穿透球体
- 拖拽和风力改变布料状态
- 重置一致，数值稳定
