# 生成结果数据约定

输入题库：manifest.json 的 cases 数组。默认结果唯一键为 (case_id, model_id, run_number, variant, language)。同一个条件中的 run_number 为 1–5。

推荐每个 run 目录包含：
- artifact.html：实际模型生成 HTML。
- plan.json：实际模型提交的公开设计方案，schema 见 common/plan.schema.json。
- request.json：实际发送请求；可复用 prepare_case.py 生成的字段。
- RUN-METADATA.json：执行过程中填写实际模型、参数、耗时、状态等。
- screenshot.png：实际浏览器截图；不是输入素材。
- video.webm 或 video.mp4：实际运行录屏，可选。
- after-interaction.png：固定操作之后的截图，可选。
- console.json：浏览器错误记录，可选。
- assets/、vendor/：输入素材与本地运行依赖。

results/index.json 格式如下；这是 schema 示例，model-example 不是已跑模型：
```json
{
  "schema_version": "1.0",
  "runs": [{
    "case_id": "01-pelican-bicycle",
    "model_id": "model-example",
    "run_number": 1,
    "variant": "full",
    "language": "en",
    "mode": "one_completion",
    "status": "not_generated",
    "artifact_path": null,
    "plan_path": null,
    "screenshot_path": null,
    "video_path": null,
    "duration_ms": null,
    "usage": null,
    "repairs": [],
    "error": null
  }]
}
```

状态可为 not_generated、queued、running、succeeded、generation_failed、render_failed。
路径是相对于 results/index.json 的可访问相对路径，不允许导入路径越过结果根目录。
没有实际测到的数据保持 null，不能填估计的 token 或耗时冒充真实值。
usage 若模型提供，可存 input_tokens、output_tokens、reasoning_tokens；字段定义由 provider 决定，需要保留 provider 原始字段记录。
repairs 应说明谁修复、修改内容、是否增加模型调用；修复版与初始版可以同时保留。
render_failed 可以仍然拥有 artifact_path，让用户查看导致失败的代码。
截图、录像和运行结果不能用输入素材或空模板填充。
