# PR #17: Migrate src/ + tests/ + Python tooling

## Что сделано

- Перенесён Python-пакет `second-brain` (RAG CLI): `src/memory/` (6 файлов)
- Перенесены тесты: `tests/` (15 файлов: 13 .py + 1 .mjs + 1 .ts)
- Перенесён Python tooling: `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.python-version`
- `src/memory/embedder.py`: вынесен hardcoded endpoint `ai.slaid098.dev` → env-only (`AI_PROVIDER_API_URL`)
- `pyproject.toml`: rename `slaid098/opencode` → `slaid098/opencode-config` в [project.urls]
- Тесты: mock URLs обновлены `slaid098/opencode` → `slaid098/opencode-config`
- Source: ветка `fix/pipeline-status/review-next-by-verdict` (включает фикс `610452f` + тесты `01212b5`)

## Почему

Миграция из приватного репо `slaid098/opencode` в публичный `slaid098/opencode-config`. Hardcoded приватный API endpoint удалён — env-only для публичного релиза.

## Pending

- `pipeline-status.py` (fix `610452f`) мигрирует через #7 (`.opencode/scripts/`), не через #5
- `pyproject.toml` в корне может триггерить LSP-конфликт на bare-metal Windows — отслеживать

## Watch out

- Issue #5 заявляла "14 tests файлов", по факту 15 (13 .py + .mjs + .ts) — расхождение +1
- `config/scripts/pipeline-status.py` НЕ в scope #5 — он в `config/scripts/` → мигрирует через #7
- `tests/test_pipeline_status.py` содержит тесты для REQUEST_CHANGES/NEEDS_DISCUSSION NEXT (из fix-ветки)
- 10 из 15 тестов падают (FileNotFoundError) — они зависят от `config/scripts/` и `config/tools/` которых нет в репо (мигрируют через #7)
- `tests/test_embedder.py` обновлён: `os.environ.setdefault("AI_PROVIDER_API_URL", "http://test/v1")` перед import — необходим из-за strip hardcoded URL в embedder.py
- `ruff format` реформатнул 2 файла (test_pipeline_status.py, test_spec_status.py) — строки превысили 100 chars после добавления `-config` к URL
