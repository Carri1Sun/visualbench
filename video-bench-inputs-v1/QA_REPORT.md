# Input pack validation

Validated on 2026-10-02 UTC.

## Passed

- Exactly 20 unique cases, numbered to match the video list in the conversation.
- Both English and Chinese prompts plus task.json and SOURCE.md exist for every case.
- All 108 task input files exist, have nonzero content, and match their SHA-256 entries.
- All 11 packaged audio/video files are readable with ffprobe and have positive durations.
- JSON data and SVG/GPX XML parse successfully.
- Task 10 caption text matches the authored narration script after text correction; word timings remain approximate.
- Task 11 provided foreground file contains alpha: sampled background alpha 0 and subject alpha 255; the matte image was visually inspected.
- Representative website, UI and article input screenshots were visually inspected.
- Isolated project preparation was checked for pure-prompt, source-video and 3D-data cases (01, 11, 18). Prepared projects contain the expected files and dependency lock, without source showcase URLs in TASK.json.
- Remotion starter dependencies installed successfully; TypeScript typecheck passed.
- Starter rendered 30 frames at one-quarter scale successfully. This validates the blank starter infrastructure, not the 20 task implementations.

## Validation environment notes

Node.js 24.19.0, Remotion 4.0.532, React 19.0.0, TypeScript 5.8.3. The validation sandbox denies network-interface enumeration, so the local rendering test used a temporary harness pointing the renderer server to loopback. This harness is not in the distributed starter. Standard local Node environments normally enumerate their own interfaces.

## Scope

This archive provides inputs and a blank project. The 20 completed benchmark videos have not been generated or scored. A successful package check does not imply any particular model will complete a task. Editorial/visual quality, semantics, full-sequence synchronization and transparent master quality must be assessed on the actual generated outputs.

Original source prompts are rewritten and missing private assets are replaced transparently. No claim is made that the bundle is a byte-for-byte copy of any original creator project. Input-specific differences are listed in each SOURCE.md.
