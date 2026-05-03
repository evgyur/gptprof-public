#!/usr/bin/env python3
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
OPENCLAW = HOME / ".openclaw"
POOL = OPENCLAW / "codex-profiles"
STATE_PATH = POOL / "state.json"
CODEX_AUTH = HOME / ".codex" / "auth.json"
CODEX_HOME_AUTH = OPENCLAW / "codex-home" / "auth.json"
AGENTS = OPENCLAW / "agents"
BACKUPS = OPENCLAW / "backups"
OPENCLAW_CONFIG = OPENCLAW / "openclaw.json"
AUTH_BASE_URL = "https://auth.openai.com"
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_SCOPE = "openid profile email offline_access"
USAGE_BASE_URL = "https://chatgpt.com/backend-api/wham/usage"
DEVICE_CALLBACK_URL = f"{AUTH_BASE_URL}/deviceauth/callback"
DEVICE_VERIFY_URL = f"{AUTH_BASE_URL}/codex/device"
DEVICE_TIMEOUT_SECONDS = 15 * 60
REFRESH_AFTER_DAYS = 8
SWITCH_THRESHOLD = 95.0
DEFAULT_NATIVE_MODEL = "openai/gpt-5.5"
NATIVE_MODEL_ALIASES = {
    "openai/gpt-5.5": "gptt",
    "openai/gpt-5.4-mini": "gptm",
}
LEGACY_PI_ALIASES = {
    "openai-codex/gpt-5.5": "gptt-pi",
    "openai-codex/gpt-5.4-mini": "gptm-pi",
}

PERMANENT_REFRESH_CODES = {
    "invalid_grant", "invalid_request", "invalid_client", "unauthorized_client",
    "unsupported_grant_type", "invalid_refresh_token", "consent_required",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json_atomic(path, data, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=False)
            f.write("\n")
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def b64url_json(token):
    try:
        part = token.split(".")[1]
        part += "=" * ((4 - len(part) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode("ascii")))
    except Exception:
        return {}


def auth_email(auth):
    email = auth.get("email")
    if isinstance(email, str) and "@" in email:
        return email.lower()
    tokens = auth.get("tokens") or {}
    for key in ("id_token", "access_token"):
        claims = b64url_json(str(tokens.get(key) or ""))
        email = claims.get("email")
        if isinstance(email, str) and "@" in email:
            return email.lower()
    return None


def slug_for_email(email):
    return email.split("@", 1)[0].strip().lower().replace(" ", "-")


def profile_dir(slug):
    return POOL / slug


def profile_auth_path(slug):
    return profile_dir(slug) / "auth.json"


def load_state():
    state = load_json(STATE_PATH, {}) or {}
    if not isinstance(state, dict):
        state = {}
    state.setdefault("active", None)
    state.setdefault("history", [])
    state.setdefault("cooldowns", {})
    return state


def save_state(state):
    write_json_atomic(STATE_PATH, state)


def list_profiles():
    POOL.mkdir(parents=True, exist_ok=True)
    state = load_state()
    profiles = []
    for p in sorted(POOL.iterdir()):
        if not p.is_dir():
            continue
        auth_path = p / "auth.json"
        auth = load_json(auth_path, None)
        if not isinstance(auth, dict):
            continue
        email = auth_email(auth) or "unknown"
        tokens = auth.get("tokens") or {}
        claims = b64url_json(str(tokens.get("access_token") or tokens.get("id_token") or ""))
        exp = claims.get("exp")
        profiles.append({
            "slug": p.name,
            "email": email,
            "active": state.get("active") == p.name,
            "expiresAt": int(exp) if isinstance(exp, (int, float)) else None,
            "lastRefresh": auth.get("last_refresh"),
            "hasRefreshToken": bool(tokens.get("refresh_token")),
            "cooldownUntil": (state.get("cooldowns") or {}).get(p.name),
        })
    return profiles


def native_route_status():
    cfg = load_json(OPENCLAW_CONFIG, {}) or {}
    agents = cfg.get("agents") if isinstance(cfg.get("agents"), dict) else {}
    defaults = agents.get("defaults") if isinstance(agents.get("defaults"), dict) else {}
    model = defaults.get("model") if isinstance(defaults.get("model"), dict) else {}
    runtime = defaults.get("agentRuntime") if isinstance(defaults.get("agentRuntime"), dict) else {}
    plugins = cfg.get("plugins") if isinstance(cfg.get("plugins"), dict) else {}
    allow = plugins.get("allow") if isinstance(plugins.get("allow"), list) else []
    entries = plugins.get("entries") if isinstance(plugins.get("entries"), dict) else {}
    codex_entry = entries.get("codex") if isinstance(entries.get("codex"), dict) else {}
    primary = model.get("primary") if isinstance(model.get("primary"), str) else None
    runtime_id = runtime.get("id") if isinstance(runtime.get("id"), str) else None
    runtime_fallback = runtime.get("fallback") if isinstance(runtime.get("fallback"), str) else None
    auth_provider = "openai-codex"
    legacy_pi_route = isinstance(primary, str) and primary.startswith("openai-codex/") and runtime_id != "codex"
    ok = (
        isinstance(primary, str)
        and primary.startswith("openai/")
        and runtime_id == "codex"
        and "codex" in allow
        and codex_entry.get("enabled") is True
    )
    needs = []
    if not isinstance(primary, str) or not primary.startswith("openai/"):
        needs.append("model.primary must be openai/* for native Codex runtime")
    if runtime_id != "codex":
        needs.append("agentRuntime.id must be codex")
    if "codex" not in allow:
        needs.append("plugins.allow must include codex")
    if codex_entry.get("enabled") is not True:
        needs.append("plugins.entries.codex.enabled must be true")
    return {
        "ok": ok,
        "primaryModel": primary,
        "agentRuntime": runtime,
        "codexAllowed": "codex" in allow,
        "codexPluginEnabled": codex_entry.get("enabled") is True,
        "fallback": runtime_fallback,
        "authProvider": auth_provider,
        "expectedModelPrefix": "openai/",
        "expectedRuntime": "codex",
        "legacyPiRoute": legacy_pi_route,
        "needs": needs,
    }


def ensure_native_codex_route(model=None, reason="manual"):
    model = (model or DEFAULT_NATIVE_MODEL).strip()
    if not model.startswith("openai/"):
        raise RuntimeError("native Codex route requires an openai/* model ref")
    cfg = load_json(OPENCLAW_CONFIG, {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path(OPENCLAW_CONFIG, stamp)

    plugins = cfg.setdefault("plugins", {})
    if not isinstance(plugins, dict):
        plugins = {}
        cfg["plugins"] = plugins
    allow = plugins.get("allow")
    if not isinstance(allow, list):
        allow = []
    for plugin_id in ("openai", "codex", "codex-profile-switcher"):
        if plugin_id not in allow:
            allow.append(plugin_id)
    plugins["allow"] = allow
    entries = plugins.get("entries")
    if not isinstance(entries, dict):
        entries = {}
    entries.setdefault("openai", {})
    if isinstance(entries["openai"], dict):
        entries["openai"]["enabled"] = True
    entries.setdefault("codex", {})
    if isinstance(entries["codex"], dict):
        entries["codex"]["enabled"] = True
    plugins["entries"] = entries

    agents = cfg.setdefault("agents", {})
    if not isinstance(agents, dict):
        agents = {}
        cfg["agents"] = agents
    defaults = agents.setdefault("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
        agents["defaults"] = defaults
    default_model = defaults.get("model")
    if not isinstance(default_model, dict):
        default_model = {}
    previous_fallbacks = default_model.get("fallbacks")
    default_model["primary"] = model
    if isinstance(previous_fallbacks, list) and previous_fallbacks:
        default_model["fallbacks"] = []
    defaults["model"] = default_model
    defaults["agentRuntime"] = {"id": "codex", "fallback": "none"}

    models = defaults.get("models")
    if not isinstance(models, dict):
        models = {}
    native_entry = models.get(model)
    if not isinstance(native_entry, dict):
        native_entry = {}
    if model in NATIVE_MODEL_ALIASES:
        native_entry["alias"] = NATIVE_MODEL_ALIASES[model]
    models[model] = native_entry
    for legacy_model, alias in LEGACY_PI_ALIASES.items():
        legacy_entry = models.get(legacy_model)
        if isinstance(legacy_entry, dict):
            legacy_entry["alias"] = alias
    defaults["models"] = models

    write_json_atomic(OPENCLAW_CONFIG, cfg, mode=0o600)
    state = load_state()
    hist = state.get("routeHistory") if isinstance(state.get("routeHistory"), list) else []
    hist.append({"at": now_iso(), "model": model, "reason": reason})
    state["routeHistory"] = hist[-100:]
    native_route = {"model": model, "updatedAt": now_iso()}
    if isinstance(previous_fallbacks, list) and previous_fallbacks:
        native_route["previousFallbacks"] = previous_fallbacks
    state["nativeRoute"] = native_route
    save_state(state)
    return {"ok": True, "model": model, "status": native_route_status(), "backupStamp": stamp}


def backup_path(path, stamp):
    rel = str(Path(path).expanduser()).replace(str(HOME), "home-chip", 1).strip("/").replace("/", "__")
    dst = BACKUPS / f"codex-profile-switcher-{stamp}" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if Path(path).is_symlink():
        dst.write_text("SYMLINK -> " + os.readlink(path), encoding="utf-8")
    elif Path(path).exists():
        shutil.copy2(path, dst)


def ensure_seed_current():
    auth = load_json(CODEX_AUTH, None)
    if not isinstance(auth, dict):
        return None
    email = auth_email(auth)
    if not email:
        return None
    slug = slug_for_email(email)
    dst = profile_auth_path(slug)
    if not dst.exists():
        data = dict(auth)
        data.setdefault("email", email)
        data.setdefault("profile_slug", slug)
        data.setdefault("seeded_at", now_iso())
        write_json_atomic(dst, data)
    state = load_state()
    if not state.get("active"):
        state["active"] = slug
        state["updatedAt"] = now_iso()
        save_state(state)
    return slug


def token_exp_ms(auth):
    tokens = auth.get("tokens") or {}
    claims = b64url_json(str(tokens.get("access_token") or tokens.get("id_token") or ""))
    exp = claims.get("exp")
    return int(exp * 1000) if isinstance(exp, (int, float)) else None


def openclaw_profile_record(auth):
    email = auth_email(auth)
    if not email:
        raise RuntimeError("auth has no email")
    tokens = auth.get("tokens") or {}
    access = tokens.get("access_token") or tokens.get("id_token")
    refresh = tokens.get("refresh_token")
    if not access or not refresh:
        raise RuntimeError("auth is missing required OpenAI Codex tokens")
    claims = b64url_json(str(access or ""))
    auth_claims = claims.get("https://api.openai.com/auth") if isinstance(claims.get("https://api.openai.com/auth"), dict) else {}
    record = {
        "type": "oauth",
        "provider": "openai-codex",
        "access": access,
        "refresh": refresh,
        "email": email,
    }
    account_id = auth_claims.get("chatgpt_account_id")
    plan_type = auth_claims.get("chatgpt_plan_type")
    if isinstance(account_id, str) and account_id.strip():
        record["accountId"] = account_id.strip()
    if isinstance(plan_type, str) and plan_type.strip():
        record["planType"] = plan_type.strip()
        record["chatgptPlanType"] = plan_type.strip()
    expires = token_exp_ms(auth)
    if expires:
        record["expires"] = expires
    return email, f"openai-codex:{email}", record


def update_agent_auth(auth, stamp):
    email, profile_id, record = openclaw_profile_record(auth)
    changed = {"authProfiles": 0, "authState": 0, "sessions": 0}
    if not AGENTS.exists():
        return changed
    for agent_dir in sorted(p for p in AGENTS.iterdir() if p.is_dir()):
        ap = agent_dir / "agent" / "auth-profiles.json"
        if ap.exists():
            data = load_json(ap, {}) or {}
            if not isinstance(data, dict):
                data = {}
            profiles = data.get("profiles") if isinstance(data.get("profiles"), dict) else {}
            profiles = {k: v for k, v in profiles.items() if not str(k).startswith("openai-codex:")}
            profiles[profile_id] = record
            data["version"] = data.get("version") or 1
            data["profiles"] = profiles
            defaults = data.get("defaults") if isinstance(data.get("defaults"), dict) else {}
            defaults["openai-codex"] = profile_id
            data["defaults"] = defaults
            backup_path(ap, stamp)
            write_json_atomic(ap, data)
            changed["authProfiles"] += 1
        asp = agent_dir / "agent" / "auth-state.json"
        if asp.exists():
            data = load_json(asp, {}) or {}
            if not isinstance(data, dict):
                data = {}
            order = data.get("order") if isinstance(data.get("order"), dict) else {}
            last = data.get("lastGood") if isinstance(data.get("lastGood"), dict) else {}
            order["openai-codex"] = [profile_id]
            last["openai-codex"] = profile_id
            data["order"] = order
            data["lastGood"] = last
            usage = data.get("usageStats")
            if isinstance(usage, dict):
                data["usageStats"] = {k: v for k, v in usage.items() if not str(k).startswith("openai-codex:") or k == profile_id}
            backup_path(asp, stamp)
            write_json_atomic(asp, data)
            changed["authState"] += 1
        sp = agent_dir / "sessions" / "sessions.json"
        if sp.exists():
            data = load_json(sp, {})
            dirty = False
            if isinstance(data, dict):
                for session in data.values():
                    if not isinstance(session, dict):
                        continue
                    current = session.get("authProfileOverride")
                    if current is None or str(current).startswith("openai-codex:"):
                        if session.get("authProfileOverride") != profile_id:
                            session["authProfileOverride"] = profile_id
                            session["authProfileOverrideSource"] = "codex-profile-switcher"
                            dirty = True
            if dirty:
                backup_path(sp, stamp)
                write_json_atomic(sp, data)
                changed["sessions"] += 1
    return changed


def switch_profile(slug, reason="manual"):
    ensure_seed_current()
    slug = slug.strip().lower()
    auth_path = profile_auth_path(slug)
    auth = load_json(auth_path, None)
    if not isinstance(auth, dict):
        raise RuntimeError(f"profile not found: {slug}")
    email = auth_email(auth)
    if not email:
        raise RuntimeError(f"profile has no email: {slug}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_path(CODEX_AUTH, stamp)
    write_json_atomic(CODEX_AUTH, auth)
    CODEX_HOME_AUTH.parent.mkdir(parents=True, exist_ok=True)
    if CODEX_HOME_AUTH.exists() or CODEX_HOME_AUTH.is_symlink():
        backup_path(CODEX_HOME_AUTH, stamp)
        if CODEX_HOME_AUTH.is_dir() and not CODEX_HOME_AUTH.is_symlink():
            raise RuntimeError(f"refusing to replace directory: {CODEX_HOME_AUTH}")
        CODEX_HOME_AUTH.unlink()
    os.symlink(str(CODEX_AUTH), str(CODEX_HOME_AUTH))
    changed = update_agent_auth(auth, stamp)
    state = load_state()
    old = state.get("active")
    state["active"] = slug
    state["updatedAt"] = now_iso()
    hist = state.get("history") if isinstance(state.get("history"), list) else []
    hist.append({"at": now_iso(), "from": old, "to": slug, "reason": reason})
    state["history"] = hist[-100:]
    save_state(state)
    route = ensure_native_codex_route(reason=f"profile-switch:{reason}")
    return {"ok": True, "active": slug, "email": email, "profileId": f"openai-codex:{email}", "changed": changed, "backupStamp": stamp, "route": route}


def http_json(url, payload=None, headers=None, timeout=20):
    data = None
    method = "GET"
    req_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body) if body else {}
        except Exception:
            parsed = {"error": {"message": body[:500]}}
        return e.code, parsed


def device_headers(content_type):
    headers = {
        "Content-Type": content_type,
        "originator": "openclaw",
        "User-Agent": "openclaw-codexprofile",
    }
    return headers


def device_start():
    status, payload = http_json(
        f"{AUTH_BASE_URL}/api/accounts/deviceauth/usercode",
        {"client_id": OAUTH_CLIENT_ID},
        headers=device_headers("application/json"),
        timeout=20,
    )
    if status >= 400:
        code, msg = extract_error(payload)
        raise RuntimeError(msg or code or f"device_code_http_{status}")
    device_auth_id = payload.get("device_auth_id")
    user_code = payload.get("user_code") or payload.get("usercode")
    if not isinstance(device_auth_id, str) or not device_auth_id or not isinstance(user_code, str) or not user_code:
        raise RuntimeError("OpenAI device code response was missing device_auth_id or user_code")
    interval = payload.get("interval")
    interval_seconds = int(interval) if isinstance(interval, (int, float)) and interval > 0 else 5
    state = load_state()
    state["pendingDeviceAuth"] = {
        "deviceAuthId": device_auth_id,
        "userCode": user_code,
        "verificationUrl": DEVICE_VERIFY_URL,
        "createdAt": now_iso(),
        "expiresAt": int(time.time()) + DEVICE_TIMEOUT_SECONDS,
        "intervalSeconds": interval_seconds,
    }
    save_state(state)
    return {
        "ok": True,
        "verificationUrl": DEVICE_VERIFY_URL,
        "userCode": user_code,
        "expiresInSeconds": DEVICE_TIMEOUT_SECONDS,
        "intervalSeconds": interval_seconds,
    }


def device_check():
    state = load_state()
    pending = state.get("pendingDeviceAuth") if isinstance(state.get("pendingDeviceAuth"), dict) else None
    if not pending:
        return {"ok": False, "pending": False, "error": "no_pending_device_auth"}
    expires_at = pending.get("expiresAt")
    if isinstance(expires_at, int) and time.time() > expires_at:
        state.pop("pendingDeviceAuth", None)
        save_state(state)
        return {"ok": False, "pending": False, "error": "device_auth_expired"}
    status, payload = http_json(
        f"{AUTH_BASE_URL}/api/accounts/deviceauth/token",
        {"device_auth_id": pending.get("deviceAuthId"), "user_code": pending.get("userCode")},
        headers=device_headers("application/json"),
        timeout=20,
    )
    if status in (403, 404):
        return {
            "ok": True,
            "pending": True,
            "verificationUrl": pending.get("verificationUrl"),
            "userCode": pending.get("userCode"),
            "expiresAt": pending.get("expiresAt"),
        }
    if status >= 400:
        code, msg = extract_error(payload)
        return {"ok": False, "pending": False, "error": code or f"http_{status}", "message": msg}
    authorization_code = payload.get("authorization_code")
    code_verifier = payload.get("code_verifier")
    if not isinstance(authorization_code, str) or not authorization_code or not isinstance(code_verifier, str) or not code_verifier:
        return {"ok": False, "pending": False, "error": "missing_authorization_code"}
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": authorization_code,
        "redirect_uri": DEVICE_CALLBACK_URL,
        "client_id": OAUTH_CLIENT_ID,
        "code_verifier": code_verifier,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{AUTH_BASE_URL}/oauth/token",
        data=form,
        headers=device_headers("application/x-www-form-urlencoded"),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token_payload = json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"OpenAI token exchange failed: HTTP {e.code} {body[:300]}")
    access = token_payload.get("access_token")
    refresh = token_payload.get("refresh_token")
    if not isinstance(access, str) or not access or not isinstance(refresh, str) or not refresh:
        raise RuntimeError("OpenAI token exchange succeeded without required tokens")
    auth = {
        "auth_mode": "chatgpt",
        "OPENAI_API_KEY": "",
        "tokens": {
            "access_token": access,
            "refresh_token": refresh,
        },
        "seeded_at": now_iso(),
        "last_refresh": now_iso(),
    }
    if isinstance(token_payload.get("id_token"), str) and token_payload["id_token"]:
        auth["tokens"]["id_token"] = token_payload["id_token"]
    email = auth_email(auth)
    if not email:
        raise RuntimeError("OpenAI device auth succeeded but no email claim was available")
    slug = slug_for_email(email)
    auth["email"] = email
    auth["profile_slug"] = slug
    write_json_atomic(profile_auth_path(slug), auth)
    state.pop("pendingDeviceAuth", None)
    save_state(state)
    switched = switch_profile(slug, reason="device-auth")
    return {"ok": True, "pending": False, "active": slug, "email": email, "switch": switched}


def extract_error(payload):
    err = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(err, dict):
        return err.get("code") or err.get("error") or payload.get("code") or f"http_error", err.get("message") or err.get("error_description")
    if isinstance(err, str):
        return err, payload.get("error_description") or err
    return payload.get("code") if isinstance(payload, dict) else None, payload.get("message") if isinstance(payload, dict) else None


def refresh_one(slug, force=False):
    auth_path = profile_auth_path(slug)
    auth = load_json(auth_path, None)
    if not isinstance(auth, dict):
        return {"slug": slug, "ok": False, "error": "profile_not_found"}
    last = auth.get("last_refresh")
    if not force and last:
        try:
            dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - dt).total_seconds() < REFRESH_AFTER_DAYS * 86400:
                return {"slug": slug, "ok": True, "skipped": True, "reason": "fresh"}
        except Exception:
            pass
    token = (auth.get("tokens") or {}).get("refresh_token")
    if not token:
        return {"slug": slug, "ok": False, "error": "missing_refresh_token"}
    status, payload = http_json(f"{AUTH_BASE_URL}/oauth/token", {
        "grant_type": "refresh_token",
        "client_id": OAUTH_CLIENT_ID,
        "refresh_token": token,
        "scope": OAUTH_SCOPE,
    }, timeout=30)
    if status >= 400:
        code, msg = extract_error(payload)
        return {"slug": slug, "ok": False, "error": code or f"http_{status}", "permanent": (code in PERMANENT_REFRESH_CODES), "message": msg}
    tokens = auth.setdefault("tokens", {})
    for k in ("access_token", "refresh_token", "id_token"):
        if payload.get(k):
            tokens[k] = payload[k]
    email = auth_email(auth)
    if email:
        auth["email"] = email
    auth["last_refresh"] = now_iso()
    auth["profile_slug"] = slug
    write_json_atomic(auth_path, auth)
    state = load_state()
    if state.get("active") == slug:
        switch_profile(slug, reason="refresh-active")
    return {"slug": slug, "ok": True, "email": auth.get("email"), "expiresAt": token_exp_ms(auth)}


def fetch_usage(slug):
    auth = load_json(profile_auth_path(slug), None)
    if not isinstance(auth, dict):
        return {"slug": slug, "ok": False, "error": "profile_not_found"}
    tokens = auth.get("tokens") or {}
    token = tokens.get("access_token") or tokens.get("id_token")
    if not token:
        return {"slug": slug, "ok": False, "error": "missing_access_token"}
    claims = b64url_json(str(tokens.get("id_token") or ""))
    account_id = ((claims.get("https://api.openai.com/auth") or {}).get("chatgpt_account_id") or claims.get("chatgpt_account_id"))
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if account_id and not str(account_id).startswith(("email_", "local_")):
        headers["chatgpt-account-id"] = str(account_id)
    status, payload = http_json(USAGE_BASE_URL, None, headers=headers, timeout=20)
    if status >= 400:
        code, msg = extract_error(payload)
        return {"slug": slug, "ok": False, "error": code or f"http_{status}", "message": msg}
    rl = payload.get("rate_limit") if isinstance(payload, dict) else {}
    primary = (rl or {}).get("primary_window") or {}
    secondary = (rl or {}).get("secondary_window") or {}
    return {"slug": slug, "ok": True, "primaryUsed": primary.get("used_percent"), "primaryResetAt": primary.get("reset_at"), "primaryWindowSeconds": primary.get("limit_window_seconds"), "secondaryUsed": secondary.get("used_percent"), "secondaryResetAt": secondary.get("reset_at"), "planType": payload.get("plan_type")}


def autoswitch():
    ensure_seed_current()
    state = load_state()
    active = state.get("active")
    profiles = [p["slug"] for p in list_profiles()]
    if not active or active not in profiles:
        return {"ok": False, "error": "no_active_profile", "profiles": profiles}
    active_usage = fetch_usage(active)
    if not active_usage.get("ok"):
        return {"ok": False, "active": active, "usage": active_usage}
    primary = active_usage.get("primaryUsed")
    secondary = active_usage.get("secondaryUsed")
    if not ((isinstance(primary, (int, float)) and primary >= SWITCH_THRESHOLD) or (isinstance(secondary, (int, float)) and secondary >= SWITCH_THRESHOLD)):
        return {"ok": True, "switched": False, "active": active, "usage": active_usage}
    checked = []
    for slug in profiles:
        if slug == active:
            continue
        refresh_one(slug, force=False)
        usage = fetch_usage(slug)
        checked.append(usage)
        if usage.get("ok") and (usage.get("primaryUsed") is None or usage.get("primaryUsed") < SWITCH_THRESHOLD) and (usage.get("secondaryUsed") is None or usage.get("secondaryUsed") < SWITCH_THRESHOLD):
            result = switch_profile(slug, reason="autoswitch-usage-95")
            return {"ok": True, "switched": True, "from": active, "to": slug, "activeUsage": active_usage, "candidateUsage": usage, "switch": result}
    return {"ok": True, "switched": False, "active": active, "reason": "no_healthy_candidate", "usage": active_usage, "checked": checked}


def restart_gateway(delay=1):
    cmd = f"sleep {int(delay)}; systemctl --user restart openclaw-gateway.service"
    subprocess.Popen(["bash", "-lc", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return {"scheduled": True, "delaySeconds": delay}


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-current")
    sub.add_parser("status")
    lp = sub.add_parser("list")
    sw = sub.add_parser("switch"); sw.add_argument("slug"); sw.add_argument("--restart", action="store_true")
    ref = sub.add_parser("refresh"); ref.add_argument("--all", action="store_true"); ref.add_argument("--slug"); ref.add_argument("--force", action="store_true")
    sub.add_parser("usage")
    sub.add_parser("autoswitch")
    route = sub.add_parser("apply-native-route"); route.add_argument("--model", default=DEFAULT_NATIVE_MODEL)
    sub.add_parser("device-start")
    sub.add_parser("device-check")
    args = parser.parse_args()
    try:
        if args.cmd == "seed-current":
            out = {"ok": True, "seeded": ensure_seed_current()}
        elif args.cmd in ("status", "list"):
            ensure_seed_current()
            state = load_state()
            out = {
                "ok": True,
                "active": state.get("active"),
                "profiles": list_profiles(),
                "route": native_route_status(),
                "pendingDeviceAuth": state.get("pendingDeviceAuth") if isinstance(state.get("pendingDeviceAuth"), dict) else None,
            }
        elif args.cmd == "switch":
            out = switch_profile(args.slug, reason="manual")
            if args.restart:
                out["restart"] = restart_gateway(1)
        elif args.cmd == "refresh":
            ensure_seed_current()
            slugs = [args.slug] if args.slug else [p["slug"] for p in list_profiles()]
            if not args.all and not args.slug:
                state = load_state(); slugs = [state.get("active")] if state.get("active") else []
            out = {"ok": True, "results": [refresh_one(s, force=args.force) for s in slugs if s]}
        elif args.cmd == "usage":
            ensure_seed_current()
            out = {"ok": True, "results": [fetch_usage(p["slug"]) for p in list_profiles()]}
        elif args.cmd == "autoswitch":
            out = autoswitch()
        elif args.cmd == "apply-native-route":
            out = ensure_native_codex_route(model=args.model, reason="manual")
        elif args.cmd == "device-start":
            out = device_start()
        elif args.cmd == "device-check":
            out = device_check()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2), file=sys.stdout)
        sys.exit(1)

if __name__ == "__main__":
    main()
