---
name: repo-init
description: Sequential checklist: create GitHub remote → configure settings/branch protection → scaffold project files (Python/JS). Use when starting a new repo. Also when user says "новый репо", "создай репозиторий", "настрой репо".
---

# Repo Init

Полный чек-лист инициализации нового репозитория. Все шаблоны — внутри, берутся из эталонных репозиториев (reference repos).

## Фазы

- **Phase A — GitHub remote** (шаги 1-3, выполняется один раз): создание репо, настройки merge, защита ветки. Требует локального git-репо с initial commit.
- **Phase B — Project scaffolding** (шаги 4-9, по шаблонам): Python/JS файлы, Dependabot, LICENSE, .editorconfig, pre-commit, верификация. Можно повторно использовать для существующего репо (skip Phase A).

## Содержание

1. [Создание репозитория](#1-создание-репозитория)
2. [Настройки репозитория](#2-настройки-репозитория)
3. [Защита ветки main](#3-защита-ветки-main)
4. [Python-проект](#4-python-проект)
5. [JS/TS-проект](#5-jsts-проект)
6. [Dependabot](#6-dependabot)
7. [Общие файлы](#7-общие-файлы)
8. [Установка pre-commit](#8-установка-pre-commit)
9. [Чек-лист верификации](#9-чек-лист-верификации)

---

## Phase A — GitHub remote

> Шаги 1-3 выполняются один раз для нового репо. Требуют локального git-репо с initial commit.

## 0. Prerequisite: git init + initial commit

Перед `gh repo create --source=.` локальный каталог должен быть git-репо с хотя бы одним коммитом (`--source=.` пушит текущую ветку; без коммита — пустой репо).

```bash
git init
echo "# <repo-name>" > README.md
git add README.md
git commit -m "chore: initial commit"
```

Если bare-repo без initial commit — `gh repo create --source=.` создаст remote, но push будет пустым, а main branch не появится → branch protection упадёт.

---

## 1. Создание репозитория

```bash
gh repo create <owner>/<repo-name> --public --source=. --remote=origin --push
```

Или приватный (если internal):

```bash
gh repo create <owner>/<repo-name> --private --source=. --remote=origin --push
```

После создания — настроить git auth:

```bash
gh auth setup-git
```

---

## 2. Настройки репозитория

Squash-only merge, auto-delete branch после merge:

```bash
gh api repos/<owner>/<repo-name> \
  --method PATCH \
  -f allow_squash_merge=true \
  -f allow_merge_commit=false \
  -f allow_rebase_merge=false \
  -f delete_branch_on_merge=true \
  -f squash_merge_commit_title=COMMIT_OR_PR_TITLE \
  -f squash_merge_commit_message=COMMIT_MESSAGES
```

---

## 3. Защита ветки main

Требовать PR, требовать status checks (CI), linear history:

```bash
gh api repos/<owner>/<repo-name>/rules/branches/main \
  --method POST \
  -F target=branch \
  -f enforcement=active \
  --input - <<'EOF'
{
  "conditions": {
    "ref_name": {
      "include": ["refs/heads/main"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 0,
        "dismiss_stale_reviews_on_push": false,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": false
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks": true,
        "do_not_enforce_on_create": false,
        "required_status_checks": []
      }
    },
    {
      "type": "deletion"
    },
    {
      "type": "non_fast_forward"
    }
  ]
}
EOF
```

`required_status_checks` заполняется именами CI-джобов после первого пуша (см. шаблоны CI ниже). Имена джобов: `lint`, `typecheck`, `test`, `complexity` (Python) или `check` (JS/TS).

---

## Phase B — Project scaffolding

> Шаги 4-9 — шаблоны файлов для Python или JS/TS проекта. Можно применять к существующему репо (skip Phase A). Не зависят от GitHub remote.

## 4. Python-проект

### Инструменты

| Инструмент | Назначение | Конфиг в |
|---|---|---|
| **uv** | Package manager, virtual env | `pyproject.toml` (build + deps) |
| **ruff** | Linter + formatter (замена flake8/isort/black) | `pyproject.toml` `[tool.ruff]` |
| **mypy** | Строгая типизация | `pyproject.toml` `[tool.mypy]` |
| **pytest** + **pytest-cov** | Тесты + покрытие | `pyproject.toml` `[tool.pytest]` |
| **xenon** | Анализ сложности кода | CI workflow |
| **pre-commit** | Git hooks (ruff + mypy перед коммитом) | `.pre-commit-config.yaml` |
| **hatchling** | Build backend (wheel) | `pyproject.toml` `[build-system]` |

### pyproject.toml

> Заменить `<package-name>`, `<description>`, `<owner>/<repo>` на реальные значения. `additional_dependencies` в pre-commit — список runtime-зависимостей (для mypy).

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "<package-name>"
version = "0.1.0"
description = "<description>"
readme = "README.md"
license = "MIT"
requires-python = ">=3.12"
authors = [{ name = "slaid098" }]
keywords = []
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: End Users/Desktop",
    "License :: OSI Approved :: MIT License",
    "Operating System :: Microsoft :: Windows",
    "Operating System :: POSIX :: Linux",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Programming Language :: Python :: 3.14",
]

dependencies = []

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "pytest-timeout>=2.2",
    "mypy>=1.10",
    "ruff>=0.5",
    "xenon>=0.9",
    "pre-commit>=3.7",
]

[project.urls]
Homepage = "https://github.com/slaid098/<repo>"
Repository = "https://github.com/slaid098/<repo>"
Issues = "https://github.com/slaid098/<repo>/issues"
Changelog = "https://github.com/slaid098/<repo>/blob/main/CHANGELOG.md"

[tool.hatch.build.targets.wheel]
packages = ["src/<package_name>"]

# ── Ruff ──────────────────────────────────────────────────────────────────

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E", "W",    # pycodestyle
    "F",         # pyflakes
    "I",         # isort
    "B",         # bugbear
    "UP",        # pyupgrade
    "SIM",       # simplify
    "C90",       # mccabe complexity
    "PL",        # pylint
    "RUF",       # ruff-specific
    "S",         # bandit (security)
    "TRY",       # tryceratops (exception handling)
    "LOG",       # flake8-logging
]
ignore = [
    "S101",      # assert in tests
    "S311",      # pseudo-random for non-crypto use
    "RUF001",    # ambiguous Cyrillic chars (we write in Russian)
    "RUF002",    # same for docstrings
    "RUF003",    # same for comments
    "TRY003",    # long messages outside exception class
    "PLR2004",   # magic values in tests
    "S106",      # hardcoded passwords in tests
]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 5
max-branches = 12
max-returns = 5
max-statements = 50

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101", "PLR2004", "S106", "S603", "S607"]

# ── mypy ──────────────────────────────────────────────────────────────────

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true

# ── pytest ────────────────────────────────────────────────────────────────

[tool.pytest.ini_options]
addopts = "--cov=<package_name> --cov-report=term-missing --cov-fail-under=90 --timeout=120"
testpaths = ["tests"]

# ── coverage ──────────────────────────────────────────────────────────────

[tool.coverage.run]
source = ["src/<package_name>"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

### .pre-commit-config.yaml

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.18.2
    hooks:
      - id: mypy
        additional_dependencies: []
```

`additional_dependencies` — список runtime-зависимостей проекта (из `[project.dependencies]`), чтобы mypy мог резолвить типы.

### .gitignore (Python)

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
*.egg
build/
dist/
.eggs/
*.spec

# Virtual environments
.venv/
venv/

# Environment / secrets
.env
*.env
!.env.template

# Testing / quality caches
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/
```

### .github/workflows/ci.yml (Python)

4 job'а: lint → typecheck → test (matrix) → complexity.

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra dev
      - run: uv run ruff check src/ tests/
      - run: uv run ruff format --check src/ tests/

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra dev
      - run: uv run mypy src/

  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python: ["3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra dev --python ${{ matrix.python }}
      - run: uv run pytest

  complexity:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --extra dev
      - run: uv run xenon --max-absolute B --max-modules A --max-average A src/
```

### Структура проекта (Python)

```
<repo>/
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   └── dependabot.yml
├── src/
│   └── <package_name>/
│       ├── __init__.py
│       └── py.typed
├── tests/
│   └── __init__.py
├── .pre-commit-config.yaml
├── .gitignore
├── LICENSE
├── pyproject.toml
├── README.md
└── uv.lock
```

---

## 5. JS/TS-проект

### Инструменты

| Инструмент | Назначение | Конфиг в |
|---|---|---|
| **npm** | Package manager | `package.json` |
| **Biome** | Linter + formatter (замена ESLint/Prettier) | `biome.json` |
| **TypeScript** | Строгая типизация | `tsconfig.json` |
| **Vitest** + **@vitest/coverage-v8** | Тесты + покрытие | `vitest.config.ts` |
| **Knip** | Dead-code detection | `knip.json` |

### package.json

> Заменить `<name>`, `<description>` на реальные значения. `entry` в knip.json — точка входа (для tree-shaking анализа).

```json
{
  "name": "<name>",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": {
    "node": ">=22"
  },
  "scripts": {
    "dev": "<dev-command>",
    "build": "<build-command>",
    "lint": "biome check",
    "format": "biome format --write",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "knip": "knip"
  },
  "devDependencies": {
    "@biomejs/biome": "^1.9.4",
    "@types/node": "^22.10.0",
    "@vitest/coverage-v8": "^3.0.0",
    "happy-dom": "^20.10.0",
    "knip": "^6.24.0",
    "typescript": "^5.7.0",
    "vitest": "^3.0.0"
  }
}
```

### biome.json

```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "vcs": {
    "enabled": true,
    "clientKind": "git",
    "useIgnoreFile": true
  },
  "files": {
    "ignoreUnknown": true,
    "ignore": ["node_modules", "dist", "coverage"]
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100,
    "lineEnding": "lf"
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "always",
      "trailingCommas": "all"
    }
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "suspicious": {
        "noExplicitAny": "error"
      }
    }
  }
}
```

### knip.json

```json
{
  "entry": ["src/index.ts"],
  "project": ["src/**/*.ts", "src/**/*.tsx"],
  "ignore": []
}
```

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noFallthroughCasesInSwitch": true,
    "noImplicitOverride": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "types": ["node"]
  },
  "include": ["src", "tests"],
  "exclude": ["node_modules", "dist"]
}
```

### vitest.config.ts

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      thresholds: {
        lines: 60,
        functions: 60,
        branches: 60,
        statements: 60,
      },
      exclude: [
        "tests/**",
        "dist/**",
        "vitest.config.ts",
      ],
    },
  },
});
```

### .gitignore (JS/TS)

```gitignore
node_modules/
dist/
coverage/
*.log
.DS_Store
.env
```

### .github/workflows/ci.yml (JS/TS)

Single job: lint → typecheck → knip → test → build.

```yaml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"
      - run: npm ci
      - name: Lint (Biome)
        run: npm run lint
      - name: Typecheck
        run: npm run typecheck
      - name: Knip
        run: npm run knip
      - name: Test (Vitest + Coverage)
        run: npm run test
      - name: Build
        run: npm run build
```

### Структура проекта (JS/TS)

```
<repo>/
├── .github/
│   ├── workflows/
│   │   └── ci.yml
│   └── dependabot.yml
├── src/
│   └── index.ts
├── tests/
├── .gitignore
├── biome.json
├── knip.json
├── package.json
├── package-lock.json
├── tsconfig.json
├── vitest.config.ts
├── LICENSE
└── README.md
```

---

## 6. Dependabot

Автоматическое обновление зависимостей. Еженедельно, 5 PR max.

### Python (uv/pip)

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
```

### JS/TS (npm)

```yaml
version: 2
updates:
  - package-ecosystem: npm
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
```

---

## 7. Общие файлы

### LICENSE (MIT)

```
MIT License

Copyright (c) 2026 slaid098

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### .editorconfig

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true

[*.{py,toml}]
indent_style = space
indent_size = 4

[*.{ts,tsx,js,jsx,json,yml,yaml,css,md}]
indent_style = space
indent_size = 2
```

---

## 8. Установка pre-commit

### Python

```bash
uv sync --extra dev
uv run pre-commit install
uv run pre-commit run --all-files
```

### JS/TS

Pre-commit hooks не используются. Все quality gates — в CI (lint → typecheck → knip → test → build).

---

## 9. Чек-лист верификации

- [ ] Репозиторий создан (`gh repo create`)
- [ ] `gh auth setup-git` выполнен (push/pull работает)
- [ ] Squash-only merge, delete branch on merge (Step 2)
- [ ] Branch protection на main (Step 3)
- [ ] CI пайплайн зелёный на первом PR
- [ ] Pre-commit hooks установлены (Python) / CI гоняет (JS/TS)
- [ ] Dependabot включён (Settings → Code security → Dependabot)
- [ ] LICENSE, .gitignore, .editorconfig в репозитории
- [ ] `uv.lock` / `package-lock.json` закоммичен
