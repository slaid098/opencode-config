---
description: Run spec — interactive spec generation for new project
agent: build
---
Load the `spec` skill via `skill({name: "spec"})` and follow its ПРОТОКОЛ strictly. Главный агент — оркестратор: `spec_status` tool (read-only) + вопрос юзеру + task(general) делегирование. Не делает edit/memory_search/gh сам. Каждая фаза = 1 subagent. Стоп на issues — дальше юзер сам /run-pipeline.