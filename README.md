# gptprof-public

Sanitized public OpenClaw skill/plugin for managing OpenAI Codex OAuth profiles, GPT profile buttons, and lazy usage-based profile switching.

Русская версия - ниже.

---

# English

## What This Skill Is For

`gptprof-public` manages several local ChatGPT/OpenAI Codex OAuth profiles for OpenClaw. It lets an operator add profiles, switch between them, show usage for the 5-hour and weekly windows, and keep the base GPT route on OpenAI Codex through the Pi runtime.

The intended base route in this public version is:

- auth provider: `openai-codex`
- model: `openai-codex/gpt-5.5`
- runtime: `agents.defaults.agentRuntime.id = "pi"`

This repo contains code only. It does not include tokens, account IDs, local auth state, or machine-specific profile data.

## Main Use Cases

### Check the active profile

```text
/gptprof
/gptprof status
```

Shows:

- active local profile slug
- route status
- token refresh availability
- token expiry date when available
- cached 5-hour and weekly usage
- Telegram inline buttons for profile switching and auth actions

Profile email addresses are intentionally not shown in the compact Telegram status because profile slugs are usually enough for day-to-day switching.

### Add a new OpenAI Codex OAuth profile

```text
/gptprof add
```

Starts OpenAI device authorization and returns a verification URL, user code, and expiration window. After approving in the browser:

```text
/gptprof check
```

The manager exchanges the device code for tokens, stores them in the local profile pool, switches OpenClaw to the new profile, updates agent auth files, updates session auth overrides, and schedules a gateway restart if enabled.

### Switch between existing profiles

```text
/gptprof switch <slug>
```

Copies the selected local profile into the active Codex auth location, updates OpenClaw agent auth records, updates session profile overrides, and keeps the base Pi route applied.

In Telegram, profile buttons use native inline keyboard rows:

```json
[[{"text":"✓ work 42%","callback_data":"gptprof:work"}]]
```

For OpenClaw `2026.5.3-beta.2`, avoid abstract button fields such as `label` / `value`, avoid `style`, and avoid a flat button list. Telegram expects native `text` / `callback_data`, and this OpenClaw delivery path expects rows.

### Refresh usage

```text
/gptprof refresh
```

Fetches usage for known profiles and caches it in local state. Usage checks are lazy and bounded; this skill does not install a timer, cron job, daemon, or polling loop.

### Autoswitch

```text
/gptprof autoswitch
```

Switches only when the active profile has either its 5-hour or weekly usage window at `>=95%`, and another healthy profile is below `95%` for both windows.

If the target profile is already over threshold, the Telegram button shows a warning marker and the callback explains why it is not switching. This avoids the confusing case where a manual switch succeeds and the next `/gptprof` or `/gptt` immediately switches away again.

### Apply the base Pi route

```text
/gptprof use-pi
```

Sets OpenClaw defaults to:

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "openai-codex/gpt-5.5", "fallbacks": [] },
      "agentRuntime": { "id": "pi" }
    }
  }
}
```

OpenClaw `2026.5.3-beta.2` rejects `agents.defaults.agentRuntime.fallback`; do not write that key for this route.

## Commands

```text
/gptprof
/gptprof status
/gptprof add
/gptprof check
/gptprof refresh
/gptprof autoswitch
/gptprof use-pi
/gptprof switch <slug>
```

The manager CLI also works directly:

```bash
python3 ~/.local/bin/codex-profile-manager.py status
python3 ~/.local/bin/codex-profile-manager.py device-start
python3 ~/.local/bin/codex-profile-manager.py device-check
python3 ~/.local/bin/codex-profile-manager.py usage
python3 ~/.local/bin/codex-profile-manager.py autoswitch
python3 ~/.local/bin/codex-profile-manager.py apply-pi-route
python3 ~/.local/bin/codex-profile-manager.py switch <slug>
```

## Secret Policy

This repository is public-safe by design. It does not contain OAuth tokens, refresh tokens, access tokens, account IDs, or user auth state. Runtime secrets stay only on the user's machine:

```text
~/.codex/auth.json
~/.openclaw/codex-profiles/*/auth.json
~/.openclaw/agents/*/agent/auth-*.json
```

These paths must never be committed. The OAuth client ID used by the manager is public application metadata, not a client secret.

## Repository Layout

```text
SKILL.md                         OpenClaw skill metadata and usage notes
plugin/                          OpenClaw extension for /gptprof command handling
plugin/index.js                  Telegram/tool command bridge
plugin/openclaw.plugin.json      Plugin manifest
plugin/package.json              Plugin package metadata
bin/codex-profile-manager.py     Local profile manager CLI
tests/smoke.sh                   Syntax + secret-pattern smoke test
```

## Install

```bash
mkdir -p ~/.local/bin ~/.openclaw/extensions
cp bin/codex-profile-manager.py ~/.local/bin/codex-profile-manager.py
chmod 700 ~/.local/bin/codex-profile-manager.py
cp -R plugin ~/.openclaw/extensions/openclaw-codex-profile-switcher
```

Then enable the extension in OpenClaw config and allow the required plugins:

```json
{
  "plugins": {
    "allow": ["openai", "codex", "codex-profile-switcher"],
    "entries": {
      "codex": { "enabled": true },
      "codex-profile-switcher": { "enabled": true }
    }
  }
}
```

Exact config shape may differ by OpenClaw installation.

## Safety Checks

```bash
bash tests/smoke.sh
```

The smoke test checks JavaScript syntax, Python syntax, and obvious committed-token patterns.

## What This Skill Does Not Do

- It does not bypass OpenAI limits.
- It does not create paid accounts.
- It does not store credentials in Git.
- It does not guarantee that OpenAI/ChatGPT accepts every account or device authorization attempt.
- It manages local profile files and route config, not OpenClaw's internal auth model.

---

# Русский

## Зачем Нужен Этот Скилл

`gptprof-public` управляет несколькими локальными ChatGPT/OpenAI Codex OAuth-профилями для OpenClaw. Он добавляет профили, переключает их, показывает usage по 5-часовому и недельному окнам и держит базовый GPT route на OpenAI Codex через Pi runtime.

Целевое базовое состояние в этой публичной версии:

- провайдер авторизации: `openai-codex`
- модель: `openai-codex/gpt-5.5`
- runtime: `agents.defaults.agentRuntime.id = "pi"`

В репозитории лежит только код. В нём нет токенов, account IDs, локального auth state или данных конкретной машины.

## Основные Сценарии

### Проверить активный профиль

```text
/gptprof
/gptprof status
```

Показывает:

- активный локальный профиль
- статус route
- наличие refresh token
- дату истечения токена
- cached usage по 5-часовому и недельному окнам
- Telegram inline-кнопки для переключения профилей и auth-действий

Email в компактном Telegram-статусе намеренно не показывается: для ежедневного переключения достаточно slug профиля.

### Добавить новый OpenAI Codex OAuth-профиль

```text
/gptprof add
```

Запускает OpenAI device authorization и возвращает verification URL, user code и время жизни. После подтверждения в браузере:

```text
/gptprof check
```

Менеджер обменивает device code на токены, сохраняет их в локальном пуле профилей, переключает OpenClaw на новый профиль, обновляет agent auth files, session auth overrides и планирует restart gateway, если это включено.

### Переключить существующий профиль

```text
/gptprof switch <slug>
```

Копирует выбранный локальный профиль в активное место Codex auth, обновляет OpenClaw agent auth records, обновляет session profile overrides и сохраняет базовый Pi route.

В Telegram кнопки профилей используют native inline keyboard rows:

```json
[[{"text":"✓ work 42%","callback_data":"gptprof:work"}]]
```

Для OpenClaw `2026.5.3-beta.2` не используйте абстрактные поля `label` / `value`, не добавляйте `style` и не отдавайте плоский список кнопок. Telegram ждёт native `text` / `callback_data`, а этот OpenClaw delivery path ждёт rows.

### Обновить usage

```text
/gptprof refresh
```

Загружает usage известных профилей и кеширует его в локальном state. Проверки usage ленивые и ограничены по времени; этот скилл не ставит timer, cron job, daemon или polling loop.

### Autoswitch

```text
/gptprof autoswitch
```

Переключает профиль только если активный профиль достиг `>=95%` по 5-часовому или недельному окну, а другой рабочий профиль ниже `95%` по обоим окнам.

Если целевой профиль уже выше порога, Telegram-кнопка показывает warning marker, а callback объясняет, почему переключения нет. Это убирает ситуацию, когда ручной switch успешен, но следующий `/gptprof` или `/gptt` тут же переключает обратно.

### Применить базовый Pi route

```text
/gptprof use-pi
```

Ставит OpenClaw defaults:

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "openai-codex/gpt-5.5", "fallbacks": [] },
      "agentRuntime": { "id": "pi" }
    }
  }
}
```

OpenClaw `2026.5.3-beta.2` отклоняет `agents.defaults.agentRuntime.fallback`; для этого route такой ключ писать нельзя.

## Команды

```text
/gptprof
/gptprof status
/gptprof add
/gptprof check
/gptprof refresh
/gptprof autoswitch
/gptprof use-pi
/gptprof switch <slug>
```

CLI менеджера:

```bash
python3 ~/.local/bin/codex-profile-manager.py status
python3 ~/.local/bin/codex-profile-manager.py device-start
python3 ~/.local/bin/codex-profile-manager.py device-check
python3 ~/.local/bin/codex-profile-manager.py usage
python3 ~/.local/bin/codex-profile-manager.py autoswitch
python3 ~/.local/bin/codex-profile-manager.py apply-pi-route
python3 ~/.local/bin/codex-profile-manager.py switch <slug>
```

## Политика Секретов

Этот репозиторий безопасен для публикации. В нём нет OAuth tokens, refresh tokens, access tokens, account IDs или пользовательского auth state. Runtime secrets остаются только на машине пользователя:

```text
~/.codex/auth.json
~/.openclaw/codex-profiles/*/auth.json
~/.openclaw/agents/*/agent/auth-*.json
```

Эти пути нельзя коммитить. OAuth client ID в менеджере - публичные metadata приложения, не client secret.

## Проверки

```bash
bash tests/smoke.sh
```

Smoke test проверяет JavaScript syntax, Python syntax и очевидные committed-token patterns.
