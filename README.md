# visualbench

分数和通过率并不能让大部分人了解一个模型或 agent 的能力具体如何。visualbench 旨在直接呈现每次运行的**真实画面、视频、公开设计方案、源码与 Pi trajectory**，帮助人们更好地理解模型能力。所有运行位置均保留，不设置评分或审美排行榜。

本轮已配置 40 道题、5 个模型、各 3 次独立运行，共 600 个位置。

## 模块架构

项目拆分为三个互相解耦的模块，加上共享的数据目录：

```
visualbench/
├── result_display_frontend/   # 展示站（React + Vite SPA）
├── result_background/         # 后台数据服务（JSON API + 产物文件）
├── run_control/               # 运行控制（评测队列、渲染、采集、导出，仅本机）
├── data/                      # 索引层：catalog / trajectories / audits（生成物，不入库）
├── results/                   # results/index.json 实时状态索引（生成物，不入库）
├── runs/                      # 全部运行产物，约 49GB（生成物，不入库）
├── video-bench-inputs-v1/     # 视频赛道冻结输入数据集
└── frontend-showcase-inputs-v1/  # 前端赛道冻结输入数据集
```

## 数据流转

```
┌─────────────────────────── 本机（不出服务器） ───────────────────────────┐
│                                                                          │
│  run_control                                                              │
│  runner.py ──spawn──▶ pi CLI（受限沙箱参数，凭据仅存于 ~/.pi，不落盘）      │
│      │                    │                                               │
│      │ 采集/渲染           │ 会话事件                                      │
│      ▼                    ▼                                               │
│  render.py / capture   private/（原始会话，server 永久 403）               │
│      │                                                                   │
│      ├──▶ runs/<track>/<model>/<case>/run-N/                             │
│      │      run.json / request.json / execution.json                     │
│      │      work/{artifact.html, out/video.mp4, capture/poster.png, ...}  │
│      │      trajectory/{session-N.jsonl, session-N.html}                 │
│      │                                                                    │
│      └──▶ results/index.json、data/{catalog,trajectories,audits}.json     │
│                                                  │                        │
└──────────────────────────────────────────────────┼────────────────────────┘
                                                   │ 只读
                                                   ▼
                                     ┌───────────────────────┐
                                     │   result_background    │
                                     │   server.py :4174      │
                                     │   /api/*    JSON 接口   │
                                     │   /results  产物文件    │
                                     │   /inputs   冻结输入    │
                                     └───────────┬───────────┘
                                                 │ HTTP（同源相对路径）
                                                 ▼
                                     ┌───────────────────────┐
                                     │ result_display_frontend│
                                     │ SPA（dev: vite proxy;  │
                                     │ prod: nginx 反代或同端口）│
                                     └───────────────────────┘
```

关键约定：

- 前端**只**通过 `/api/*`（小 JSON）和 `/results/*`、`/inputs/*`（文件）三类同源相对路径与后台沟通，不硬编码任何主机端口。
- `run.json` 中的 `*_path` 字段直接以 `/results/runs/...` 形式存储公开产物路径，后台原样提供文件服务。
- `run_control` 是唯一写入方；`result_background` 对全部数据只读。
- 后台与运行控制无代码依赖：**服务器部署不需要 run_control，也不需要本机 pi 登录态**，凭据不会随任何同步文件离开本机。

## 本地启动

```sh
npm --prefix result_display_frontend install
npm run bench:setup        # 首次：安装冻结运行时并预热工作区
npm run dev                # 启动展示页、数据服务、采集与归档服务（不含模型队列）
```

访问 [http://127.0.0.1:4173](http://127.0.0.1:4173)。启动或恢复批量模型队列使用 `npm run bench:start`（需已有可用的 Pi Provider 登录）。

```sh
npm run bench:status       # 查看队列与服务状态
npm run build              # 构建展示页到 result_display_frontend/dist
npm run bench:export       # 导出已结束的 Pi 会话
npm run serve              # 只启动后台服务（:4174，同时服务构建产物）
```

## 服务器部署

展示面 = `result_display_frontend/dist` + `result_background` + 索引层 + 产物子集，约 21GB（引用产物 1.64GB + 轨迹导出 19GB）：

1. 同步 `result_display_frontend/`、`result_background/`、`data/`、`results/index.json`、`runs/` 中被索引引用的产物、两个输入数据集；
2. `npm --prefix result_display_frontend run build`；
3. 服务器上运行 `python3 result_background/server.py --port 4174`（systemd 守护，绑定 127.0.0.1）；
4. nginx/Caddy 反代 443 → 4174，对 `/results/runs/` 可加长缓存，`/api/*` 保持 no-store。

后台自身也能直接服务 `dist` 静态文件（单机模式），因此最简部署只需一个进程 + 一个反代。

## 安全边界

- 原始 Pi 会话（`private/`）、`.pi/`、`.git/`、node_modules、`*.log` 一律 403；非 trajectory 的 `*.jsonl` 一律 403。
- 路径穿越与 symlink 的 run 根目录被拒绝；模型产物 HTML 以 iframe sandbox + CSP 隔离展示。
- `run_control` 调用的 pi 子进程带严格沙箱参数（`--offline --no-extensions --no-skills`、工具白名单、45 分钟预算、进程组隔离），POLICY 明确禁止读取环境变量、认证信息与用户文件。本机 `~/.pi` 凭据只被 pi 进程自己使用，不进入仓库、不进入 `runs/`、不被后台提供下载。

## 各模块文档

- [result_display_frontend/README.md](result_display_frontend/README.md)
- [result_background/README.md](result_background/README.md)
- [run_control/README.md](run_control/README.md)
- 评测协议：[run_control/BENCH_PROTOCOL.zh-CN.md](run_control/BENCH_PROTOCOL.zh-CN.md)
