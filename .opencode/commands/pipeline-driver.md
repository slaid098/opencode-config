---
description: Run pipeline-driver — autonomous 7-phase PR pipeline
agent: build
---
Load the `pipeline-driver` skill via `skill({name: "pipeline-driver"})` and follow its ПРОТОКОЛ strictly. Each iteration: call `pipeline_status` tool, execute the `NEXT:` action it returns, repeat until COMPLETE or STOP. Полностью автономно — 1 строка прогресса после каждой фазы, STOP на AMBIGUOUS/error.