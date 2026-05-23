#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const command = process.argv[2] || "help";
const passthroughArgs = process.argv.slice(3);

const commands = {
  setup: "install",
  start: "start",
  verify: "verify",
  doctor: "doctor",
  "context:export": "context-export",
  "context:import": "context-import",
  "context:sync": "context-sync",
};

function log(message) {
  console.log(`[xmem] ${message}`);
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
  npm run context:import -- --file .\\exports\\xmem-context.json
  npm run context:sync -- --file .\\exports\\xmem-context.json --server https://api.xmem.in --api-key <key>

Power-user flags can be passed after --, for example:
  npm run setup -- -IncludeMcp
  npm run start -- -SkipDocker
`);
  process.exit(exitCode);
}

function powershellExecutable() {
  if (process.env.XMEM_POWERSHELL) {
    return process.env.XMEM_POWERSHELL;
  }
  return process.platform === "win32" ? "powershell.exe" : "pwsh";
}

function powershellArgs(scriptPath, extraArgs) {
  const args = ["-NoProfile"];
  if (process.platform === "win32") {
    args.push("-ExecutionPolicy", "Bypass");
  }
  args.push("-File", scriptPath, ...extraArgs);
  return args;
}

function shellArgs(scriptPath, extraArgs) {
  return [scriptPath, ...extraArgs];
}

function runScript(scriptName, extraArgs = []) {
  const extension = process.platform === "win32" ? ".ps1" : ".sh";
  const executable =
    process.platform === "win32"
      ? powershellExecutable()
      : process.env.XMEM_SHELL || "bash";
  const scriptPath = path.join(root, "scripts", `${scriptName}${extension}`);
  if (!fs.existsSync(scriptPath)) {
    console.error(`[xmem] Missing script: ${scriptPath}`);
    process.exit(1);
  }

  const args =
    process.platform === "win32"
      ? powershellArgs(scriptPath, extraArgs)
      : shellArgs(scriptPath, extraArgs);

  const result = spawnSync(executable, args, {
    cwd: root,
    stdio: "inherit",
    shell: false,
  });

  if (result.error) {
    const installHint =
      process.platform === "win32"
        ? "PowerShell should be available on Windows. Reopen the terminal and try again."
        : "Install bash, or set XMEM_SHELL to a compatible shell.";
    console.error(`[xmem] Could not start ${executable}: ${result.error.message}`);
    console.error(`[xmem] ${installHint}`);
    process.exit(1);
  }

  process.exitCode = result.status || 0;
  return process.exitCode;
}

function getOptionValue(args, optionName) {
  const wanted = optionName.toLowerCase();
  for (let index = 0; index < args.length; index += 1) {
    if (args[index].toLowerCase() === wanted) {
      return args[index + 1] || "";
    }
  }
  return "";
}

function hasSwitch(args, switchName) {
  const wanted = switchName.toLowerCase();
  return args.some((arg) => arg.toLowerCase() === wanted);
}

function startCompatibleArgs(args) {
  const next = [];
  const reposDir = getOptionValue(args, "-ReposDir");
  if (reposDir) {
    next.push("-ReposDir", reposDir);
  }
  if (hasSwitch(args, "-SkipDocker")) {
    next.push("-SkipDocker");
  }
  return next;
}

function setupLooksComplete(reposDir) {
  function existsInRoot(relativePath) {
    return fs.existsSync(path.join(root, relativePath));
  }

  const pythonVenv =
    process.platform === "win32"
      ? ".venv/Scripts/python.exe"
      : ".venv/bin/python";

  return (
    existsInRoot("pyproject.toml") &&
    existsInRoot(".env") &&
    existsInRoot(pythonVenv) &&
    fs.existsSync(path.join(reposDir, "xmem-extension", ".git")) &&
    fs.existsSync(path.join(reposDir, "xmem-extension", "dist", "manifest.json"))
  );
}

function runDev() {
  const reposDir = path.resolve(root, getOptionValue(passthroughArgs, "-ReposDir") || "repos");

  if (!setupLooksComplete(reposDir)) {
    log("First run detected; running setup before starting XMem.");
    const setupStatus = runScript(commands.setup, passthroughArgs);
    if (setupStatus !== 0) {
      process.exit(setupStatus);
    }
  }

  return runScript(commands.start, startCompatibleArgs(passthroughArgs));
}

if (command === "help" || command === "--help" || command === "-h") {
  usage(0);
}

if (command === "dev") {
  runDev();
} else if (commands[command]) {
  runScript(commands[command], passthroughArgs);
} else {
  console.error(`[xmem] Unknown command: ${command}`);
  usage(1);
}
