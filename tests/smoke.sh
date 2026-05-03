#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
node --check "$ROOT/plugin/index.js"
python3 -m py_compile "$ROOT/bin/codex-profile-manager.py"
if grep -RInE '(gho_[A-Za-z0-9_]+|sk-[A-Za-z0-9]|refresh_token"\s*:\s*"[^"]+|access_token"\s*:\s*"[^"]+)' "$ROOT" \
  --exclude-dir=.git --exclude=smoke.sh; then
  echo "Potential secret found" >&2
  exit 1
fi
echo "gptprof-public smoke: ok"
