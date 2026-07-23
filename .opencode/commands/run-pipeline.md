---
description: Run pipeline — autonomous 7-phase PR pipeline
agent: build
---
Load the `run-pipeline` skill via `skill({name: "run-pipeline"})` and follow its ПРОТОКОЛ strictly. Each iteration: call `pipeline_status` tool, execute the `NEXT:` action it returns, repeat until COMPLETE or STOP. Полностью автономно — 1 строка прогресса после каждой фазы, STOP на AMBIGUOUS/error.