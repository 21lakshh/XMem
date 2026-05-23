#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const scriptsDir = path.join(root, "scripts");
const command = process.argv[2] || "help";
const passthroughArgs = process.argv.slice(3);
const isWindows = process.platform === "win32";

const managedRepos = [
  {
    flag: "includeMcp",
    name: "xmem-mcp",
    url: "https://github.com/XortexAI/xmem-mcp.git",
    branch: "main",
  },
  {
    flag: "includeSdk",
    name: "xmem-sdk",
    url: "https://github.com/XortexAI/xmem-sdk.git",
    branch: "master",
  },
];

function log(message) {
  console.log(`[xmem] ${message}`);
}

function warn(message) {
  console.warn(`[xmem] ${message}`);
}

function fail(message, exitCode = 1) {
  console.error(`[xmem] ${message}`);
  process.exit(exitCode);
}

function usage(exitCode = 0) {
  console.log(`XMem local workspace

Usage:
  npm run dev
  npm run setup
  npm run start
  npm run verify
  npm run doctor
  npm run context:export
  npm run context:import -- --file ./exports/xmem-context.json
  npm run context:sync -- --file ./exports/xmem-context.json --server https://api.xmem.in --api-key <key>

Power-user flags can be passed after --, for example:
  npm run setup -- --include-mcp
  npm run setup -- --skip-model-pull
  npm run start -- --skip-docker

Windows-style flags are also accepted:
  npm run setup -- -IncludeMcp
  npm run start -- -SkipDocker
`);
  process.exit(exitCode);
}

function commandInvocation(commandName, args) {
  if (commandName === "npm" && process.env.npm_execpath) {
    return {
      command: process.execPath,
      args: [process.env.npm_execpath, ...args],
      shell: false,
    };
  }

  if (isWindows && ["npm", "npx"].includes(commandName)) {
    return {
      command: commandName,
      args,
      shell: true,
    };
  }

  return {
    command: commandName,
    args,
    shell: false,
  };
}

function run(commandName, args = [], options = {}) {
  const invocation = commandInvocation(commandName, args);
  const result = spawnSync(invocation.command, invocation.args, {
    cwd: options.cwd || root,
    env: options.env || process.env,
    encoding: options.capture ? "utf8" : undefined,
    stdio: options.capture ? "pipe" : "inherit",
    shell: invocation.shell,
  });

  if (result.error) {
    if (options.allowFailure) {
      return result;
    }
    throw new Error(`Could not start ${commandName}: ${result.error.message}`);
  }

  if (result.status !== 0 && !options.allowFailure) {
    throw new Error(`${commandName} ${args.join(" ")} failed with exit code ${result.status}`);
  }

  return result;
}

function commandExists(commandName) {
  const checker = isWindows
    ? ["where.exe", [commandName]]
    : ["which", [commandName]];
  const result = run(checker[0], checker[1], {
    capture: true,
    allowFailure: true,
  });
  return result.status === 0;
}

function sleep(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function optionParser(spec) {
  const aliases = new Map();
  for (const [key, config] of Object.entries(spec)) {
    for (const alias of config.aliases || []) {
      aliases.set(alias.toLowerCase(), { key, ...config });
    }
  }

  return function parse(args) {
    const values = {};
    for (const [key, config] of Object.entries(spec)) {
      values[key] = config.type === "flag" ? false : config.default || "";
    }

    for (let index = 0; index < args.length; index += 1) {
      let arg = args[index];
      let inlineValue = "";
      const equalsIndex = arg.indexOf("=");
      if (equalsIndex > -1) {
        inlineValue = arg.slice(equalsIndex + 1);
        arg = arg.slice(0, equalsIndex);
      }

      const match = aliases.get(arg.toLowerCase());
      if (!match) {
        throw new Error(`Unknown option: ${args[index]}`);
      }

      if (match.type === "flag") {
        values[match.key] = true;
        continue;
      }

      const value = inlineValue || args[index + 1];
      if (!value || value.startsWith("-")) {
        throw new Error(`${arg} requires a value.`);
      }
      values[match.key] = value;
      if (!inlineValue) {
        index += 1;
      }
    }

    return values;
  };
}

const parseSetupOptions = optionParser({
  reposDir: { type: "value", default: "repos", aliases: ["--repos-dir", "-ReposDir"] },
  includeMcp: { type: "flag", aliases: ["--include-mcp", "-IncludeMcp"] },
  includeSdk: { type: "flag", aliases: ["--include-sdk", "-IncludeSdk"] },
  skipModelPull: { type: "flag", aliases: ["--skip-model-pull", "-SkipModelPull"] },
  skipPythonInstall: { type: "flag", aliases: ["--skip-python-install", "-SkipPythonInstall"] },
  skipNodeInstall: { type: "flag", aliases: ["--skip-node-install", "-SkipNodeInstall"] },
  skipDocker: { type: "flag", aliases: ["--skip-docker", "-SkipDocker"] },
});

const parseStartOptions = optionParser({
  reposDir: { type: "value", default: "repos", aliases: ["--repos-dir", "-ReposDir"] },
  skipDocker: { type: "flag", aliases: ["--skip-docker", "-SkipDocker"] },
});

const parseDoctorOptions = optionParser({
  baseUrl: { type: "value", default: "http://localhost:8000", aliases: ["--base-url", "-BaseUrl"] },
  reposDir: { type: "value", default: "repos", aliases: ["--repos-dir", "-ReposDir"] },
});

function readOption(args, names, fallback = "") {
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    const equalsIndex = arg.indexOf("=");
    const name = equalsIndex > -1 ? arg.slice(0, equalsIndex) : arg;
    if (!names.map((item) => item.toLowerCase()).includes(name.toLowerCase())) {
      continue;
    }
    if (equalsIndex > -1) {
      return arg.slice(equalsIndex + 1);
    }
    return args[index + 1] || fallback;
  }
  return fallback;
}

function hasSwitch(args, names) {
  const wanted = names.map((name) => name.toLowerCase());
  return args.some((arg) => wanted.includes(arg.split("=")[0].toLowerCase()));
}

function startCompatibleArgs(args) {
  const next = [];
  const reposDir = readOption(args, ["--repos-dir", "-ReposDir"]);
  if (reposDir) {
    next.push("--repos-dir", reposDir);
  }
  if (hasSwitch(args, ["--skip-docker", "-SkipDocker"])) {
    next.push("--skip-docker");
  }
  return next;
}

function systemPythonCommand() {
  if (!isWindows && commandExists("python3")) {
    return "python3";
  }
  if (commandExists("python")) {
    return "python";
  }
  fail("Python 3.11+ is required. Install Python, reopen your terminal, and rerun this command.");
}

function venvPythonPath() {
  return path.join(root, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
}

function pythonForRuntime() {
  const venvPython = venvPythonPath();
  if (fs.existsSync(venvPython)) {
    return venvPython;
  }
  warn("XMem virtualenv was not found; using system Python. Run npm run setup if startup fails.");
  return systemPythonCommand();
}

function stripQuotes(value) {
  const trimmed = String(value || "").trim();
  if (
    (trimmed.startsWith("'") && trimmed.endsWith("'")) ||
    (trimmed.startsWith('"') && trimmed.endsWith('"'))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function readDotEnv(envPath) {
  const values = {};
  if (!fs.existsSync(envPath)) {
    return values;
  }

  for (const rawLine of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#") || !line.includes("=")) {
      continue;
    }
    const [key, ...rest] = line.split("=");
    values[key.trim()] = stripQuotes(rest.join("="));
  }
  return values;
}

function setDotEnvValues(envPath, updates) {
  const original = fs.existsSync(envPath) ? fs.readFileSync(envPath, "utf8") : "";
  const lines = original ? original.split(/\r?\n/) : [];
  const updatedKeys = new Set();
  const next = lines.map((line) => {
    for (const [key, value] of Object.entries(updates)) {
      const pattern = new RegExp(`^\\s*${key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*=`);
      if (pattern.test(line)) {
        updatedKeys.add(key);
        return `${key}=${value}`;
      }
    }
    return line;
  });

  for (const [key, value] of Object.entries(updates)) {
    if (!updatedKeys.has(key)) {
      next.push(`${key}=${value}`);
    }
  }

  fs.writeFileSync(envPath, `${next.join("\n").replace(/\n+$/g, "")}\n`);
}

function isRealSecret(value) {
  const text = stripQuotes(value).trim();
  if (!text) {
    return false;
  }

  return ![
    /^your[_-]/i,
    /your_.*_key/i,
    /example/i,
    /sample/i,
    /placeholder/i,
    /change[-_]?me/i,
    /^dummy([-_].*)?$/i,
    /^fake([-_].*)?$/i,
    /^test([-_].*)?$/i,
  ].some((pattern) => pattern.test(text));
}

function configuredValue(envPath, name) {
  const envValue = process.env[name];
  if (isRealSecret(envValue)) {
    return envValue;
  }
  const fileValue = readDotEnv(envPath)[name];
  return isRealSecret(fileValue) ? fileValue : "";
}

function configuredProviders(envPath) {
  const providers = [];
  if (configuredValue(envPath, "OPENROUTER_API_KEY")) providers.push("openrouter");
  if (configuredValue(envPath, "GEMINI_API_KEY")) providers.push("gemini");
  if (configuredValue(envPath, "CLAUDE_API_KEY")) providers.push("claude");
  if (configuredValue(envPath, "OPENAI_API_KEY")) providers.push("openai");
  if (
    configuredValue(envPath, "AWS_ACCESS_KEY_ID") &&
    configuredValue(envPath, "AWS_SECRET_ACCESS_KEY")
  ) {
    providers.push("bedrock");
  }
  return providers;
}

function configureEnv(envPath, quiet = false) {
  if (!fs.existsSync(envPath)) {
    throw new Error(`XMem .env not found at ${envPath}. Run npm run setup first.`);
  }

  const providers = configuredProviders(envPath);

  if (providers.length > 0) {
    setDotEnvValues(envPath, {
      FALLBACK_ORDER: `'${JSON.stringify(providers)}'`,
      EMBEDDING_PROVIDER: "fastembed",
      FASTEMBED_MODEL: "BAAI/bge-small-en-v1.5",
      EMBEDDING_MODEL: "BAAI/bge-small-en-v1.5",
      PINECONE_DIMENSION: "384",
    });
    if (!quiet) {
      log(`Detected cloud LLM provider(s): ${providers.join(", ")}`);
      log("Configured XMem to avoid Ollama for LLM and embedding calls.");
    }
    return providers;
  }

  setDotEnvValues(envPath, {
    FALLBACK_ORDER: `'["ollama"]'`,
    EMBEDDING_PROVIDER: "ollama",
    OLLAMA_EMBEDDING_MODEL: "nomic-embed-text",
    EMBEDDING_MODEL: "nomic-embed-text",
    PINECONE_DIMENSION: "768",
  });
  if (!quiet) {
    log("No cloud LLM provider keys detected.");
    log("Configured XMem to use local Ollama for LLM and embedding calls.");
  }
  return [];
}

function dotEnvValue(envPath, name, fallback = "") {
  return readDotEnv(envPath)[name] || fallback;
}

function usesOllama(envPath) {
  if (!fs.existsSync(envPath)) {
    return true;
  }
  return /ollama/i.test(readDotEnv(envPath).FALLBACK_ORDER || "");
}

function syncRepo(reposDir, name, url, branch) {
  const target = path.join(reposDir, name);
  if (fs.existsSync(target)) {
    if (!fs.existsSync(path.join(target, ".git"))) {
      throw new Error(`${target} exists but is not a git checkout.`);
    }
    log(`Updating ${name}`);
    run("git", ["-C", target, "reset", "--hard"]);
    run("git", ["-C", target, "fetch", "origin"]);
    run("git", ["-C", target, "checkout", branch]);
    run("git", ["-C", target, "pull", "--ff-only", "origin", branch]);
    return;
  }

  log(`Cloning ${name}`);
  run("git", ["clone", "--branch", branch, url, target]);
}

function dockerRunning() {
  return commandExists("docker") && run("docker", ["info"], { capture: true, allowFailure: true }).status === 0;
}

function ollamaRunning() {
  return commandExists("ollama") && run("ollama", ["list"], { capture: true, allowFailure: true }).status === 0;
}

function waitForContainers(names, timeoutSeconds = 180) {
  const pending = new Set(names);
  const deadline = Date.now() + timeoutSeconds * 1000;
  let waitLogged = false;

  while (Date.now() < deadline) {
    for (const name of [...pending]) {
      const result = run(
        "docker",
        [
          "inspect",
          "--format",
          "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
          name,
        ],
        { capture: true, allowFailure: true },
      );

      if (result.status !== 0) {
        continue;
      }

      const status = String(result.stdout || "").trim();
      if (status === "healthy" || status === "running") {
        pending.delete(name);
      } else if (status === "unhealthy") {
        throw new Error(`Container ${name} is unhealthy. Run npm run doctor or inspect it with: docker logs ${name}`);
      }
    }

    if (pending.size === 0) {
      return;
    }

    if (!waitLogged) {
      log("Waiting for local database containers to become healthy. First startup can take 1-2 minutes.");
      waitLogged = true;
    }
    log(`Still waiting for: ${[...pending].join(", ")}`);
    sleep(5000);
  }

  throw new Error(`Timed out waiting for local database containers: ${[...pending].join(", ")}. Run npm run doctor for details.`);
}

function startDockerServices() {
  if (!dockerRunning()) {
    return false;
  }
  log("Starting local Docker services");
  run("docker", ["compose", "-f", path.join(root, "docker-compose.local.yml"), "up", "-d", "--remove-orphans"]);
  waitForContainers(["xmem-postgres", "xmem-mongo", "xmem-neo4j"]);
  return true;
}

function installedOllamaModels() {
  const result = run("ollama", ["list"], { capture: true, allowFailure: true });
  if (result.status !== 0) {
    return new Set();
  }
  return new Set(
    String(result.stdout || "")
      .split(/\r?\n/)
      .slice(1)
      .map((line) => line.trim().split(/\s+/)[0])
      .filter(Boolean),
  );
}

function hasOllamaModel(model, installed) {
  if (!model) {
    return true;
  }
  return installed.has(model) || (!model.includes(":") && installed.has(`${model}:latest`));
}

function assertOllamaReady(envPath) {
  if (!commandExists("ollama")) {
    fail("Ollama was not found. Install Ollama, or add a cloud LLM key to .env and rerun.", 2);
  }
  if (!ollamaRunning()) {
    fail("XMem is configured to use local Ollama, but Ollama is not running. Start Ollama, or add a cloud LLM key to .env and rerun.", 2);
  }

  const chatModel = dotEnvValue(envPath, "OLLAMA_MODEL", "qwen2.5:1.5b");
  const embeddingModel = dotEnvValue(envPath, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text");
  const installed = installedOllamaModels();
  const missing = [chatModel, embeddingModel].filter((model) => !hasOllamaModel(model, installed));
  if (missing.length > 0) {
    for (const model of missing) {
      warn(`Ollama model ${model} is missing. Run: ollama pull ${model}`);
    }
    fail("Required Ollama model(s) are missing, or add a cloud LLM key to .env so XMem does not use Ollama.", 2);
  }
}

function ensurePrerequisites(skipPython = false) {
  for (const required of ["git", "node", "npm"]) {
    if (!commandExists(required)) {
      fail(`${required} is required. Install it, reopen your terminal, and rerun this command.`);
    }
  }
  if (!skipPython) {
    systemPythonCommand();
  }
}

function pythonHasPip(pythonPath) {
  return run(pythonPath, ["-m", "pip", "--version"], { capture: true, allowFailure: true }).status === 0;
}

function ensureVirtualenv() {
  const venvPython = venvPythonPath();
  if (!fs.existsSync(venvPython)) {
    log("Creating XMem virtualenv. Keep this terminal open; Windows may take a minute here.");
    run(systemPythonCommand(), ["-m", "venv", path.join(root, ".venv")]);
    log("XMem virtualenv created");
  }

  if (!pythonHasPip(venvPython)) {
    log("Repairing XMem virtualenv pip");
    const result = run(venvPython, ["-m", "ensurepip", "--upgrade"], {
      allowFailure: true,
    });
    if (result.status !== 0 || !pythonHasPip(venvPython)) {
      fail(
        "XMem virtualenv was created, but pip is unavailable. Reinstall Python with venv/pip support, delete .venv, and rerun npm run setup.",
        2,
      );
    }
  }

  return venvPython;
}

function setupLooksComplete(reposDir) {
  return (
    fs.existsSync(path.join(root, "pyproject.toml")) &&
    fs.existsSync(path.join(root, ".env")) &&
    fs.existsSync(venvPythonPath()) &&
    fs.existsSync(path.join(reposDir, "xmem-extension", ".git")) &&
    fs.existsSync(path.join(reposDir, "xmem-extension", "dist", "manifest.json"))
  );
}

function runSetup(args) {
  const options = parseSetupOptions(args);
  const reposDir = path.resolve(root, options.reposDir);
  const extensionDir = path.join(reposDir, "xmem-extension");
  let dockerSkipped = false;
  let ollamaSkipped = false;

  ensurePrerequisites(options.skipPythonInstall);
  fs.mkdirSync(reposDir, { recursive: true });

  syncRepo(reposDir, "xmem-extension", "https://github.com/XortexAI/xmem-extension.git", "main");
  for (const repo of managedRepos) {
    if (options[repo.flag]) {
      syncRepo(reposDir, repo.name, repo.url, repo.branch);
    }
  }

  const envTemplate = path.join(root, "templates", "xmem.env.local");
  const envTarget = path.join(root, ".env");
  if (!fs.existsSync(envTarget)) {
    fs.copyFileSync(envTemplate, envTarget);
    log("Created .env from local template");
  } else {
    log(".env already exists; leaving it unchanged");
  }

  configureEnv(envTarget);

  if (!options.skipModelPull) {
    if (usesOllama(envTarget)) {
      if (ollamaRunning()) {
        const chatModel = dotEnvValue(envTarget, "OLLAMA_MODEL", "qwen2.5:1.5b");
        const embeddingModel = dotEnvValue(envTarget, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text");
        log("Pulling Ollama chat model");
        run("ollama", ["pull", chatModel]);
        log("Pulling Ollama embedding model");
        run("ollama", ["pull", embeddingModel]);
      } else {
        warn("Ollama was not found or is not running.");
        warn("Start Ollama, or add a cloud LLM key to .env and rerun.");
        ollamaSkipped = true;
      }
    } else {
      log("Cloud LLM provider key detected; skipping Ollama model pulls");
    }
  }

  if (!options.skipDocker) {
    if (!startDockerServices()) {
      warn("Docker Desktop is installed but not running, or Docker was not found.");
      warn("Start Docker Desktop, wait until it says Docker is running, then rerun this command.");
      warn("Temporary escape hatch: rerun npm run setup -- --skip-docker to continue without local databases.");
      dockerSkipped = true;
    }
  }

  if (!options.skipPythonInstall) {
    const venvPython = ensureVirtualenv();
    log("Installing XMem local dependencies");
    run(venvPython, ["-m", "pip", "install", "--upgrade", "pip"]);
    run(venvPython, ["-m", "pip", "install", "-e", `${root}[local,dev]`]);
  }

  log("Patching extension for local API");
  run(process.execPath, [path.join(scriptsDir, "patch-extension-local.js"), "--extension-dir", extensionDir]);

  if (!options.skipNodeInstall) {
    log("Installing and building Chrome extension");
    run("npm", ["--prefix", extensionDir, "install"]);
    run("npm", ["--prefix", extensionDir, "run", "build"]);
  }

  log("Install complete");
  console.log("");
  console.log("Next:");
  console.log("  npm run dev");
  console.log("  npm run verify");
  if (dockerSkipped) {
    console.log("");
    warn("Docker services were not started. Start Docker Desktop before running npm run dev.");
  }
  if (ollamaSkipped) {
    console.log("");
    warn("Ollama models were not pulled. Start Ollama, then rerun npm run setup or add a cloud LLM key.");
  }
}

function runStart(args) {
  const options = parseStartOptions(args);
  const envTarget = path.join(root, ".env");

  if (!fs.existsSync(envTarget)) {
    fail(`XMem .env not found at ${envTarget}. Run npm run setup first.`);
  }

  configureEnv(envTarget);

  if (usesOllama(envTarget)) {
    assertOllamaReady(envTarget);
  }

  if (!options.skipDocker) {
    if (!startDockerServices()) {
      fail("Docker Desktop is installed but not running, or Docker was not found. Start Docker Desktop, then rerun npm run dev.", 2);
    }
  }

  const python = pythonForRuntime();
  log("Starting XMem API at http://localhost:8000");
  run(python, ["-m", "uvicorn", "src.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]);
}

function runDev(args) {
  const reposDir = path.resolve(root, readOption(args, ["--repos-dir", "-ReposDir"], "repos"));
  if (!setupLooksComplete(reposDir)) {
    log("First run detected; running setup before starting XMem.");
    runSetup(args);
  }
  runStart(startCompatibleArgs(args));
}

function runVerify(args) {
  const python = pythonForRuntime();
  run(python, [path.join(scriptsDir, "verify.py"), ...args]);
}

function runContext(subcommand, args) {
  const venvPython = venvPythonPath();
  if (!fs.existsSync(venvPython)) {
    fail("XMem virtualenv not found. Run npm run setup first.");
  }
  run(venvPython, [path.join(scriptsDir, "context.py"), subcommand, ...args]);
}

function writeCheck(name, ok, message, fix = "") {
  const label = ok ? "OK" : "FIX";
  console.log(`[${label}] ${name} - ${message}`);
  if (!ok && fix) {
    console.log(`      ${fix}`);
  }
}

async function fetchHealth(baseUrl) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(`${baseUrl.replace(/\/+$/, "")}/health`, {
      signal: controller.signal,
    });
    if (!response.ok) {
      return { ok: false, message: `HTTP ${response.status}` };
    }
    const body = await response.json();
    const data = body.data || body;
    return {
      ok: Boolean(data.pipelines_ready),
      message: `${baseUrl}/health`,
    };
  } catch {
    return { ok: false, message: `${baseUrl} is not reachable` };
  } finally {
    clearTimeout(timeout);
  }
}

async function runDoctor(args) {
  const options = parseDoctorOptions(args);
  const reposDir = path.resolve(root, options.reposDir);
  const envPath = path.join(root, ".env");
  const extensionDir = path.join(reposDir, "xmem-extension");
  let failures = 0;

  console.log("[xmem] Doctor report");
  console.log("");

  for (const cmd of ["git", "node", "npm"]) {
    const ok = commandExists(cmd);
    if (!ok) failures += 1;
    writeCheck(cmd, ok, "command lookup", `Install ${cmd} and reopen this terminal.`);
  }

  const pythonOk = commandExists("python") || (!isWindows && commandExists("python3"));
  if (!pythonOk) failures += 1;
  writeCheck("Python", pythonOk, "Python 3.11+ lookup", "Install Python 3.11+ and reopen this terminal.");

  const dockerOk = dockerRunning();
  if (!dockerOk) failures += 1;
  writeCheck("Docker", dockerOk, "local database runtime", "Start Docker Desktop, then rerun npm run dev.");

  const xmemExists = fs.existsSync(path.join(root, "pyproject.toml"));
  if (!xmemExists) failures += 1;
  writeCheck("XMem repo", xmemExists, root, "Run this from the XMem repository root.");

  const extensionExists = fs.existsSync(extensionDir);
  if (!extensionExists) failures += 1;
  writeCheck("Extension repo", extensionExists, extensionDir, "Run npm run setup.");

  const extensionBuildExists = fs.existsSync(path.join(extensionDir, "dist", "manifest.json"));
  if (!extensionBuildExists) failures += 1;
  writeCheck("Extension build", extensionBuildExists, "repos/xmem-extension/dist", "Run npm run setup.");

  const envExists = fs.existsSync(envPath);
  if (!envExists) failures += 1;
  writeCheck("XMem .env", envExists, envPath, "Run npm run setup to create it from templates/xmem.env.local.");

  if (envExists) {
    const providers = configuredProviders(envPath);
    if (providers.length > 0) {
      writeCheck("LLM routing", true, `cloud key detected: ${providers.join(", ")}; Ollama is not required`);
    } else if (usesOllama(envPath)) {
      const ollamaOk = ollamaRunning();
      if (!ollamaOk) failures += 1;
      writeCheck("Ollama", ollamaOk, "required because no cloud LLM key is configured", "Start Ollama, or add a cloud LLM key to .env.");

      if (ollamaOk) {
        const installed = installedOllamaModels();
        for (const model of [
          dotEnvValue(envPath, "OLLAMA_MODEL", "qwen2.5:1.5b"),
          dotEnvValue(envPath, "OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"),
        ]) {
          const ok = hasOllamaModel(model, installed);
          if (!ok) failures += 1;
          writeCheck(`Ollama model ${model}`, ok, "local model availability", `Run: ollama pull ${model}`);
        }
      }
    } else {
      failures += 1;
      writeCheck("LLM routing", false, "no cloud key detected and FALLBACK_ORDER does not include Ollama", "Run npm run setup to repair .env routing.");
    }
  }

  const health = await fetchHealth(options.baseUrl);
  if (!health.ok) failures += 1;
  writeCheck("XMem API", health.ok, health.message, "Start it with npm run dev and wait for pipelines_ready=true.");

  console.log("");
  if (failures === 0) {
    log("Everything looks ready.");
  } else {
    warn(`Found ${failures} setup item(s) to fix.`);
  }
}

async function main() {
  try {
    if (command === "help" || command === "--help" || command === "-h") {
      usage(0);
    } else if (command === "setup") {
      runSetup(passthroughArgs);
    } else if (command === "dev") {
      runDev(passthroughArgs);
    } else if (command === "start") {
      runStart(passthroughArgs);
    } else if (command === "verify") {
      runVerify(passthroughArgs);
    } else if (command === "doctor") {
      await runDoctor(passthroughArgs);
    } else if (command === "context:export") {
      runContext("export", passthroughArgs);
    } else if (command === "context:import") {
      runContext("import", passthroughArgs);
    } else if (command === "context:sync") {
      runContext("sync", passthroughArgs);
    } else {
      console.error(`[xmem] Unknown command: ${command}`);
      usage(1);
    }
  } catch (error) {
    fail(error.message || String(error));
  }
}

main();
