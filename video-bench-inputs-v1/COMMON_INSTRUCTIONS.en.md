# Execution contract

You are implementing ONE video benchmark case in an isolated Remotion + React + TypeScript project. Read the task below and TASK.json. Replace the placeholder composition in src/Root.tsx. Use composition id Main and preserve the dimensions, fps and duration from case.config.json.

## Inputs and environment

- Task assets are under public/input/. Load them with staticFile('input/<relative-path>'). Fonts are under public/fonts/. The task's file inventory uses paths relative to public/input/.
- This is the fixed-input baseline: do not browse source showcases, obtain other people's solutions, call image/video generation services, or download replacement creative assets. Generate additional vector graphics, UI or 3D geometry with your own code. Package installation/documentation access is allowed if the evaluation runner permits it equally for all models.
- The project pins Remotion packages to one matching version. Do not upgrade packages or replace the lockfile merely to begin. Run npm ci. Adding a genuinely necessary dependency is allowed only when the runner has enabled that policy; record it in implementation.md.
- Do not change supplied data, screenshots, audio, source footage or reference HTML. Copying/deriving working assets is allowed; retain originals.
- Use frame-derived animation that supports seeking and deterministic rendering. A seeded random function is allowed. Avoid wall-clock animation, unseeded randomness and playback-state-dependent output.
- Supplied fonts are available, not a mandated aesthetic. Custom code-drawn letterforms are allowed. Keep runtime asset loading local.
- Unless narration is supplied or expressly required, a silent video is allowed. Do not invent unsupported product statistics, sales facts or endorsements. Fictional fixture values remain fictional.
- Resolve routine creative decisions yourself. The task is complete enough to execute without asking the evaluator for creative direction.

## Work and deliverables

1. Write design-plan.md: a concise visual concept plus a scene/time table. This is a deliverable, not a pause for approval.
2. Implement the case and save all editable source.
3. Run type checking, render the full video, and inspect both the complete timeline and representative frames. Fix failures within the same run's allowed budget.
4. Deliver out/video.mp4 (H.264), out/poster.png, at least six evenly spaced frames under out/frames/, design-plan.md and implementation.md. Include factual test outcomes and any remaining failure in implementation.md.
5. For alpha_required cases, also deliver out/overlay.mov using ProRes 4444 with alpha. video.mp4 is a composited preview. Supply a background/preview switch so the alpha master has no opaque background. Test the overlay over light and dark backgrounds.
6. Preserve the actual artifact and logs even if incomplete. Do not present a starter placeholder, a reference screenshot or another creator's video as your completed result.

Useful commands: npm run typecheck; npm run studio; npm run render; npm run render:alpha; npm run still. The poster and frame commands accept frame overrides through the Remotion CLI. The starter is infrastructure only and intentionally contains no animation solution.
