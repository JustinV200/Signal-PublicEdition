// HTTP client for the console backend: login, state, send, action, devices,
// away, the console's health checks and model picks. Every request is same-origin JSON with the X-Console-Token header; a
// 401 clears the token and becomes UnauthorizedError (with the server's reason and its
// `console open` command line) so callers can show the signed-out page. A request that
// never reaches the server fails with plain words, not the browser's "Failed to fetch".
import { parseConsoleHealth, parseIdReply, parseServerState, parseToken } from "./parse";
import { parseAway, parseDevicesPayload } from "./parseDevices";
import { isDict, stringOr } from "./parseFields";
import { authHeaders, setToken } from "./token";
import type {
  ActionArgs,
  ActionName,
  AwayInfo,
  ConsoleCheck,
  DevicesPayload,
  ModelField,
  ModelTarget,
  ServerState,
} from "./types";

const HTTP_UNAUTHORIZED = 401;
/** The guard's reason for a missing or dead token, and the default for a 401 without one. */
export const NOT_SIGNED_IN = "not signed in";
/** What a request that never reached the server (fetch's TypeError) fails with. */
const SERVER_NOT_ANSWERING = "the console server isn't answering";

/** A 401: the token is missing, bad, or older than the newest 8 logins, or a login key failed. */
export class UnauthorizedError extends Error {
  /** The server's `console open` command line from the 401 body; null when it sent none. */
  readonly openCommand: string | null;

  /** `reason` is the server's words (`message`), e.g. "that login key is wrong, used or expired". */
  constructor(reason: string = NOT_SIGNED_IN, openCommand: string | null = null) {
    super(reason);
    this.name = "UnauthorizedError";
    this.openCommand = openCommand;
  }
}

/** The JSON body as a dict, or null when it is not a JSON object. */
async function readBody(response: Response): Promise<Record<string, unknown> | null> {
  try {
    const body: unknown = await response.json();
    return isDict(body) ? body : null;
  } catch {
    return null;
  }
}

// Error replies carry `{error}`; fall back to the status when the body is not JSON.
export async function errorMessage(path: string, response: Response): Promise<string> {
  const error = stringOr((await readBody(response))?.error, "");
  return error || `${path}: HTTP ${response.status}`;
}

/**
 * 401 handling for the streamed requests (the event stream, the camera, setup runs).
 * Their 401 is always the guard's "not signed in", so the body isn't read.
 */
export function rejectUnauthorized(response: Response): void {
  if (response.status !== HTTP_UNAUTHORIZED) return;
  setToken(null);
  throw new UnauthorizedError();
}

/** Clears the token and builds the error from a 401's body: the reason and the command. */
async function signedOutError(response: Response): Promise<UnauthorizedError> {
  setToken(null);
  const body = await readBody(response);
  const reason = stringOr(body?.error, "") || NOT_SIGNED_IN;
  return new UnauthorizedError(reason, stringOr(body?.openCommand, null));
}

/**
 * fetch, with a network failure (a TypeError: server down, connection refused) in plain words.
 * An abort (an AbortError, not a TypeError) is rethrown as is.
 */
export async function fetchOrExplain(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(path, init);
  } catch (error) {
    if (error instanceof TypeError) throw new Error(SERVER_NOT_ANSWERING, { cause: error });
    throw error;
  }
}

async function request(path: string, body?: unknown): Promise<unknown> {
  const response = await fetchOrExplain(path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    headers: {
      ...authHeaders(),
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === HTTP_UNAUTHORIZED) throw await signedOutError(response);
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

/** GET /api/health: the console's own checks (a local read on the server; no socket or token). */
export async function getHealth(): Promise<ConsoleCheck[]> {
  return parseConsoleHealth(await request("/api/health"));
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
