# 展示数据与本地资源服务

本模块提供两个独立的只读 HTTP 服务，不依赖 `run_control`、Pi 或模型凭据。

| 服务 | 默认端口 | 职责 |
|---|---|---|
| `server.py` | 4174 | JSON API、可选的已构建前端 |
| `resource_server.py` | 4180 | 题目素材、截图、视频、源码、HTML 预览、轨迹和文件下载 |

## 本地启动

在项目根目录运行 `npm run dev`，会同时启动前端（4173）、API（4174）和资源服务（4180）。Ctrl+C 停止这一组服务。该命令不启动评测、采集、轨迹导出或审计写入进程。

也可以分别启动：

```sh
npm run serve
npm run serve:resources
npm --prefix result_display_frontend run dev
```

API 只代理 `/api/*`；浏览器直接从 4180 获取文件，保留真实跨域访问，便于测试未来对象存储和 CDN 的资源访问方式。

## 资源地址配置

API 的 `GET /api/config` 返回：

```json
{"resource_base_url":"http://127.0.0.1:4180"}
```

前端先读取配置，将索引中的 `/results/...` 和 `/inputs/...` 逻辑路径解析成完整资源地址。已有索引和评测产物无需改写。配置失败时不首次展示未经配置的资源链接。

启动 API 时可以修改地址，修改后前端下一次同步生效：

```sh
python3 result_background/server.py --resource-base-url http://127.0.0.1:4280
python3 result_background/resource_server.py --port 4280
```

也支持 `VISUALBENCH_RESOURCE_BASE_URL` 环境变量。CLI 参数优先于环境变量。前端的 `VITE_RESOURCE_BASE_URL` 可以覆盖 API 配置，需在启动 Vite 或构建前设置；配置优先级为前端构建变量、API 参数/环境变量、API 默认值。

API 与资源文件可使用不同的本地目录：

```sh
python3 result_background/server.py --root /path/to/metadata
python3 result_background/resource_server.py --root /path/to/public-resources
```

目录分别保留 `data/`、`results/index.json`，以及 `runs/`、`frontend-showcase-inputs-v1/`、`video-bench-inputs-v1/` 的布局。对应环境变量是 `VISUALBENCH_DATA_ROOT` 和 `VISUALBENCH_RESOURCE_ROOT`。默认从仓库目录只读读取，当前阶段不复制、修改或重新渲染真实产物。这个服务模拟对象的 HTTP 读取，不实现 S3 上传、签名或权限 API。

## API

所有 API 使用 `Cache-Control: no-store`。

| 路由 | 数据源 |
|---|---|
| `/api/health` | 服务存活状态 |
| `/api/config` | 资源服务公开地址 |
| `/api/catalog` | `data/catalog.json` |
| `/api/index` | `results/index.json` |
| `/api/trajectories` | `data/trajectories.json` |
| `/api/audits` | `data/audits.json` |
| `/api/execution-changes` | `data/execution-changes.json` |
| `/api/environment` | `data/environment.json` |

4174 默认不返回 `/results/*` 或 `/inputs/*` 文件。`--with-resources` 是给本地 4175 捕获服务保留的显式兼容模式，维持采集所用的原有 HTML CSP。

## 资源 HTTP 行为

- `/results/runs/...` 映射到 `runs/`；`/inputs/frontend/...` 和 `/inputs/video/...` 映射到冻结题包。
- `/health` 返回资源服务状态。无 API、无 SPA 回退、无目录列表。
- `GET`、`HEAD`、`OPTIONS` 支持跨域读取；暴露下载、分段和缓存相关响应头。
- 支持单个 `Range`（指定区间、尾部区间、开放结尾）、`206`、`416` 和 `If-Range`，用于视频拖动。多区间请求回退为完整响应。
- 默认 `Cache-Control: public, max-age=60`，可用 `--cache-seconds` 调整。支持 ETag 与 `If-None-Match` 的 `304`。本地产物可能更新，因此默认不声明 `immutable`。
- `?download=1` 强制 attachment；可附带 `filename`，支持 UTF-8 文件名。预览和下载 URL 分开；JSONL 默认下载。前端统一生成下载地址，避免依赖跨域 `download` 属性。
- 模型 HTML 与轨迹 HTML 都附加 CSP 和 `sandbox allow-scripts`；前端 iframe 同时保留 `sandbox="allow-scripts"`。相对资源按文件 URL 正常解析。
- 拒绝私有目录、隐藏路径、依赖目录、日志、非轨迹 JSONL、路径穿越、重复编码和文件 symlink。服务始终只读。

## 验证

```sh
npm run test:display
npm run build
```

前端测试覆盖资源地址解析、可信地址限制和下载 URL；HTTP 集成测试使用临时目录与真实监听端口，覆盖跨域、分段读取、缓存、预览/下载分离和私有文件拒绝。测试不改写评测记录。

云端对象存储、CDN、上传发布流程在后续阶段接入。本地 HTTP 服务仅用于开发与预览。
