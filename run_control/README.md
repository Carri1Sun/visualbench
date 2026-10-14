# run_control

visualbench 运行控制模块：**仅在本机运行**的评测执行系统。负责批量调度模型运行、采集与渲染产物、导出轨迹、维护实时索引。它不对外提供任何网络服务（4174/4175/4180 端口属于 `result_background`）。

## 组成

| 文件 | 职责 |
|---|---|
| `runner.py` | 队列调度核心：按 `config.json` 并发执行每模型 worker、45 分钟墙钟预算（超时 SIGTERM→SIGKILL 进程组）、崩溃后用 `lsof` 找回孤儿 pi 进程、驱动渲染队列、写 `run.json` |
| `render.py` | 采集/渲染：前端赛道用共享 Ego TaskSpace 浏览器捕获（`browser.lock` 互斥）；视频赛道用 Remotion 渲染（`--concurrency=1`） |
| `capture_frontend.mjs` | 浏览器内采集脚本（独立 `capture.localhost` origin，逐 run 清空存储） |
| `export_trajectories.py` | 把已结束的 Pi 会话导出为原生 JSONL + 自包含 HTML 浏览版（`--watch` 常驻） |
| `audit_outputs.py` | 输入完整性与产物审计，写 `data/audits.json`（`--watch` 常驻） |
| `manage.py` | 服务编排：启动/恢复全部本地服务（含 `result_background` 与前端 dev），PID 管理，防重复启动 |
| `setup.py` | 首次安装冻结运行时并预热干净的视频工作区 |
| `common.py` | 共享工具：ROOT/PACKS 定位、原子 JSON 写入、SHA-256、协议元数据 |
| `config.json` | 本轮协议配置：模型清单、思考档位策略、超时、并发 |
| `test_harness.py` | 对外测服务的自测（不改动任何评测源与元数据） |
| `BENCH_PROTOCOL.zh-CN.md` | 评测协议文档 |

## 运行方式

```sh
npm run bench:setup     # 首次：安装 .runtime/remotion 冻结依赖并预热工作区
npm run bench:start     # 启动全部服务 + 模型队列（需本机已有可用的 Pi Provider 登录）
npm run bench:status    # 队列与服务状态（PID 存活、各状态计数）
npm run bench:export    # 手动触发一次轨迹导出
```

目录约定（均为生成物，不入库）：

```
runs/<track>/<model>/<case>/run-N/
├── run.json / request.json / execution.json / source-hashes.json   # 公开元数据
├── work/          # 模型独立工作区（artifact.html、out/video.mp4、capture/...）
├── private/       # 原始 Pi 会话与策略文件 —— result_background 永久 403
└── trajectory/    # 导出的会话副本（可公开下载）
```

## 模型调用与凭据安全

`runner.py` 通过 spawn `pi` CLI 子进程执行每次运行：

```
pi --provider <p> --model <m> --mode json --print
   --offline --no-extensions --no-skills --no-prompt-templates
   --no-context-files --no-themes --tools read,bash,edit,write
   --session-dir runs/.../private/sessions
   --append-system-prompt private/policy.txt
```

- **凭据零接触**：本模块从不读取 `~/.pi`；登录态由 pi 进程自行加载并直接用于调用 provider API，不经过 runner、不写入任何文件
- **沙箱约束**：注入的 POLICY 禁止读取其他运行、用户文件、认证信息、环境变量；禁止联网、安装依赖、后台常驻进程
- **生命周期控制**：独立进程组（`start_new_session`）、45 分钟预算强杀、崩溃恢复时按 stdout 归属识别残留进程
- macOS 下以 `caffeinate` 防止评测期间休眠

## 与其他模块的关系

- 唯一数据写入方：产出 `runs/`、`results/index.json`、`data/*.json`，由 `result_background` 只读提供
- `manage.py` 会同时拉起 `result_background/server.py`（4174 数据、4180 资源、4175 独立捕获 origin）与前端 dev 服务
- **部署到服务器时本模块不需要同步**：远端没有任何组件能触发本机模型运行
