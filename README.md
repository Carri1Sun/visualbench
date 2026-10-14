# visualbench

分数和通过率并不能让大部分人了解一个模型或 agent 的能力具体如何。visualbench 旨在直接呈现每次运行的**真实画面、视频、公开设计方案、源码与 Pi trajectory**，帮助人们更好地理解模型能力。所有运行位置均保留，不设置评分或审美排行榜。

本轮已配置 40 道题、5 个模型、各 3 次独立运行，共 600 个位置。

## 模块架构

项目拆分为三个互相解耦的模块，加上共享的数据目录：

```
visualbench/
├── result_display_frontend/   # 展示站（React + Vite SPA）
├── result_background/         # 展示数据 API + 独立本地资源服务
├── run_control/               # 运行控制（评测队列、渲染、采集、导出，仅本机）
├── data/                      # 索引层：catalog / trajectories / audits（生成物，不入库）
├── results/                   # results/index.json 实时状态索引（生成物，不入库）
├── runs/                      # 全部运行产物，约 49GB（生成物，不入库）
├── video-bench-inputs-v1/     # 视频赛道冻结输入数据集
└── frontend-showcase-inputs-v1/  # 前端赛道冻结输入数据集
```

## 展示访问链路

```text
浏览器 → 展示前端 :4173
       → /api/* → 数据服务 :4174 → data/ 与 results/index.json
       → 配置后的资源地址 :4180 → runs/ 与冻结输入题包
```

- `server.py` 提供 JSON API 和可选的构建后前端；`resource_server.py` 独立提供资源文件。
- `/api/config` 返回 `resource_base_url`，默认 `http://127.0.0.1:4180`。前端统一解析 `/results/...` 和 `/inputs/...` 逻辑路径，无需改写评测记录。
- 浏览器直接跨域读取资源；Vite 只代理 `/api`，可以在本地测试未来对象存储与 CDN 的访问链路。
- 文件服务支持视频 Range、跨域文本读取、预览 CSP、下载 attachment、ETag 与短时缓存。
- 展示服务对数据只读。评测运行、采集、导出和审计仍由本地 `run_control` 管理。

## 本地启动

```sh
npm --prefix result_display_frontend install
npm run dev                # 只启动前端 :4173、API :4174、资源 :4180
```

访问 [http://127.0.0.1:4173](http://127.0.0.1:4173)。Ctrl+C 停止展示服务。若已有旧服务占用端口，先停止旧的展示进程。

```sh
npm run build              # 构建前端
npm run serve              # 单独启动 API，兼容服务构建后前端
npm run serve:resources    # 单独启动资源服务
npm run test:display       # 前端与 HTTP 集成测试
```

资源地址在 API 启动时配置，前端下次同步生效：

```sh
python3 result_background/server.py --resource-base-url http://127.0.0.1:4280
python3 result_background/resource_server.py --port 4280
```

也支持 `VISUALBENCH_RESOURCE_BASE_URL`；前端 `VITE_RESOURCE_BASE_URL` 可以在 Vite 启动或构建时覆盖配置。完整选项见 [展示服务文档](result_background/README.md)。

本地执行评测的命令继续保留：

```sh
npm run bench:setup        # 安装冻结运行时
npm run bench:start        # 启动或恢复本地队列及采集/归档，需要 Pi 登录
npm run bench:status
npm run bench:export
```

## 后续云端接入

云端只展示本地生成并发布的内容。对象存储保存公开产物，CDN 分发资源，数据接口返回元数据与资源地址。当前实现已拆分 API 与资源服务，并提供本地 HTTP 模拟；对象存储上传、版本化发布和 CDN 配置后续接入。

## 安全边界

- 原始 Pi 会话（`private/`）、`.pi/`、`.git/`、node_modules、`*.log` 一律 403；非 trajectory 的 `*.jsonl` 一律 403。
- 路径穿越与 symlink 的 run 根目录被拒绝；模型产物 HTML 以 iframe sandbox + CSP 隔离展示。
- `run_control` 调用的 pi 子进程带严格沙箱参数（`--offline --no-extensions --no-skills`、工具白名单、45 分钟预算、进程组隔离），POLICY 明确禁止读取环境变量、认证信息与用户文件。本机 `~/.pi` 凭据只被 pi 进程自己使用，不进入仓库、不进入 `runs/`、不被后台提供下载。

## 各模块文档

- [result_display_frontend/README.md](result_display_frontend/README.md)
- [result_background/README.md](result_background/README.md)
- [run_control/README.md](run_control/README.md)
- 评测协议：[run_control/BENCH_PROTOCOL.zh-CN.md](run_control/BENCH_PROTOCOL.zh-CN.md)
