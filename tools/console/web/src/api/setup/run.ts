// POST /api/setup/run: runs one setup CLI command in the console server and
// reads its NDJSON answer as it streams (`{"line"}` per output line, then
// `{"exit"}`), so a long install shows live. POST /api/setup/terminal opens a
// terminal window on one step that needs one. Both use the page's session token;
// a 401 signs the page out like every other call.
import { errorMessage, fetchOrExplain, rejectUnauthorized } from "../client";
import { authHeaders } from "../token";
import type { SetupRequest, SetupResult } from "./types";

const RUN_PATH = "/api/setup/run";
const TERMINAL_PATH = "/api/setup/terminal";
const HTTP_CONFLICT = 409;

/** The server is busy with another setup command (a 409): wait, nothing failed. */
export class SetupBusyError extends Error {}

function post(path: string, body: unknown): Promise<Response> {
  return fetchOrExplain(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { ...authHeaders(), "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

/**
 * Applies one NDJSON record to the result; a malformed line shows as plain output.
 * Returns true for the server's busy record (it lost the one-at-a-time race).
 */
function takeRecord(raw: string, result: SetupResult, onLine?: (line: string) => void): boolean {
  if (!raw.trim()) return false;
  let record: unknown;
  try {
    record = JSON.parse(raw);
  } catch {
    record = { line: raw };
  }
  const { line, exit, busy } = (record ?? {}) as { line?: unknown; exit?: unknown; busy?: unknown };
  if (typeof exit === "number") result.exit = exit;
  if (typeof line === "string") {
    result.lines.push(line);
    onLine?.(line);
  }
  return busy === true;
}

/**
 * Runs `request` and resolves when the command ends. `onLine` sees each output
 * line as it arrives. Rejects on a 400 (with the server's reason), on a 409 or
 * a busy record (a SetupBusyError: another command is running), or on a
 * dropped connection; a command that fails still resolves, with its exit code.
 */
export async function runSetup(
  request: SetupRequest,
  onLine?: (line: string) => void,
): Promise<SetupResult> {
  const response = await post(RUN_PATH, request);
  rejectUnauthorized(response);
  if (response.status === HTTP_CONFLICT)
    throw new SetupBusyError(await errorMessage(RUN_PATH, response));
  if (!response.ok || !response.body) throw new Error(await errorMessage(RUN_PATH, response));
  // -1 until the exit record arrives: a stream cut short reads as a failure.
  const result: SetupResult = { exit: -1, lines: [] };
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffered = "";
  let isBusy = false;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffered += value;
    const parts = buffered.split("\n");
    buffered = parts.pop() ?? "";
    for (const raw of parts) isBusy = takeRecord(raw, result, onLine) || isBusy;
  }
  isBusy = takeRecord(buffered, result, onLine) || isBusy;
  if (isBusy) throw new SetupBusyError(result.lines.at(-1) ?? "another setup step is running");
  return result;
}

/**
 * Opens a terminal window on `setup.ps1 step <tool> <step>` (Windows): that one
 * step, no wiring. Rejects with the reason it can't.
 */
export async function openSetupTerminal(tool: string, step: string): Promise<void> {
  const response = await post(TERMINAL_PATH, { tool, step });
  rejectUnauthorized(response);
  if (!response.ok) throw new Error(await errorMessage(TERMINAL_PATH, response));
}
