---
description: Run spec-driver — interactive spec generation for new project
agent: build
---
Load the `spec-driver` skill via `skill({name: "spec-driver"})` and follow its ПРОТОКОЛ strictly. Главный агент — оркестратор: `spec_status` tool (read-only) + вопрос юзеру + task(general) делегирование. Не делает edit/memory_search/gh сам. Каждая фаза = 1 subagent. Стоп на issues — дальше юзер сам /pipeline-driver.