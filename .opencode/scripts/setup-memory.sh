#!/usr/bin/env bash
set -euo pipefail

MEMORY_DIR="${OPENCODE_MEMORY_DIR:-/root/.local/share/opencode/opencode-memory}"
HOOK="$MEMORY_DIR/.git/hooks/post-commit"
BRANCH="master"
EXPECTED_HOOK='#!/bin/bash
git push origin master 2>/dev/null || true'

if [ -z "${OPENCODE_MEMORY_REMOTE:-}" ]; then
  echo "ERROR: OPENCODE_MEMORY_REMOTE not set" >&2
  exit 1
fi
REMOTE="${OPENCODE_MEMORY_REMOTE}"

echo "memory setup: $MEMORY_DIR"

# 1. MEMORY_DIR exists? → mkdir -p
if [ ! -d "$MEMORY_DIR" ]; then
  mkdir -p "$MEMORY_DIR"
  echo "  [1/6] created directory: $MEMORY_DIR"
else
  echo "  [1/6] directory exists"
fi

# 2. .git exists? → clone (no) | pull --ff-only (yes)
if [ ! -d "$MEMORY_DIR/.git" ]; then
  echo "  [2/6] cloning remote: $REMOTE"
  git clone --origin origin "$REMOTE" "$MEMORY_DIR"
  git -C "$MEMORY_DIR" checkout "$BRANCH" 2>/dev/null || true
else
  echo "  [2/6] pulling latest (ff-only)"
  git -C "$MEMORY_DIR" pull --ff-only origin "$BRANCH" 2>/dev/null || \
    echo "    pull skipped (no upstream or offline)"
fi

# 3. remote origin correct? → set-url (no) | noop (yes)
CURRENT_REMOTE="$(git -C "$MEMORY_DIR" remote get-url origin 2>/dev/null || echo "")"
if [ "$CURRENT_REMOTE" != "$REMOTE" ]; then
  echo "  [3/6] fixing remote: $CURRENT_REMOTE → $REMOTE"
  git -C "$MEMORY_DIR" remote set-url origin "$REMOTE"
else
  echo "  [3/6] remote correct"
fi

# 4. post-commit hook exists + content correct? → create/fix (no) | noop (yes)
NEEDS_HOOK=0
if [ ! -f "$HOOK" ]; then
  NEEDS_HOOK=1
elif [ "$(cat "$HOOK")" != "$EXPECTED_HOOK" ]; then
  NEEDS_HOOK=1
fi
if [ "$NEEDS_HOOK" -eq 1 ]; then
  echo "  [4/6] installing post-commit hook (auto-push)"
  mkdir -p "$(dirname "$HOOK")"
  printf '%s\n' "$EXPECTED_HOOK" > "$HOOK"
  chmod +x "$HOOK"
else
  echo "  [4/6] hook correct"
fi

# 5. .rag index exists? → rag index (no) | noop (yes)
if command -v rag >/dev/null 2>&1; then
  if [ ! -d "$MEMORY_DIR/.rag" ]; then
    echo "  [5/6] building RAG index"
    (cd "$MEMORY_DIR" && rag index) 2>/dev/null || echo "    rag index failed — continuing"
  else
    echo "  [5/6] RAG index exists"
  fi
else
  echo "  [5/6] rag CLI not installed — skipping index"
fi

# 6. status
echo "  [6/6] done"
echo ""
echo "memory: ready at $MEMORY_DIR"
echo "  remote: $REMOTE"
echo "  branch: $BRANCH"
echo "  auto-push: enabled (post-commit hook)"