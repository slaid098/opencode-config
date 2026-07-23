---
pr_number: 34
title: Tunnel tool with toggle mode
---

# PR: Tunnel tool with toggle mode

## Что сделано
- `.opencode/tools/tunnel.ts` — TS tool wrapper (toggle без args, вызывает `bash .opencode/scripts/tunnel.sh`)
- `.opencode/scripts/tunnel.sh` — bash toggle: PID файл → stop, нет → start named tunnel (`cloudflared tunnel run --token $CLOUDFLARE_TUNNEL_TOKEN`)
- `Dockerfile` — cloudflared install (`curl -L ... -o /usr/local/bin/cloudflared`)
- `.env.example` — добавлен `TUNNEL_DOMAIN=` (опциональный, для display)
- ADR-013 + этот handoff

## Почему
Tunnel skill в старом приватном репо содержал приватные данные (IPs, домены, UUID). Для публичного репо нужен tool без хардкода. Toggle mode (без аргументов) максимально прост для агента — первый вызов = start, второй = stop.

## Pending
- Нет

## Watch out
- `CLOUDFLARE_TUNNEL_TOKEN` должен быть в `.env` (compose env_file) — без него скрипт падает exit 1
- PID-файл `/tmp/tunnel.pid` теряется при рестарте контейнера — `status` скажет not running, нужно перезапустить
- DinD: origin host в Cloudflare dashboard должен быть `docker-dind:<PORT>` (не `localhost:<PORT>`), иначе 502 Bad Gateway
- Tools auto-discovered через @opencode-ai/plugin — НЕ нужно регистрировать в opencode.json
- `cloudflared` в Dockerfile устанавливается из latest release (не pinned version)
