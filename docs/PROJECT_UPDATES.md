# Project Updates

## 2026-05-13 Revision Log

- Restored the missing `/api/plc/engine/config` request model so OpenAPI generation succeeds.
- Created data directories before mounting static files to avoid startup failures on a clean workspace.
- Adjusted PLC output batching to merge only truly contiguous output addresses, preventing sparse mappings from writing unintended PLC addresses.
- Restored runtime image storage settings on startup and ensured PLC/runtime config edits trigger auto-save.
- Fixed `npm run build` in restricted/sandboxed environments by adding a local Vite API build entry.
- Reworked presets to load from backend `presets/*.json`, with list/read/load endpoints and replace-on-load semantics.
- Added VisFlowZ-compatible low-coupling capabilities: GPU info, config import/export, raw model upload, record statistics, and record deletion.
- Added a generic communication device layer and UI for TCP client/server and serial device definitions, including connect/disconnect/send operations.
- Added VisFlowZ-style event-action mapping: backend mapping API, template generation, dry-run event testing, frontend management page, and preset persistence.
- Added a lightweight VisFlowZ-style rules engine: rule CRUD, enable/disable, condition evaluation, action execution hooks, frontend management page, and preset persistence.
- Fixed device API/UI connection field mismatch and event-action template append behavior.
- Reduced real-time monitoring overhead: hidden tabs skip polling, monitor reads are de-duplicated and capped, polling intervals were relaxed, and overlapping requests are prevented.
- Added Settings config import/export UI and built-in preset loading from backend preset files.
- Added six VModule-native presets that cover the same business workflows as VisFlowZ: Daheng inspection/dataset, Hikvision inspection/dataset, and dual USB inspection/dataset.
- Rewrote the PLC API source file to remove legacy encoding corruption while preserving all route behavior.
- Added regression coverage for OpenAPI compatibility routes, preset replacement, runtime settings restore, device manager lifecycle, and event-action template execution.
- Added a formal handoff document at `docs/HANDOFF_2026-05-13.md`, documenting the real workspace boundary, VisFlowZ-to-VModule workflow mapping, runtime validation evidence for `visflowz-config-vmodule-2026-05-13.json`, key frontend entry points, startup/build/test procedures, and the recommended next implementation order.

## VisFlowZ Feature Gap And Implementation Order

Aligned:

- Backend-loaded presets from `presets/`.
- Config import/export.
- Model weight upload.
- GPU status query.
- Detection record statistics and deletion.
- Generic device abstraction and device management page.
- Event-action mapping, templates, and dry-run testing.
- Rules engine, rules management page, and dry-run evaluation.
- Six VisFlowZ-equivalent business presets expressed in VModule's own preset schema.

Still Pending:

- Authentication, users, and permission controls.
- Standalone pipeline orchestration, external trigger configuration, and quick-start flow.
- WebSocket real-time status/frame/result push.
- Richer history with defect type, confidence, and trend charts.
- Camera multi-exposure, ROI, and trigger mode editor.
- Automatic converter from VisFlowZ project-level preset fields to VModule PLC mapping format.
