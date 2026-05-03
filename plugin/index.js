import { spawn } from "node:child_process";
const Type = {
  String: (options = {}) => ({ type: "string", ...options }),
  Optional: (schema) => ({ ...schema, optional: true }),
  Object: (properties = {}, options = {}) => {
    const required = Object.entries(properties)
      .filter(([, schema]) => !schema?.optional)
      .map(([key]) => key);
    const cleanProperties = Object.fromEntries(
      Object.entries(properties).map(([key, schema]) => {
        const { optional, ...rest } = schema || {};
        return [key, rest];
      }),
    );
    return {
      type: "object",
      properties: cleanProperties,
      ...(required.length ? { required } : {}),
      ...options,
    };
  },
};

const DEFAULT_MANAGER_CANDIDATES = [
  process.env.GPTPROF_MANAGER_PATH,
  process.env.CODEX_PROFILE_MANAGER,
  `${process.env.HOME || ""}/.local/bin/codex-profile-manager.py`,
  "/usr/local/bin/codex-profile-manager.py",
].filter(Boolean);
const DEFAULT_PYTHON = process.env.GPTPROF_PYTHON || "python3";
const DEFAULT_TIMEOUT_MS = 12_000;

function asObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function getConfig(api) {
  const config = asObject(api?.config);
  const managerPath = typeof config.managerPath === "string" && config.managerPath.trim()
    ? config.managerPath.trim()
    : DEFAULT_MANAGER_CANDIDATES[0];
  return {
    enabled: config.enabled !== false,
    managerPath,
    pythonCommand: typeof config.pythonCommand === "string" && config.pythonCommand.trim() ? config.pythonCommand.trim() : DEFAULT_PYTHON,
    timeoutMs: Number.isFinite(config.timeoutMs) && config.timeoutMs > 0 ? Math.min(Number(config.timeoutMs), 120_000) : DEFAULT_TIMEOUT_MS,
    restartAfterSwitch: config.restartAfterSwitch !== false,
  };
}

function textResult(text, details) {
  return {
    content: [{ type: "text", text }],
    details,
  };
}

function runManager(config, args) {
  return new Promise((resolve) => {
    const child = spawn(config.pythonCommand, [config.managerPath, ...args], { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    let settled = false;
    const settle = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ...result, stdout, stderr });
    };
    const timer = setTimeout(() => {
      child.kill("SIGTERM");
      settle({ code: null, timedOut: true });
    }, config.timeoutMs);
    child.stdout.on("data", (chunk) => {
      stdout += String(chunk);
      if (stdout.length > 256_000) stdout = stdout.slice(-256_000);
    });
    child.stderr.on("data", (chunk) => {
      stderr += String(chunk);
      if (stderr.length > 32_000) stderr = stderr.slice(-32_000);
    });
    child.on("error", (error) => {
      stderr += String(error);
      settle({ code: null, timedOut: false });
    });
    child.on("close", (code) => settle({ code, timedOut: false }));
  });
}

function parseJson(text) {
  try {
    const parsed = JSON.parse(text);
    return asObject(parsed);
  } catch {
    return {};
  }
}

async function managerJson(config, args) {
  const result = await runManager(config, args);
  const payload = parseJson(result.stdout);
  if (result.code !== 0 || result.timedOut || payload.ok === false) {
    const reason = payload.error || (result.timedOut ? "manager timed out" : result.stderr || "manager failed");
    return { ok: false, error: String(reason).slice(0, 800), payload };
  }
  return payload;
}

function profileButtons(status) {
  const profiles = Array.isArray(status.profiles) ? status.profiles : [];
  const buttons = profiles.map((profile) => ({
    label: profile.active ? `* ${profile.slug}` : profile.slug,
    value: `gptprof:${profile.slug}`,
    style: profile.active ? "success" : "secondary",
  }));
  buttons.push({
    label: "+ Add profile",
    value: "gptprof:device-start",
    style: "primary",
  });
  buttons.push({
    label: "Check auth",
    value: "gptprof:device-check",
    style: "secondary",
  });
  if (!status?.route?.ok) {
    buttons.push({
      label: "Use native Codex",
      value: "gptprof:route-native",
      style: "warning",
    });
  }
  return buttons;
}

function statusText(status) {
  const profiles = Array.isArray(status.profiles) ? status.profiles : [];
  const route = asObject(status.route);
  const runtimeId = route.agentRuntime?.id || "pi";
  const routeLine = route.ok
    ? `Route: native Codex (${route.primaryModel}, runtime=codex)`
    : `Route: needs native Codex runtime (current model=${route.primaryModel || "none"}, runtime=${runtimeId}). OAuth provider stays openai-codex; model route should be openai/* + runtime=codex.`;
  const rows = profiles.map((profile) => {
    const marker = profile.active ? "*" : " ";
    const email = profile.email || "unknown";
    const exp = profile.expiresAt ? new Date(profile.expiresAt * 1000).toISOString().slice(0, 10) : "unknown exp";
    const refresh = profile.hasRefreshToken ? "refresh ok" : "no refresh token";
    return `${marker} ${profile.slug} (${email}, ${exp}, ${refresh})`;
  });
  const pending = status.pendingDeviceAuth
    ? "\n\nDevice auth pending. Open the auth link/code from the previous message, then press Check auth."
    : "";
  return `GPT profile: ${status.active || "none"}\n${routeLine}\n\n${rows.length ? rows.join("\n") : "No profiles found in ~/.openclaw/codex-profiles."}${pending}`;
}

function scheduleRestart() {
  const child = spawn("bash", ["-lc", "sleep 1; systemctl --user restart openclaw-gateway.service"], {
    stdio: "ignore",
    detached: true,
  });
  child.unref();
}

async function handleCommand(config) {
  if (!config.enabled) return { text: "GPT profile switcher is disabled." };
  const status = await managerJson(config, ["status"]);
  if (status.ok === false) return { text: `GPT profile status failed: ${status.error}` };
  return {
    text: statusText(status),
    channelData: { telegram: { buttons: profileButtons(status) } },
  };
}

async function handleInboundClaim(event, config) {
  const text = String(event?.messageText || event?.text || event?.content || "").trim();
  const command = text.startsWith("/") ? text.slice(1).split(/\s+/, 1)[0].split("@", 1)[0].toLowerCase() : "";
  if (command !== "gptprof") return { handled: false };
  const reply = await handleCommand(config);
  return { handled: true, reply };
}

function commandPartsFromText(text) {
  const trimmed = String(text || "").trim();
  if (!trimmed.startsWith("/")) return null;
  const parts = trimmed.split(/\s+/);
  const command = parts[0].slice(1).split("@", 1)[0].toLowerCase();
  if (command !== "gptprof") return null;
  return parts.slice(1);
}

function textOnlyStatus(status) {
  return [
    statusText(status),
    "",
    "Commands:",
    "/gptprof add - start OpenAI device auth",
    "/gptprof check - finish pending device auth",
    "/gptprof use-native - apply openai/* + native Codex runtime",
    "/gptprof switch <slug> - switch profile",
  ].join("\n");
}

async function handleTextCommand(args, config) {
  const fastConfig = { ...config, timeoutMs: Math.min(config.timeoutMs || DEFAULT_TIMEOUT_MS, 12_000) };
  const action = String(args[0] || "status").toLowerCase();
  if (action === "status") {
    const status = await managerJson(fastConfig, ["status"]);
    if (status.ok === false) return `GPT profile status failed: ${status.error}`;
    return textOnlyStatus(status);
  }
  if (action === "add" || action === "device-start") {
    const started = await managerJson(config, ["device-start"]);
    if (started.ok === false) return `OpenAI device auth failed to start: ${started.error}`;
    const expires = Math.max(1, Math.round((started.expiresInSeconds || 900) / 60));
    return [
      "OpenAI device auth",
      "",
      `Open: ${started.verificationUrl}`,
      `Code: ${started.userCode}`,
      `Expires in ${expires} minutes.`,
      "",
      "After approving it, send /gptprof check.",
    ].join("\n");
  }
  if (action === "check" || action === "device-check") {
    const checked = await managerJson(config, ["device-check"]);
    if (checked.ok === false) return `OpenAI device auth check failed: ${checked.error || "unknown error"}`;
    if (checked.pending) {
      return [
        "OpenAI device auth is still waiting.",
        "",
        `Open: ${checked.verificationUrl}`,
        `Code: ${checked.userCode}`,
        "",
        "Approve it, then send /gptprof check again.",
      ].join("\n");
    }
    if (config.restartAfterSwitch) scheduleRestart();
    return `Added and switched GPT profile to ${checked.active} (${checked.email}). Gateway restart scheduled.`;
  }
  if (action === "use-native" || action === "native" || action === "route-native") {
    const routed = await managerJson(config, ["apply-native-route"]);
    if (routed.ok === false) return `Native Codex route failed: ${routed.error}`;
    if (config.restartAfterSwitch) scheduleRestart();
    return "Native Codex route applied. Gateway restart scheduled.";
  }
  if (action === "switch") {
    const slug = String(args[1] || "").trim().toLowerCase();
    if (!slug || !/^[a-z0-9._-]+$/.test(slug)) return "Usage: /gptprof switch <slug>";
    const switched = await managerJson(config, ["switch", slug]);
    if (switched.ok === false) return `GPT profile switch failed: ${switched.error}`;
    if (config.restartAfterSwitch) scheduleRestart();
    return `Switched GPT profile to ${switched.active} (${switched.email}). Gateway restart scheduled.`;
  }
  return "Usage: /gptprof [status|add|check|use-native|switch <slug>]";
}

async function handleBeforeDispatch(event, config) {
  const text = String(event?.content || event?.body || "").trim();
  const args = commandPartsFromText(text);
  if (!args) return { handled: false };
  if (!config.enabled) return { handled: true, text: "GPT profile switcher is disabled." };
  return { handled: true, text: await handleTextCommand(args, config) };
}

const GptProfToolSchema = Type.Object({
  command: Type.Optional(Type.String({ description: "Raw /gptprof arguments." })),
  commandName: Type.Optional(Type.String({ description: "Slash command name." })),
  skillName: Type.Optional(Type.String({ description: "Skill name." })),
}, { additionalProperties: true });

function createGptProfTool(config) {
  return {
    name: "gptprof",
    label: "GPT Profile",
    description: "Manage OpenAI account profiles and native Codex runtime routing.",
    parameters: GptProfToolSchema,
    execute: async (_toolCallId, rawParams) => {
      const command = String(rawParams?.command || "").trim();
      const args = command ? command.split(/\s+/) : [];
      const text = await handleTextCommand(args, config);
      return textResult(text, { ok: true, command: args });
    },
  };
}

async function handleInteractive(ctx, config) {
  const slug = String(ctx?.callback?.payload || "").trim().toLowerCase();
  if (!slug || !/^[a-z0-9._-]+$/.test(slug)) {
    await ctx.respond?.editMessage?.({ text: "Bad GPT profile selection." });
    return { handled: true };
  }
  if (slug === "route-native") {
    const routed = await managerJson(config, ["apply-native-route"]);
    if (routed.ok === false) {
      await ctx.respond?.editMessage?.({ text: `Native Codex route failed: ${routed.error}` });
      return { handled: true };
    }
    const status = await managerJson(config, ["status"]);
    await ctx.respond?.editMessage?.({ text: `Native Codex route applied.\nGateway restart scheduled.\n\n${statusText(status)}`, buttons: profileButtons(status) });
    if (config.restartAfterSwitch) scheduleRestart();
    return { handled: true };
  }
  if (slug === "device-start") {
    const started = await managerJson(config, ["device-start"]);
    if (started.ok === false) {
      await ctx.respond?.editMessage?.({ text: `OpenAI device auth failed to start: ${started.error}` });
      return { handled: true };
    }
    const expires = Math.max(1, Math.round((started.expiresInSeconds || 900) / 60));
    const text = [
      "OpenAI device auth",
      "",
      `Open: ${started.verificationUrl}`,
      `Code: ${started.userCode}`,
      `Expires in ${expires} minutes.`,
      "",
      "After approving it, press Check auth.",
    ].join("\n");
    const status = await managerJson(config, ["status"]);
    await ctx.respond?.editMessage?.({ text, buttons: profileButtons(status) });
    return { handled: true };
  }
  if (slug === "device-check") {
    const checked = await managerJson(config, ["device-check"]);
    if (checked.ok === false) {
      await ctx.respond?.editMessage?.({ text: `OpenAI device auth check failed: ${checked.error || "unknown error"}` });
      return { handled: true };
    }
    if (checked.pending) {
      const text = [
        "OpenAI device auth is still waiting.",
        "",
        `Open: ${checked.verificationUrl}`,
        `Code: ${checked.userCode}`,
        "",
        "Approve it, then press Check auth again.",
      ].join("\n");
      const status = await managerJson(config, ["status"]);
      await ctx.respond?.editMessage?.({ text, buttons: profileButtons(status) });
      return { handled: true };
    }
    const status = await managerJson(config, ["status"]);
    await ctx.respond?.editMessage?.({ text: `Added and switched GPT profile to ${checked.active} (${checked.email}).\nGateway restart scheduled.\n\n${statusText(status)}`, buttons: profileButtons(status) });
    if (config.restartAfterSwitch) scheduleRestart();
    return { handled: true };
  }
  const switched = await managerJson(config, ["switch", slug]);
  if (switched.ok === false) {
    await ctx.respond?.editMessage?.({ text: `GPT profile switch failed: ${switched.error}` });
    return { handled: true };
  }
  const status = await managerJson(config, ["status"]);
  const text = `Switched GPT profile to ${switched.active} (${switched.email}).\nGateway restart scheduled so every agent reloads auth state.\n\n${statusText(status)}`;
  await ctx.respond?.editMessage?.({ text, buttons: profileButtons(status) });
  if (config.restartAfterSwitch) scheduleRestart();
  return { handled: true };
}

const plugin = {
  id: "codex-profile-switcher",
  name: "GPT Profile Switcher",
  description: "Telegram /gptprof buttons for OpenAI account profiles and native Codex runtime routing.",
  register(api) {
    const config = getConfig(api);
    if (typeof api.registerTool === "function") {
      api.registerTool(createGptProfTool(config), { name: "gptprof" });
    }
    api.registerCommand({
      name: "gptprof",
      description: "Switch OpenAI account profiles and keep OpenClaw on openai/* with native Codex runtime.",
      acceptsArgs: false,
      handler: async () => await handleCommand(config),
    });
    if (typeof api.registerInteractiveHandler === "function") {
      api.registerInteractiveHandler({
        channel: "telegram",
        namespace: "gptprof",
        handler: async (ctx) => await handleInteractive(ctx, config),
      });
    }
    if (typeof api.on === "function") {
      api.on("inbound_claim", async (event) => await handleInboundClaim(event, config));
      api.on("before_dispatch", async (event) => await handleBeforeDispatch(event, config));
    } else if (typeof api.registerHook === "function") {
      api.registerHook(
        "inbound_claim",
        async (event) => await handleInboundClaim(event, config),
        {
          name: "gpt-profile-switcher-inbound-claim",
          description: "Route Telegram /gptprof to GPT profile switcher.",
        },
      );
      api.registerHook(
        "before_dispatch",
        async (event) => await handleBeforeDispatch(event, config),
        {
          name: "gpt-profile-switcher-before-dispatch",
          description: "Handle Telegram /gptprof before agent dispatch.",
        },
      );
    }
    const payload = { event: "gpt_profile_switcher.registered", enabled: config.enabled, managerPath: config.managerPath };
    if (api?.logger?.info) api.logger.info(payload);
    else console.info(JSON.stringify(payload));
  },
};

export { handleBeforeDispatch, handleCommand, handleInboundClaim, handleInteractive, profileButtons, statusText };
export default plugin;
