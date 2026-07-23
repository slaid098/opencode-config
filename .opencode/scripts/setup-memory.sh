#!/bin/bash
set -euo pipefail

MEMORY_DIR="${OPENCODE_MEMORY_DIR}"
REMOTE="${OPENCODE_MEMORY_REMOTE:-https://github.com/slaid098/opencode-memory.git}"

if [ -z "$MEMORY_DIR" ]; then
  echo "ERROR: OPENCODE_MEMORY_DIR not set"
  exit 1
fi

echo "Setting up memory repo at: $MEMORY_DIR"

# 1. If .git doesn't exist — init + pull
if [ ! -d "$MEMORY_DIR/.git" ]; then
  echo "Initializing new memory repo..."
  mkdir -p "$MEMORY_DIR"
  git init "$MEMORY_DIR"
  git -C "$MEMORY_DIR" remote add origin "$REMOTE"
  git -C "$MEMORY_DIR" pull origin master 2>/dev/null || echo "No remote memory yet — starting fresh"
else
  echo "Memory repo already exists."
  # 2. If remote not configured — add it
  if ! git -C "$MEMORY_DIR" remote get-url origin 2>/dev/null; then
    git -C "$MEMORY_DIR" remote add origin "$REMOTE"
  fi
  # 3. Pull latest changes
  echo "Pulling latest memory..."
  git -C "$MEMORY_DIR" pull --rebase origin master 2>/dev/null || echo "Pull failed — continuing with local state"
fi

# 4. Install post-commit hook for auto-push
HOOK="$MEMORY_DIR/.git/hooks/post-commit"
echo "Installing post-commit hook for auto-push..."
cat > "$HOOK" << 'EOF'
#!/bin/bash
git push origin master 2>/dev/null || true
EOF
chmod +x "$HOOK"

echo ""
echo "Memory repo configured successfully."
echo "  Remote: $REMOTE"
echo "  Auto-push: enabled (post-commit hook)"
echo ""
echo "memory_save() will now auto-push after each commit."
