---
description: Edit opencode.json config (MCP, providers, permissions, agents)
agent: build
---
Load the `opencode-config` skill via `skill({name: "opencode-config"})` and apply its canonical rules to the user's request about opencode.json changes (MCP servers, providers, permissions, agents, plugins). Follow the skill's rules strictly: always write to `config/opencode.json` in slaid098/opencode repo, never project-local.