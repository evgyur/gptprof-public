# gptprof-public

Sanitized public OpenClaw skill/plugin for managing OpenAI Codex OAuth profiles and keeping GPT traffic on the native Codex runtime.

Русская версия ниже.

---

# ENGLISH

## What this skill is for

`gptprof-public` solves a narrow but painful OpenClaw operational problem: you may have several ChatGPT/OpenAI Codex OAuth accounts, but OpenClaw needs a safe way to switch between them and verify that GPT models are routed through the correct native Codex runtime.

Without a dedicated profile manager, it is easy to end up in a confusing state:

- OAuth tokens belong to the `openai-codex` provider;
- the selected model is accidentally configured as `openai-codex/gpt-*`;
- the execution runtime is still Pi instead of native Codex;
- agents keep using stale auth-profile files after a manual switch;
- a new account is authorized, but OpenClaw sessions do not reload the new auth state.

This skill makes those states visible and provides commands to fix them.

## The core distinction

This is the most important concept:

- Auth provider: `openai-codex`
- Correct execution route: `openai/*` model + `agentRuntime.id = "codex"`

The OAuth profile is still an OpenAI Codex/ChatGPT OAuth profile. That does not mean the model route should stay on `openai-codex/*` with Pi runtime.

`/gptprof status` explicitly detects the old/legacy Pi route and reports it as `needs native Codex`.

## Main use cases

### 1. Check the active GPT account

```text
/gptprof
/gptprof status
```

Shows:

- active local profile slug;
- email attached to each profile;
- refresh-token availability;
- token expiry date when available;
- whether the current OpenClaw route is native Codex;
- whether device authorization is pending.

### 2. Add a new OpenAI Codex OAuth profile

```text
/gptprof add
```

The command starts OpenAI device authorization and returns:

- verification URL;
- user code;
- expiration window.

After approving the login in the browser, run:

```text
/gptprof check
```

The manager exchanges the authorization code for tokens, stores them in the local profile pool, switches OpenClaw to the new profile, updates agent auth files, and schedules a gateway restart if enabled.

### 3. Switch between existing profiles

```text
/gptprof switch <slug>
```

This copies the selected local profile into the active Codex auth location, updates OpenClaw agent auth records, updates session profile overrides where appropriate, and reapplies the native Codex route.

### 4. Force native Codex routing

```text
/gptprof use-native
```

This sets OpenClaw defaults to:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai/gpt-5.5"
      },
      "agentRuntime": {
        "id": "codex",
        "fallback": "none"
      }
    }
  }
}
```

It also ensures the `codex` plugin is enabled/allowed.

## Secret policy

This repository is public-safe by design.

It does not contain OAuth tokens, refresh tokens, access tokens, account IDs, or user auth state.

Runtime secrets are stored only on the user's machine, for example:

```text
~/.codex/auth.json
~/.openclaw/codex-profiles/*/auth.json
~/.openclaw/agents/*/agent/auth-*.json
```

These paths must never be committed.

The OAuth client id used by the manager is public application metadata, not a client secret.

## Repository layout

```text
SKILL.md                         OpenClaw skill metadata and usage notes
plugin/                          OpenClaw extension for /gptprof command handling
plugin/index.js                  Telegram/tool command bridge
plugin/openclaw.plugin.json      Plugin manifest
plugin/package.json              Plugin package metadata
bin/codex-profile-manager.py     Local profile manager CLI
tests/smoke.sh                   Syntax + basic secret-pattern smoke test
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

Exact OpenClaw config shape may differ by installation.

## Commands

```text
/gptprof
/gptprof status
/gptprof add
/gptprof check
/gptprof use-native
/gptprof switch <slug>
```

The manager CLI can also be used directly:

```bash
python3 ~/.local/bin/codex-profile-manager.py status
python3 ~/.local/bin/codex-profile-manager.py device-start
python3 ~/.local/bin/codex-profile-manager.py device-check
python3 ~/.local/bin/codex-profile-manager.py switch <slug>
python3 ~/.local/bin/codex-profile-manager.py apply-native-route
```

## Safety checks

Run:

```bash
bash tests/smoke.sh
```

The smoke test checks JavaScript syntax, Python syntax, and obvious committed-token patterns.

## What this skill does not do

- It does not bypass OpenAI limits.
- It does not create paid accounts.
- It does not store credentials in Git.
- It does not guarantee that OpenAI/ChatGPT will accept every account or device authorization attempt.
- It does not replace OpenClaw's own auth model; it only manages local profile files and route config.

---

# РУССКИЙ

## Зачем нужен этот скилл

`gptprof-public` решает узкую, но неприятную операционную проблему OpenClaw: у пользователя может быть несколько ChatGPT/OpenAI Codex OAuth-аккаунтов, а OpenClaw должен уметь безопасно переключаться между ними и проверять, что GPT-модели идут через правильный native Codex runtime.

Без отдельного менеджера профилей легко получить запутанное состояние:

- OAuth-токены относятся к провайдеру `openai-codex`;
- модель случайно указана как `openai-codex/gpt-*`;
- выполнение всё ещё идёт через Pi runtime, а не через native Codex;
- агенты продолжают использовать старые auth-profile файлы после ручного переключения;
- новый аккаунт авторизован, но OpenClaw-сессии не подхватили новое состояние.

Этот скилл делает такие состояния видимыми и даёт команды для исправления.

## Главное различие

Самая важная мысль:

- провайдер авторизации: `openai-codex`;
- правильный маршрут выполнения: модель `openai/*` + `agentRuntime.id = "codex"`.

OAuth-профиль остаётся профилем OpenAI Codex/ChatGPT. Но это не значит, что модельный маршрут должен оставаться `openai-codex/*` на Pi runtime.

`/gptprof status` специально определяет старый/legacy Pi route и показывает, что нужен native Codex.

## Основные сценарии

### 1. Проверить активный GPT-аккаунт

```text
/gptprof
/gptprof status
```

Показывает:

- активный локальный профиль;
- email каждого профиля;
- есть ли refresh token;
- дату истечения токена, если она доступна;
- включён ли правильный native Codex route;
- есть ли незавершённая device authorization.

### 2. Добавить новый OpenAI Codex OAuth-профиль

```text
/gptprof add
```

Команда запускает OpenAI device authorization и возвращает:

- ссылку для подтверждения;
- код пользователя;
- время жизни кода.

После подтверждения входа в браузере нужно выполнить:

```text
/gptprof check
```

Менеджер обменяет authorization code на токены, сохранит их в локальный пул профилей, переключит OpenClaw на новый профиль, обновит auth-файлы агентов и, если включено, запланирует перезапуск gateway.

### 3. Переключиться между существующими профилями

```text
/gptprof switch <slug>
```

Команда копирует выбранный локальный профиль в активное место Codex auth, обновляет auth records агентов, обновляет session overrides там, где это нужно, и заново применяет native Codex route.

### 4. Принудительно включить native Codex route

```text
/gptprof use-native
```

Команда выставляет дефолты OpenClaw примерно в такое состояние:

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "openai/gpt-5.5"
      },
      "agentRuntime": {
        "id": "codex",
        "fallback": "none"
      }
    }
  }
}
```

Также проверяется, что плагин `codex` включён и разрешён.

## Политика по секретам

Этот репозиторий сделан безопасным для публичной публикации.

В нём нет OAuth-токенов, refresh tokens, access tokens, account IDs или пользовательского auth-state.

Секреты живут только локально на машине пользователя, например:

```text
~/.codex/auth.json
~/.openclaw/codex-profiles/*/auth.json
~/.openclaw/agents/*/agent/auth-*.json
```

Эти файлы нельзя коммитить.

OAuth client id в менеджере — это публичный идентификатор приложения, не client secret.

## Структура репозитория

```text
SKILL.md                         метаданные OpenClaw-скилла и заметки по использованию
plugin/                          OpenClaw extension для команды /gptprof
plugin/index.js                  мост между Telegram/tool command и CLI-менеджером
plugin/openclaw.plugin.json      манифест плагина
plugin/package.json              метаданные пакета
bin/codex-profile-manager.py     локальный CLI-менеджер профилей
tests/smoke.sh                   syntax check + базовая проверка на очевидные секреты
```

## Установка

```bash
mkdir -p ~/.local/bin ~/.openclaw/extensions
cp bin/codex-profile-manager.py ~/.local/bin/codex-profile-manager.py
chmod 700 ~/.local/bin/codex-profile-manager.py
cp -R plugin ~/.openclaw/extensions/openclaw-codex-profile-switcher
```

Затем нужно включить extension в конфиге OpenClaw и разрешить нужные плагины:

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

Точная форма конфига может отличаться в зависимости от установки OpenClaw.

## Команды

```text
/gptprof
/gptprof status
/gptprof add
/gptprof check
/gptprof use-native
/gptprof switch <slug>
```

CLI-менеджер можно использовать напрямую:

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

Smoke test проверяет синтаксис JavaScript, синтаксис Python и очевидные паттерны случайно закоммиченных токенов.

## Чего этот скилл не делает

- Не обходит лимиты OpenAI.
- Не создаёт платные аккаунты.
- Не хранит credentials в Git.
- Не гарантирует, что OpenAI/ChatGPT примет любой аккаунт или любую device authorization попытку.
- Не заменяет auth-модель OpenClaw, а только управляет локальными profile-файлами и route config.
