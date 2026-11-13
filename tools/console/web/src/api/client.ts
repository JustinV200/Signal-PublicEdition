// HTTP client for the console backend: login, state, send, action, devices,
// away and model picks. Every request is same-origin JSON with the X-Console-Token header; a
// 401 clears the token and becomes UnauthorizedError so callers can show the
// "run console open" state.
import { parseIdReply, parseServerState, parseToken } from "./parse";
import { parseAway, parseDevicesPayload } from "./parseDevices";
import { authHeaders, setToken } from "./token";
import type {
  ActionArgs,
  ActionName,
  AwayInfo,
  DevicesPayload,
  ModelField,
  ModelTarget,
  ServerState,
} from "./types";

const HTTP_UNAUTHORIZED = 401;

/** The token is missing, bad, or the server restarted. */
export class UnauthorizedError extends Error {
  constructor() {
    super("not signed in");
    this.name = "UnauthorizedError";
  }
}

// Error replies carry `{error}`; fall back to the status when the body is not JSON.
export async function errorMessage(path: string, response: Response): Promise<string> {
  const fallback = `${path}: HTTP ${response.status}`;
  try {
    const body: unknown = await response.json();
    const error = (body as { error?: unknown } | null)?.error;
    return typeof error === "string" && error ? error : fallback;
  } catch {
    return fallback;
  }
}

/** Shared 401 handling for every /api request (also used by the event stream). */
export function rejectUnauthorized(response: Response): void {
  if (response.status !== HTTP_UNAUTHORIZED) return;
  setToken(null);
  throw new UnauthorizedError();
}

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: {
      ...authHeaders(),
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  rejectUnauthorized(response);
  if (!response.ok) throw new Error(await errorMessage(path, response));
  return response.json();
}

/** POST /api/login with the key from the URL hash; stores the returned token. */
export async function login(key: string): Promise<void> {
  setToken(parseToken(await request("/api/login", { key })));
}

/** GET /api/state. Throws UnauthorizedError or a network/HTTP error. */
export async function getState(): Promise<ServerState> {
  return parseServerState(await request("/api/state"));
}

/** POST /api/send. Resolves with the server's message id. */
export async function sendText(text: string): Promise<{ id: string }> {
  return parseIdReply(await request("/api/send", { text }));
}

/** POST /api/action. Resolves with the id of the action's echo message. */
export async function sendAction(action: ActionName, args?: ActionArgs): Promise<{ id: string }> {
  return parseIdReply(await request("/api/action", args ? { action, args } : { action }));
}

/** GET /api/devices: the Connected devices rows and away mode (a read, like /api/state). */
export async function getDevices(): Promise<DevicesPayload> {
  return parseDevicesPayload(await request("/api/devices"));
}

/** POST /api/away: the owner's own Away/Here toggle. Resolves with away mode after the change. */
export async function setAway(on: boolean, until: string): Promise<AwayInfo> {
  const away = parseAway(await request("/api/away", { on, until }));
  if (!away) throw new Error("/api/away: unexpected reply");
  return away;
}

/**
 * POST /api/models: the owner's model or effort pick. `index` points into the
 * state's `models.choices[target][field]`; the new state follows on the event stream.
 */
export async function pickModel(
  target: ModelTarget,
  field: ModelField,
  index: number,
): Promise<void> {
  await request("/api/models", { target, field, index });
}
