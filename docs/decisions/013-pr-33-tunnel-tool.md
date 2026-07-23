# ADR-013: Cloudflare tunnel toggle tool

## Статус
Accepted

## Контекст
Tunnel skill в старом приватном репо (slaid098/opencode, PR#52/54) содержал приватные данные — IPs, домены, UUIDs. Для публичного репо opencode-config нужен tool без хардкода. Toggle mode (без аргументов) максимально прост для агента: первый вызов = start, второй = stop.

## Решение
TS tool `tunnel.ts` (wrapper) + bash script `tunnel.sh` (toggle logic). Named tunnel через env var `CLOUDFLARE_TUNNEL_TOKEN` (dashboard-managed, без локального config.yml). PID-файл `/tmp/tunnel.pid` отслеживает состояние. `TUNNEL_DOMAIN` — опциональный, только для display в output.

## Альтернативы
- Quick mode (random `*.trycloudflare.com`) — отклонено (random URL меняется при рестарте, не подходит для стабильного доступа)
- localtunnel (npx) — отклонено (лишняя Node.js зависимость, less reliable чем cloudflared)
- SSH localhost.run — отклонено (ограниченный bandwidth, TCP-only)
