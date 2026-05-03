---
name: gptprof-public
description: Public sanitized GPT profile manager for OpenClaw: switch OpenAI Codex OAuth profiles and enforce native Codex runtime routing without storing secrets in the skill.
user-invocable: true
disable-model-invocation: true
command-dispatch: tool
command-tool: gptprof
command-arg-mode: raw
---

# gptprof-public

Manage local OpenAI Codex OAuth profiles for OpenClaw and keep GPT models on the native Codex runtime.

## What it does

- `/gptprof` or `/gptprof status` shows the active profile and route status.
- `/gptprof add` starts OpenAI device authorization.
- `/gptprof check` completes pending device authorization after the user approves it.
- `/gptprof use-native` sets `agents.defaults.model.primary` to `openai/gpt-5.5` and `agents.defaults.agentRuntime.id` to `codex`.
- `/gptprof switch <slug>` switches to an existing local profile.

## Important routing distinction

Auth records use provider `openai-codex` because the OAuth token is for ChatGPT/Codex auth.
Execution should use native Codex routing:

- model: `openai/*`, for example `openai/gpt-5.5`
- runtime: `agentRuntime.id = "codex"`

A legacy `openai-codex/*` model on Pi runtime is detected as a legacy/fallback route and reported as `needs native Codex`.

## Secret policy

This public skill contains no tokens and should never commit tokens.
Runtime secrets stay in user-local files only:

- `~/.codex/auth.json`
- `~/.openclaw/codex-profiles/*/auth.json`
- `~/.openclaw/agents/*/agent/auth-*.json`

The OAuth client id in the manager is public application metadata, not a client secret.
