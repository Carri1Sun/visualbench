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

所有请求均为**同源相对路径**，不硬编码主机或端口：

| 用途 | 请求 |
|---|---|
| 任务与模型目录 | `GET /api/catalog` |
| 全部运行状态索引（10s 轮询） | `GET /api/index` |
| 轨迹下载索引 | `GET /api/trajectories` |
| 输入完整性审计 | `GET /api/audits` |
| 截图 / 视频 / 源码 / 方案 / 产物预览 / 轨迹文件 | `GET /results/runs/...`（路径来自 `/api/index` 各 `*_path` 字段） |
| 冻结输入文件 | `GET /inputs/...` |

- `src/lib/data.js` 的 `artifactUrl()` 是产物 URL 的唯一出口，只放行 `/results/` 前缀的安全相对路径。
- 源码面板只以文本展示 `code_path`，从不执行模型代码。

## 本地开发

```sh
npm install
npm run dev        # http://127.0.0.1:4173，需 result_background 已在 4174 运行
```

`vite.config.js` 将 `/api`、`/results`、`/inputs` 代理到 `http://127.0.0.1:4174`。

## 构建与部署

```sh
npm run build      # 产物输出到 dist/
```

`dist/` 是纯静态文件，可托管在任意静态服务器；数据请求由 nginx/Caddy 反代到 `result_background`，或直接使用 `result_background` 的单机模式（它本身会服务 `dist/`）。

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
