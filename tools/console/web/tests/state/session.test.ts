// Session start against a fake fetch: a 401 anywhere must end in the
// signed-out state with the server's own reason and command, and a good hash
// key is redeemed for a token that every later request carries.
import { afterEach, describe, expect, it, vi } from "vitest";
import { getState, getToken, login } from "../../src/api";
import { startSession } from "../../src/state";

const STATE = {
  orchestrator: {
    claimed: true,
    alive: true,
    label: "main",
    claimedAt: null,
    turn: { state: "idle", startedAt: null, lastActivityAt: null, agents: 0, agentsUnsure: false },
  },
  voice: { running: false, phase: null, startedBy: null },
  board: { saves: [], view: null, itemCount: null, online: false },
  models: null,
  away: null,
  openCommand: 'uv run --project "C:/fake dir/tools/console" --frozen --no-sync console open',
};

function jsonResponse(status: number, body: unknown): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("startSession", () => {
  it("redeems the hash key for a token, sends it on later requests, then loads the state", async () => {
    const fetchMock = vi.fn((url: string) =>
      url === "/api/login" ? jsonResponse(200, { token: "tok-1" }) : jsonResponse(200, STATE),
    );
    vi.stubGlobal("fetch", fetchMock);
    expect(await startSession("abc", { login, getState })).toEqual({ kind: "in", state: STATE });
    const [[, loginInit], [, stateInit]] = fetchMock.mock.calls as unknown as [
      string,
      RequestInit,
    ][];
    expect(JSON.parse(String(loginInit.body))).toEqual({ key: "abc" });
    expect(loginInit.credentials).toBe("same-origin");
    expect(stateInit.headers).toMatchObject({ "X-Console-Token": "tok-1" });
    expect(getToken()).toBe("tok-1");
  });

  it("turns a failed login into the signed-out state with the server's reason", async () => {
    const reason = "that login key is wrong, used or expired";
    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse(401, { error: reason, openCommand: STATE.openCommand })),
    );
    expect(await startSession("used-key", { login, getState })).toEqual({
      kind: "out",
      reason,
      openCommand: STATE.openCommand,
    });
    expect(getToken()).toBeNull();
  });

  it("says the server isn't answering, not the browser's words, when fetch can't connect", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))),
    );
    const outcome = await startSession(null, { login, getState });
    expect(outcome.kind === "down" && String(outcome.error)).toBe(
      "Error: the console server isn't answering",
    );
  });
});
