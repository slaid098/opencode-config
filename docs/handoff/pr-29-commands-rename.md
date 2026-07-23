# PR #29: Commands rename /run-pipeline + /spec

## Что сделано
- Rename: /pipeline-driver → /run-pipeline (command + skill dir + skill() ref)
- Rename: /spec-driver → /spec (command + skill dir + skill() ref)
- Updated cross-references in .opencode/ .md files
- pipeline_status / spec_status tool names NOT changed (independent)

## Почему
Commands should be verbs (imperative), not nouns. /run-pipeline, /spec — clearer user actions.

## Pending
- AGENTS.md references to /pipeline-driver — обновляется в #10 (orchestrator AGENTS.md)
- pipeline-driver skill content rewrite — в #16

## Watch out
- Tool names (pipeline_status, spec_status) unchanged — independent of command names
- Cross-references updated in .opencode/ .md files