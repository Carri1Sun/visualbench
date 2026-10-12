# result_background

visualbench 后台数据服务：为 `result_display_frontend` 提供只读的 JSON 接口与运行产物文件服务。标准库实现（`http.server`），零依赖，单进程。

## 启动

```sh
python3 result_background/server.py --port 4174            # 默认绑定 127.0.0.1
python3 result_background/server.py --host 0.0.0.0 --port 4174
```

本模块**自包含**：不 import `run_control`，不需要 pi，除仓库内数据目录外没有任何外部依赖。服务器部署只需本目录 + 数据文件 + 前端 `dist/`。

## API

### JSON 接口（`/api/*`，一律 `Cache-Control: no-store`）

| 路由 | 数据源 | 内容 |
|---|---|---|
| `GET /api/health` | — | 存活检查 `{ok, service, time}` |
| `GET /api/catalog` | `data/catalog.json` | 题目、模型、输入与本轮协议 |
| `GET /api/index` | `results/index.json` | 全部 600 个运行位的状态与产物路径 |
| `GET /api/trajectories` | `data/trajectories.json` | 逐 run 轨迹下载索引 |
| `GET /api/audits` | `data/audits.json` | 输入完整性等补充审计 |
| `GET /api/execution-changes` | `data/execution-changes.json` | 协议中途变更记录 |
| `GET /api/environment` | `data/environment.json` | 采集环境信息 |

### 文件服务

| 前缀 | 数据源 | 说明 |
|---|---|---|
| `/results/runs/...` | `runs/` | 运行产物（截图、视频、artifact.html、方案、源码、轨迹）。支持 `Range`（视频拖动）；`.jsonl` 以 `attachment` 提供下载；artifact HTML 附带隔离 CSP |
| `/inputs/...` | 两个 `*-inputs-v1` 数据集 | 冻结输入文件 |
| `/*` | `result_display_frontend/dist/` | 构建后的 SPA（单机部署模式，SPA 路由回退到 `index.html`） |

## 安全规则

后台服务的内容包含不可信的模型产物，内置多层防护：

- **永不提供原始 Pi 会话**：路径中含 `private`、`.pi`、`.git`、`node_modules` 一律 403
- `*.log` 一律 403；`*.jsonl` 仅在 `trajectory` 目录内可访问
- `/results/runs/` 要求至少 `track/model/case/run-N` 五级路径，且任一级为 symlink 即 403（防 symlink 逃逸）
- 全局拒绝 `..`、URL 编码穿越与 NUL 字节
- 响应带 `X-Content-Type-Options: nosniff`；trajectory 之外的 HTML 产物附带严格 CSP
- 对全部磁盘数据只读，不生成、不修改任何文件

## 与其他模块的关系

- 数据生产方是 `run_control`（本机运行，写入 `runs/`、`results/`、`data/`）
- 数据消费方是 `result_display_frontend`（同源相对路径请求）
- 本服务与 `run_control` 无代码依赖；部署到服务器时不需要 `run_control`，也不需要任何 pi 登录态或 API 凭据

## 部署建议

- systemd 守护、绑定 `127.0.0.1`，由 nginx/Caddy 反代对外提供 HTTPS
- `/api/*` 保持 no-store（索引随队列实时更新）；`/results/runs/` 与 `/inputs/` 内容不可变，可在反代层加长缓存
- 服务器上只需同步：本目录、`data/`、`results/index.json`、`runs/` 中被索引引用的产物子集（约 21GB）、输入数据集与前端 `dist/`
