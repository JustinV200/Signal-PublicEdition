// POST /api/setup/run: runs one setup CLI command in the console server and
// reads its NDJSON answer as it streams (`{"line"}` per output line, then
// `{"exit"}`), so a long install shows live. POST /api/setup/terminal opens a
// terminal window for steps that need one. Both use the page's session token;
// a 401 signs the page out like every other call.
import { errorMessage, rejectUnauthorized } from "../client";
import { authHeaders } from "../token";
import type { SetupRequest, SetupResult } from "./types";

const RUN_PATH = "/api/setup/run";
const TERMINAL_PATH = "/api/setup/terminal";

function post(path: string, body: unknown): Promise<Response> {
  return fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { ...authHeaders(), "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** Applies one NDJSON record to the result; a malformed line shows as plain output. */
function takeRecord(raw: string, result: SetupResult, onLine?: (line: string) => void): void {
  if (!raw.trim()) return;
  let record: unknown;
  try {
    record = JSON.parse(raw);
  } catch {
    record = { line: raw };
  }
  const { line, exit } = (record ?? {}) as { line?: unknown; exit?: unknown };
  if (typeof exit === "number") result.exit = exit;
  if (typeof line === "string") {
    result.lines.push(line);
    onLine?.(line);
  }
}

/**
 * Runs `request` and resolves when the command ends. `onLine` sees each output
 * line as it arrives. Rejects on a 400/409 (with the server's reason) or a
 * dropped connection; a command that fails still resolves, with its exit code.
 */
export async function runSetup(
  request: SetupRequest,
  onLine?: (line: string) => void,
): Promise<SetupResult> {
  const response = await post(RUN_PATH, request);
  rejectUnauthorized(response);
  if (!response.ok || !response.body) throw new Error(await errorMessage(RUN_PATH, response));
  // -1 until the exit record arrives: a stream cut short reads as a failure.
  const result: SetupResult = { exit: -1, lines: [] };
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffered = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffered += value;
    const parts = buffered.split("\n");
    buffered = parts.pop() ?? "";
    parts.forEach((raw) => takeRecord(raw, result, onLine));
  }
  takeRecord(buffered, result, onLine);
  return result;
}

/** Opens a terminal window on `setup.ps1 <tool>` (Windows). Rejects with the reason it can't. */
export async function openSetupTerminal(tool: string): Promise<void> {
  const response = await post(TERMINAL_PATH, { tool });
  rejectUnauthorized(response);
  if (!response.ok) throw new Error(await errorMessage(TERMINAL_PATH, response));
}
