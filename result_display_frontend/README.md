# result_display_frontend

visualbench 展示站前端：React 19 + Vite 6 单页应用，只消费 `result_background` 提供的接口，自身无状态、无后端逻辑。

## 职责

- 首页进度 dashboard、搜索、前端/视频作品浏览
- 题目页以模型为行、三次运行为列，保留失败与未开始的位置
- 结果详情：截图、录屏/视频、源码、公开方案、请求与技术观测、隔离交互预览（iframe sandbox + CSP）
- 对比页：并排比较、隐藏模型名、视频同步操作
- 轨迹下载入口（原生 Pi JSONL 与本地可打开的 HTML 浏览版）
- 人工失败标记与自由备注保存在当前浏览器，可导出 JSON

## 与后台的接口约定

API 使用同源 `/api/*`；资源通过 `/api/config` 中的 `resource_base_url` 解析后直接访问独立资源服务：

| 用途 | 请求 |
|---|---|
| 任务与模型目录 | `GET /api/catalog` |
| 全部运行状态索引（10s 轮询） | `GET /api/index` |
| 轨迹下载索引 | `GET /api/trajectories` |
| 输入完整性审计 | `GET /api/audits` |
| 截图 / 视频 / 源码 / 方案 / 产物预览 / 轨迹文件 | `GET /results/runs/...`（路径来自 `/api/index` 各 `*_path` 字段） |
| 冻结输入文件 | `GET /inputs/...` |

- `src/lib/resources.js` 统一解析资源与下载地址，只接受 `/results/`、`/inputs/` 逻辑路径和当前配置下的完整地址。
- 默认从 API 配置读取资源地址；可用 `VITE_RESOURCE_BASE_URL` 在启动 Vite 或构建时覆盖。
- 下载链接使用 `?download=1`，由资源服务提供 attachment 响应。
- 源码面板只以文本展示 `code_path`，从不执行模型代码。

## 本地开发

```sh
npm install
npm run dev        # http://127.0.0.1:4173，需 result_background 已在 4174 运行
```

`vite.config.js` 只将 `/api` 代理到 `http://127.0.0.1:4174`。默认资源直接访问 `http://127.0.0.1:4180`。在项目根目录运行 `npm run dev` 可启动完整展示服务。

## 构建与部署

```sh
npm run build      # 产物输出到 dist/
```

`dist/` 是纯静态文件。数据请求由 `/api` 提供，资源地址由运行时配置决定。`result_background/server.py` 也可以服务构建后的前端；资源仍由独立服务提供。

## 目录结构

```
src/
├── App.jsx                 # 路由与页面骨架
├── components/             # Dashboard / Gallery / TaskPage / ResultDialog / Comparison / ...
├── hooks/
│   ├── useLiveData.js      # /api/* 轮询与状态合并
│   ├── useRoute.js         # hash 路由
│   └── useTextFile.js      # 文本文件读取
├── lib/
│   ├── data.js             # 目录构建、过滤、路径安全（artifactUrl/resultPath）
│   └── navigation.js
└── styles/app.css
```
