---
name: branch
description: Use when creating a new git branch for work. Describes branch naming convention and creation workflow. Format: type/scope/kebab-description.
---

## Branch format

```
type/scope/kebab-description
```

### Examples

```
feat/auth/add-refresh-token-rotation
fix/api/handle-null-response
chore/deps/update-pytest
refactor/db/simplify-queries
```

### Rules

1. Always branch from `main`
2. Before creating a branch, **discuss with the user**:
   - Confirm the branch name
   - Confirm the scope
   - Make sure you understand the task
3. Push the branch to remote after creation

The type and scope follow the same conventions as commit messages.
