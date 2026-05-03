# gptprof-public

Sanitized public OpenClaw skill/plugin for managing OpenAI Codex OAuth profiles and keeping GPT traffic on the native Codex runtime.

Русская версия — ниже.

---

# ENGLISH

## What this skill is for

`gptprof-public` solves a specific OpenClaw operational problem: you may have several ChatGPT/OpenAI Codex OAuth accounts, but OpenClaw needs a reliable way to switch between them and verify that GPT models run through the correct native Codex runtime.

Without a dedicated profile manager, it is easy to end up in a broken state. The model route uses `openai-codex/gpt-*` instead of `openai/*`. The execution runtime stays on Pi instead of switching to native Codex. Agents keep using stale auth files after a manual switch. Sessions do not reload auth state after a new account is authorized. The `/gptprof status` command makes these states visible and provides commands to fix them.

## The key distinction

This is the most important concept in this skill:

- Auth provider: `openai-codex` (OAuth token is for ChatGPT/Codex auth)
- Correct execution route: model `openai/*` + `agentRuntime.id = "codex"`

The OAuth profile remains an OpenAI Codex profile. This does not mean the model route should stay on `openai-codex/*` with Pi runtime. `/gptprof status` explicitly detects the old Pi route and flags it as `needs native Codex`.

## Main use cases

### Check the active GPT account

```
/gptprof
/gptprof status
```

Shows:

- active local profile slug
- email attached to each profile
- refresh-token availability
- token expiry date when available
- whether the current OpenClaw route is native Codex
- whether device authorization is pending

### Add a new OpenAI Codex OAuth profile

```
/gptprof add
```

Starts OpenAI device authorization and returns a verification URL, user code, and expiration window. After approving in the browser, run:

```
/gptprof check
```

The manager exchanges the authorization code for tokens, stores them in the local profile pool, switches OpenClaw to the new profile, updates agent auth files, and schedules a gateway restart if enabled.

### Switch between existing profiles

```
/gptprof switch <slug>
```

Copies the selected local profile into the active Codex auth location, updates OpenClaw agent auth records, updates session profile overrides, and reapplies the native Codex route.

### Force native Codex routing

```
/gptprof use-native
```

Sets OpenClaw defaults to:

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "openai/gpt-5.5" },
      "agentRuntime": { "id": "codex", "fallback": "none" }
    }
  }
}
```

Also ensures the `codex` plugin is enabled and allowed.

## Secret policy

This repository is public-safe by design. It does not contain OAuth tokens, refresh tokens, access tokens, account IDs, or user auth state. Runtime secrets are stored only on the user's machine:

```
~/.codex/auth.json
~/.openclaw/codex-profiles/*/auth.json
~/.openclaw/agents/*/agent/auth-*.json
```

These paths must never be committed. The OAuth client ID used by the manager is public application metadata, not a client secret.

## Repository layout

```
SKILL.md                         OpenClaw skill metadata and usage notes
plugin/                          OpenClaw extension for /gptprof command handling
plugin/index.js                  Telegram/tool command bridge
plugin/openclaw.plugin.json      Plugin manifest
plugin/package.json              Plugin package metadata
bin/codex-profile-manager.py     Local profile manager CLI
tests/smoke.sh                  Syntax + secret-pattern smoke test
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

## Commands

```
/gptprof
/gptprof status
/gptprof add
/gptprof check
/gptprof use-native
/gptprof switch <slug>
```

The manager CLI also works directly:

```bash
python3 ~/.local/bin/codex-profile-manager.py status
python3 ~/.local/bin/codex-profile-manager.py device-start
python3 ~/.local/bin/codex-profile-manager.py device-check
python3 ~/.local/bin/codex-profile-manager.py switch <slug>
python3 ~/.local/bin/codex-profile-manager.py apply-native-route
```

## Safety checks

```bash
bash tests/smoke.sh
```

The smoke test checks JavaScript syntax, Python syntax, and obvious committed-token patterns.

## What this skill does not do

- It does not bypass OpenAI limits.
- It does not create paid accounts.
- It does not store credentials in Git.
- It does not guarantee that OpenAI/ChatGPT accepts every account or device authorization attempt.
- It manages local profile files and route config, not OpenClaw's internal auth model.

---

# РУССКИЙ

## Зачем нужен этот скилл

`gptprof-public` решает конкретную операционную проблему OpenClaw: у пользователя может быть несколько ChatGPT/OpenAI Codex OAuth-аккаунтов, а OpenClaw должен уметь переключаться между ними и проверять, что GPT-модели идут через правильный native Codex runtime.

Без отдельного менеджера профилей легко получить сломанное состояние. Модельный маршрут использует `openai-codex/gpt-*` вместо `openai/*`. Runtime выполнения остаётся на Pi вместо native Codex. Агенты продолжают использовать устаревшие auth-файлы после ручного переключения. Сессии не подхватывают новое auth state после авторизации нового аккаунта. Команда `/gptprof status` делает такие состояния видимыми и даёт команды для исправления.

## Главное различие

Самая важная концепция скилла:

- провайдер авторизации: `openai-codex` (OAuth-токен для ChatGPT/Codex auth)
- правильный маршрут выполнения: модель `openai/*` + `agentRuntime.id = "codex"`

OAuth-профиль остаётся профилем OpenAI Codex. Но это не значит, что модельный маршрут должен оставаться `openai-codex/*` на Pi runtime. `/gptprof status` специально определяет старый Pi route и помечает его как `needs native Codex`.

## Основные сценарии

### Проверить активный GPT-аккаунт

```
/gptprof
/gptprof status
```

Показывает:

- активный локальный профиль
- email каждого профиля
- наличие refresh token
- дату истечения токена
- текущий OpenClaw route — native Codex или нет
- есть ли незавершённая device authorization

### Добавить новый OpenAI Codex OAuth-профиль

```
/gptprof add
```

Запускает OpenAI device authorization, возвращает verification URL, код пользователя и время жизни. После подтверждения в браузере:

```
/gptprof check
```

Менеджер обменивает authorization code на токены, сохраняет их в локальный пул профилей, переключает OpenClaw на новый профиль, обновляет auth-файлы агентов и планирует перезапуск gateway.

### Переключиться между существующими профилями

```
/gptprof switch <slug>
```

Копирует выбранный локальный профиль в активное место Codex auth, обновляет OpenClaw agent auth records, обновляет session overrides и заново применяет native Codex route.

### Принудительно включить native Codex route

```
/gptprof use-native
```

Выставляет дефолты OpenClaw:

```json
{
  "agents": {
    "defaults": {
      "model": { "primary": "openai/gpt-5.5" },
      "agentRuntime": { "id": "codex", "fallback": "none" }
    }
  }
}
```

Также проверяет, что плагин `codex` включён и разрешён.

## Политика по секретам

Этот репозиторий безопасен для публичной публикации. Нет OAuth-токенов, refresh tokens, access tokens, account IDs или пользовательского auth-state. Секреты живут только локально:

```
~/.codex/auth.json
~/.openclaw/codex-profiles/*/auth.json
~/.openclaw/agents/*/agent/auth-*.json
```

Эти файлы нельзя коммитить. OAuth client id в менеджере — публичный идентификатор приложения, не client secret.

## Структура репозитория

```
SKILL.md                         метаданные OpenClaw-скилла
plugin/                          OpenClaw extension для /gptprof
plugin/index.js                  мост между Telegram/tool command и CLI
plugin/openclaw.plugin.json      манифест плагина
plugin/package.json              метаданные пакета
bin/codex-profile-manager.py     локальный CLI-менеджер профилей
tests/smoke.sh                  syntax check + проверка на секреты
```

## Установка

```bash
mkdir -p ~/.local/bin ~/.openclaw/extensions
cp bin/codex-profile-manager.py ~/.local/bin/codex-profile-manager.py
chmod 700 ~/.local/bin/codex-profile-manager.py
cp -R plugin ~/.openclaw/extensions/openclaw-codex-profile-switcher
```

Затем включить extension в конфиге OpenClaw и разрешить нужные плагины:

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

Точная форма конфига зависит от установки OpenClaw.

## Команды

```
/gptprof
/gptprof status
/gptprof add
/gptprof check
/gptprof use-native
/gptprof switch <slug>
```

CLI-менеджер работает напрямую:

```bash
python3 ~/.local/bin/codex-profile-manager.py status
python3 ~/.local/bin/codex-profile-manager.py device-start
python3 ~/.local/bin/codex-profile-manager.py device-check
python3 ~/.local/bin/codex-profile-manager.py switch <slug>
python3 ~/.local/bin/codex-profile-manager.py apply-native-route
```

## Проверки

```bash
bash tests/smoke.sh
```

Smoke test проверяет синтаксис JavaScript, Python и очевидные паттерны закоммиченных токенов.

## Чего этот скилл не делает

- Не обходит лимиты OpenAI.
- Не создаёт платные аккаунты.
- Не хранит credentials в Git.
- Не гарантирует, что OpenAI/ChatGPT примет любой аккаунт или любую device authorization попытку.
- Управляет локальными profile-файлами и route config, но не внутренней auth-моделью OpenClaw.
