import { spawn } from "child_process";
import path from "path";
import fs from "fs/promises";

const AGENTS_DIR =
  process.env.AGENTS_DIR || path.resolve(process.cwd(), "..", "agents");
// In Docker/Railway set PYTHON_BIN (e.g. /app/agents/.venv/bin/python). Locally
// it defaults to the venv created next to the agents.
const PY = process.env.PYTHON_BIN || path.join(AGENTS_DIR, ".venv", "bin", "python");

const NOISE = /FutureWarning|NotOpenSSLWarning|warnings\.warn|eol_message|past its end of life|urllib3/;

export type AgentResult = { ok: boolean; output: string; code: number | null };

/** Run a python agent script from the agents/ dir and return its cleaned output. */
export function runAgent(
  script: string,
  args: string[],
  timeoutMs = 1000 * 60 * 15
): Promise<AgentResult> {
  return new Promise((resolve) => {
    const child = spawn(PY, [script, ...args], { cwd: AGENTS_DIR });
    let buf = "";
    const timer = setTimeout(() => child.kill("SIGKILL"), timeoutMs);
    child.stdout.on("data", (d) => (buf += d.toString()));
    child.stderr.on("data", (d) => (buf += d.toString()));
    child.on("error", (e) => {
      clearTimeout(timer);
      resolve({ ok: false, output: `failed to start: ${e.message}`, code: null });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      const clean = buf
        .split("\n")
        .filter((l) => !NOISE.test(l))
        .join("\n")
        .trim();
      resolve({ ok: code === 0, output: clean, code });
    });
  });
}

/** Persist a pasted blob to agents/clients/_uploads and return the file path. */
export async function writeUpload(prefix: string, content: string): Promise<string> {
  const dir = path.join(AGENTS_DIR, "clients", "_uploads");
  await fs.mkdir(dir, { recursive: true });
  const safe = prefix.replace(/[^a-z0-9_-]/gi, "_");
  const file = path.join(dir, `${safe}-${Date.now()}.txt`);
  await fs.writeFile(file, content, "utf8");
  return file;
}
