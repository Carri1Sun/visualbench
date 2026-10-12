# 单题执行约定

你在独立的 Remotion + React + TypeScript 项目内完成一道视频评测题。阅读下方任务及 TASK.json，替换 src/Root.tsx 的占位内容。Composition id 保持 Main，尺寸、帧率、时长以 case.config.json 为准。

## 输入与环境

- 题目素材在 public/input/，使用 staticFile('input/<相对路径>') 读取。公共字体在 public/fonts/。题内文件清单的路径相对于 public/input/。
- 默认固定输入测试：不浏览原作者成片和答案，不调用额外图像/视频生成服务，不下载替代创意素材。新增 UI、矢量图形和 3D 几何可用代码完成。依赖安装和文档查询由评测器统一决定是否开放。
- 已固定一致的 Remotion 版本，先 npm ci，不要为开始任务而升级依赖或替换锁文件。只有评测器统一开放时才新增必要依赖，并在 implementation.md 中记录。
- 不更改原始数据、截图、音频、视频和参考 HTML；可以派生工作文件，但保留原始输入。
- 动画由帧号决定，可随意定位和重复渲染。可使用固定种子的随机数，不使用墙钟时间或无种子随机变化。
- 公共字体仅供使用，不限定设计风格，也可以用代码绘制字形。渲染阶段素材全部使用本地路径。
- 未提供或要求旁白时允许无声。不编造产品指标、销量事实或人物背书；虚构测试数据保持虚构属性。
- 自行决定一般创意细节，输入已足够开始，不需要追问评测者创意方向。

## 执行与交付

1. 写 design-plan.md，给出简短视觉方案和时间分镜表，然后继续执行，无需等待审批。
2. 完成代码，保存可编辑源文件。
3. 类型检查、完整视频渲染、全时间轴和关键帧检查；在本次运行预算内修复问题。
4. 交付 out/video.mp4（H.264）、out/poster.png、out/frames/ 下至少六张等间隔关键帧，以及 design-plan.md、implementation.md。实现说明记录实际检查结果和未解决问题。
5. alpha_required 题另交付含 alpha 的 ProRes 4444 out/overlay.mov；video.mp4 用于合成预览。实现背景开关，透明母版不能含不透明背景，并在深浅底色上检查。
6. 无论是否成功都保留真实产物和日志，不把起始占位、参考截图或原作者视频当作已完成结果。

常用命令：npm run typecheck、npm run studio、npm run render、npm run render:alpha、npm run still。海报和关键帧可通过 Remotion CLI 指定帧号。起始项目只含基础设施，不包含题目动画答案。
