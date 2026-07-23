---
description: Edit opencode.json config (MCP, providers, permissions, agents)
agent: build
---
Load the `configure-opencode` skill via `skill({name: "configure-opencode"})` and apply its canonical rules to the user's request about opencode.json changes (MCP servers, providers, permissions, agents, plugins). Follow the skill's rules strictly: always write to `.opencode/opencode.json` in slaid098/opencode-config repo (project-local, auto-discovered), never project-local in other repos.