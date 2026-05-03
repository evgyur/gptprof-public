# gptprof-public

Sanitized public OpenClaw skill/plugin for managing OpenAI Codex OAuth profiles and forcing GPT traffic onto native Codex runtime.

## Install

```bash
mkdir -p ~/.local/bin ~/.openclaw/extensions
cp bin/codex-profile-manager.py ~/.local/bin/codex-profile-manager.py
chmod 700 ~/.local/bin/codex-profile-manager.py
cp -R plugin ~/.openclaw/extensions/openclaw-codex-profile-switcher
```

Then enable the extension in OpenClaw config and allow the `codex-profile-switcher` and `codex` plugins.

## Commands

```text
/gptprof
/gptprof add
/gptprof check
/gptprof use-native
/gptprof switch <slug>
```

## Public safety

No OAuth tokens are stored in this repository. Tokens are read/written only at runtime in the user's home directory.
