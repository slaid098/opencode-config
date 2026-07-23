# ADR-009: Commands rename to verbs

## Статус
Accepted

## Контекст
Commands /pipeline-driver and /spec-driver — nouns, should be verbs (imperative). /opencode-config → /configure-opencode done in #12.

## Решение
- /pipeline-driver → /run-pipeline
- /spec-driver → /spec
- Cross-references updated
- Tool names unchanged (independent)

## Альтернативы
- Keep noun names — отклонено (commands should be verbs per convention)
- Rename tools too — отклонено (tools independent, renaming breaks pipeline_status oracle)