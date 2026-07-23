# PR: Fix reviewer agent echo bypass

## Что сделано
- Удалён `"echo *": allow` из .opencode/agents/reviewer.md bash allow-list
- echo больше не может писать файлы (echo "x" > file.txt)
- Rule 10 становится accurate ("echo не в allow-list")

## Почему
Security: echo * + edit: deny = bypass risk. echo с перенаправлением пишет файл, обходя read-only контракт ревьюера.

## Pending
- Нет

## Watch out
- reviewer всё ещё имеет pwd, ls, cat для debug вывода
- Удаление echo не влияет на функциональность ревьюера