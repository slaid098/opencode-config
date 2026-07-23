#!/usr/bin/env bash
# Create handoff + ADR templates for a PR.
# Usage: bash config/scripts/scaffold-handoff.sh <PR#> <slug>
# Idempotent: does not overwrite existing files.
set -euo pipefail

PR="${1:?Usage: scaffold-handoff.sh <PR#> <slug>}"
SLUG="${2:?Usage: scaffold-handoff.sh <PR#> <slug>}"

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "")"
if [ -z "$REPO_ROOT" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

HANDOFF_DIR="$REPO_ROOT/docs/handoff"
ADR_DIR="$REPO_ROOT/docs/decisions"
mkdir -p "$HANDOFF_DIR" "$ADR_DIR"

HANDOFF="$HANDOFF_DIR/pr-${PR}-${SLUG}.md"
TODAY="$(date +%Y-%m-%d)"

if [ -f "$HANDOFF" ]; then
    echo "handoff already exists: $HANDOFF"
else
    cat > "$HANDOFF" <<EOF
---
pr: ${PR}
title: <заполни>
---

## Что сделано
<заполни>

## Почему
<заполни>

## Pending
<заполни, или «—»>

## Watch out
<заполни, или «—»>
EOF
    echo "created: $HANDOFF"
fi

EXISTING_ADR="$(ls "$ADR_DIR"/*-pr-${PR}-${SLUG}.md 2>/dev/null | head -n1 || true)"
if [ -n "$EXISTING_ADR" ]; then
    ADR="$EXISTING_ADR"
    echo "ADR already exists: $ADR"
else
    NEXT_N="$(ls "$ADR_DIR" 2>/dev/null | grep -E '^[0-9]{3}-' | wc -l | awk '{print $1+1}')"
    NN="$(printf "%03d" "$NEXT_N")"
    ADR="$ADR_DIR/${NN}-pr-${PR}-${SLUG}.md"
    cat > "$ADR" <<EOF
# ADR-${NN}: <title>

## Статус
Accepted (${TODAY})

## Контекст
<заполни, или «—» если архитектурных решений не было>

## Решение
<заполни, или «—»>

## Альтернативы
<заполни, или «—»>
EOF
    echo "created: $ADR"
fi

echo ""
echo "handoff: $HANDOFF"
echo "adr:     $ADR"