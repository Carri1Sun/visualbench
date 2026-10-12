# visualbench

[English](README.md) | [简体中文](README.zh-CN.md)

分数和通过率并不能让大部分人了解一个模型或者 agent 的能力具体如何，visualbench 是一个旨在解决此问题的项目，它目标在于帮助人们更好的了解模型能力。

展示站直接呈现每次运行的画面、视频、公开设计方案、代码和 Pi trajectory。所有运行位置均保留，不设置评分或审美排行榜。

## 本地启动

本轮已配置 40 道题、5 个模型、各 3 次独立运行，共 600 个位置。真实进度来自 `results/index.json`。

```sh
npm --prefix app install
npm run bench:setup
npm run dev
```

访问 [本地展示站](http://127.0.0.1:4173)。`npm run dev` 启动页面、数据服务、采集服务和归档服务，会检查已有 PID，避免重复启动。启动或恢复批量模型队列使用 `npm run bench:start`，需已有可用的 Pi Provider 登录；本轮已授权的队列正在独立运行。

```sh
npm run bench:status    # 查看真实队列和服务状态
npm run build           # 构建展示页
npm run bench:export    # 导出已结束的 Pi 会话
```

只浏览已有结果时，在一个终端运行 `python3 bench/server.py`，另一个终端运行 `npm --prefix app run dev`，不启动模型队列。

## 页面与数据

- 首页提供进度 dashboard、搜索和前端/视频作品浏览。
- 题目页以模型为行、三次运行为列，保留失败与未开始的位置。
- 结果详情展示截图、录屏/视频、源码、公开方案、请求与技术观测，可进入隔离的交互预览。
- 对比页支持并排比较、隐藏模型名以及视频同步操作。
- 每次运行可下载原生 Pi JSONL 轨迹和本地可打开的 HTML 轨迹浏览版。多个会话会逐项列出。
- 人工失败标记与自由备注保存在当前浏览器，并可导出 JSON；它们与生成、构建、渲染状态独立记录。失败占用该次运行，所有结果继续展示。

目录：

```text
app/                      展示站源码
bench/                    执行、渲染、采集和轨迹导出工具
data/catalog.json         40题、5模型及本轮协议
data/trajectories.json    逐run的轨迹下载索引
data/audits.json          输入完整性等补充审计
results/index.json        600个位置的实时状态
runs/<track>/<model>/<case>/run-N/
  request.json            实际模型请求与输入哈希
  run.json                单次真实状态和产物路径
  work/                   模型独立项目与实际媒体
  trajectory/             Pi JSONL与离线HTML导出
  private/                原始模型日志及session，不经HTTP公开
.runtime/                 依赖缓存、PID、服务日志
```

大体积实际结果与本地日志不提交 Git；题库、应用和执行工具留在项目中。展示数据通过服务实时读取，构建前端不会固化或伪造结果。

## 公允与复核

完整实验条件见 [执行协议](BENCH_PROTOCOL.zh-CN.md)，媒体采集实现见 [渲染协议](bench/RENDERING.md)。原题包保持不变；模型运行只接收 prepare 脚本产生的独立题目，来源链接仅供观众溯源。

本轮统一中文 full prompt，初始思考档位为 `max`。2026-10-03 按用户要求，Astra 与 Sol 尚未启动的实验改为 `high`，已有和正在执行的 max 样本原样保留；逐次档位和切换边界公开展示。各 Provider 的能力差异、45分钟生成预算、工具权限、输入哈希、实际使用量和修复/恢复记录均公开。前端手机截图覆盖产品页面的响应式表现；后续的同题多档指导强度应建立独立实验组。

截图和媒体可播放只说明相应技术产物已生成。任务语义、完整交互和视觉偏好需观众实际检查。页面不把这些观测换算为审美分数。
