# 结果渲染与采集

```sh
python3 bench/server.py --port 4175
python3 bench/render.py runs/frontend/MODEL/CASE/run-1/work --track frontend --case-id CASE
python3 bench/render.py runs/video/MODEL/CASE/run-1/work --track video --case-id CASE
```

`render.py` 的最后一行 stdout 是结果 JSON，工作目录内另存 `render-result.json`。
对外状态为 `succeeded`、`render_failed` 或 `generation_failed`，详细渲染过程状态保存在 `render_outcome`。
`succeeded` 表示媒体采集完成，且没有明确的生成失败退出码；缺失文档、运行时异常或格式问题仍会明确出现在 `technical_checks` 中。
每次采集结束读取上级 `run.json` 的 `generation_exit_code`。明确非 0 时，该次运行保留 `generation_failed` 终态，仍展示已得到的媒体与技术检查；超时也计入这一次结果。
独立字段 `generation_status` 为 `succeeded`、`failed` 或 `unknown`。退出码为 `null` 或缺失时使用 `unknown`，不据此推断生成失败。生成与渲染同时失败时，另用 `render_error` 保留原渲染错误。
所有单数 `*_path` 相对工作目录；`frame_paths` 内的图片使用 `/results/runs/...` 公共路径。
`keyframes_path` 指向帧编号、时间和图片地址清单。模型源码保持原样。

## 前端

- 通过 Ego Browser 的同一个 TaskSpace 采集；状态文件为 `bench/browser-space.json`，用 `bench/browser.lock` 串行访问。
- 浏览器采集专用 origin 为 `http://capture.localhost:4175`。本机浏览器将此域解析到回环地址。
- 每次运行先清理这个专用 origin 的数据，在文档执行前清理 sessionStorage，并禁用该页 HTTP 缓存。
- 桌面视口固定 1280×800，加载完成后约 2 秒截图，原生时钟录制 8 秒。产品题 16–20 另采集 390×844 截图。
- 用 CDP 帧时间戳编码成 30 fps MP4；静态画面按实际时间停留。保存真实帧数与时间记录，成功编码后删除临时 JPEG。
- 不注入统一随机种子或虚拟时钟。采集期间没有输入交互；逐题 `interaction_actions` 明确标为 `not_performed`。
- 控制台日志、运行时异常和 DOM 基础信息独立记录。浏览器控制权丢失时保留错误，标记需要用户操作，不创建替代空间。

默认目录包含 `capture/poster.png`、`capture/preview.mp4`、`capture/console.json`、`capture/source.txt`；产品题增加 `capture/mobile.png`。

## 视频

- 复用固定 Remotion 依赖与预装浏览器；渲染显式传入共享浏览器路径，无需逐次下载。
- 用 `.runtime/remotion/render.lock` 控制全局串行渲染，每个渲染最多 2 个并发 worker。
- 已有视频先做 ffprobe 技术检查，符合配置时直接复用。已有错误视频保留，补渲染另存 `capture/rendered-video.mp4`。
- 渲染完整 `Main` composition，透明题额外生成 ProRes 4444 alpha master；不修改模型源码来纠正设计或配置。
- 从实际视频提取 6 个等距帧和中间帧海报，保存到 `capture/keyframes/` 与 `capture/poster.png`。
- 对采集结果建立临时符号链接视图，调用题包原 `verify_outputs.py`，检查尺寸、帧率、时长、alpha、文档和帧截图数量。
- 详细本地日志保留为 `.log`，可公开的渲染诊断另汇总到 `capture/console.json`。

## 中断与时间预算

默认总预算取 runner 的 `render_timeout_seconds - 30` 秒，包含等待锁、渲染、探测和截图。
也可使用 `--timeout-seconds` 显式指定。每个子进程只获取剩余预算。
收到 SIGTERM/SIGINT 或子进程超时时，终止对应整个进程组，避免遗留 Chromium、ffmpeg 或 Node 渲染进程。
