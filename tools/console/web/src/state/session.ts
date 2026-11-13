// Session start: redeem the `#k=<key>` hash for a token, then fetch the
// first state snapshot. Pure apart from the injected api, so the 401 path is
// testable without a browser.
import { UnauthorizedError } from "../api";
import type { ServerState } from "../api";

const HASH_KEY_PARAM = "k";
// `console open --view setup --tool mail` adds `&v=setup&t=mail` after the key.
const HASH_VIEW_PARAM = "v";
const HASH_TOOL_PARAM = "t";

/** What the opening URL asked for: the login key, and a view and tool to open on. */
export interface HashLink {
  key: string | null;
  view: string | null;
  tool: string | null;
}

export interface SessionApi {
  login: (key: string) => Promise<void>;
  getState: () => Promise<ServerState>;
}

export type SessionOutcome =
  { kind: "in"; state: ServerState } | { kind: "out" } | { kind: "down"; error: unknown };

/** The key, view and tool from a `#k=<key>&v=<view>&t=<tool>` hash (each null if absent). */
export function readHashLink(hash: string): HashLink {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  return {
    key: params.get(HASH_KEY_PARAM),
    view: params.get(HASH_VIEW_PARAM),
    tool: params.get(HASH_TOOL_PARAM),
  };
}

/**
 * Reads the URL fragment and drops it at once, so the key never stays in the
 * address bar or in history. Call before rendering.
 */
export function takeHashLink(): HashLink {
  const link = readHashLink(location.hash);
  if (location.hash) history.replaceState(null, "", location.pathname + location.search);
  return link;
}

/** Just the login key of takeHashLink (a re-login on hashchange ignores the view). */
export function takeHashKey(): string | null {
  return takeHashLink().key;
}

/**
 * Logs in with `hashKey` when there is one, then loads the state. `out`
 * means a 401 anywhere; `down` means the server could not be reached.
 */
export async function startSession(
  hashKey: string | null,
  api: SessionApi,
): Promise<SessionOutcome> {
  try {
    if (hashKey) await api.login(hashKey);
    return { kind: "in", state: await api.getState() };
  } catch (error) {
    if (error instanceof UnauthorizedError) return { kind: "out" };
    return { kind: "down", error };
  }
}
