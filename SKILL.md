---
name: gptprof-public
description: Public sanitized GPT profile manager for OpenClaw: switch OpenAI Codex OAuth profiles, show usage, keep the safe Pi route, and optionally try the native Codex runtime without storing secrets in the skill.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: gptprof
command-arg-mode: raw
---

# gptprof-public

Manage local OpenAI Codex OAuth profiles for OpenClaw, keep the safe OpenAI-Codex Pi route available, and optionally switch to the native Codex runtime route.

## What It Does

- `/gptprof` or `/gptprof status` shows the active profile, plan badge when available, route status, cached usage, and Telegram profile buttons.
- `/gptprof add` starts OpenAI device authorization.
- `/gptprof check` completes pending device authorization after the user approves it.
- `/gptprof refresh` refreshes usage cache on demand.
- `/gptprof autoswitch` switches only when the active profile is at or above the 95% usage threshold and a healthy spare profile is below threshold; Telegram plugin also checks autoswitch before ordinary dispatch and schedules a gateway restart after a real switch so all agent sessions reload auth.
- `/gptprof use-pi` sets `agents.defaults.model.primary` to `openai-codex/gpt-5.5` and `agents.defaults.agentRuntime.id` to `pi`.
- `/gptprof try-codex` or `/gptprof use-native` sets `agents.defaults.model.primary` to `openai/gpt-5.5` and `agents.defaults.agentRuntime.id` to `codex`.
- `/gptprof switch <slug>` switches to an existing local profile unless the selected profile is already over the autoswitch threshold.
- `/gptt` patches the current session to `openai-codex/gpt-5.5` with the active gptprof auth profile, medium thinking, and fast mode.
- `/gptpro` patches the current session to `openai/gpt-5.5-pro` with high thinking and fast mode off.

## Important Routing Distinction

Auth records use provider `openai-codex` because the OAuth token is for ChatGPT/Codex auth.
The safe fallback route is:

- model: `openai-codex/gpt-5.5`
- runtime: `agentRuntime.id = "pi"`

The native Codex trial route is:

- model: `openai/gpt-5.5`
- runtime: `agentRuntime.id = "codex"`

On OpenClaw `2026.5.3-beta.2` and newer, do not write `agents.defaults.agentRuntime.fallback`; config validation rejects that key for these routes.

## Telegram Buttons

Buttons should be native Telegram rows:

```json
[[{"text":"✓ profile 42%","callback_data":"gptprof:profile"}]]
```

Do not use abstract `{label,value}` buttons, do not include `style`, and do not pass a flat button list in this OpenClaw delivery path.

## Secret Policy

This public skill contains no tokens and should never commit tokens.
Runtime secrets stay in user-local files only:

- `~/.codex/auth.json`
- `~/.openclaw/codex-profiles/*/auth.json`
- `~/.openclaw/agents/*/agent/auth-*.json`

The OAuth client id in the manager is public application metadata, not a client secret.

Session alias handling writes only the current OpenClaw session store entry and creates a timestamped backup before changing model override fields.
