// Session start against a fake fetch: a 401 anywhere must end in the calm
// "run console open" state, and a good hash key is redeemed for a token
// that every later request carries.
import { afterEach, describe, expect, it, vi } from "vitest";
import { getState, getToken, login } from "../../src/api";
import { startSession } from "../../src/state";

const STATE = {
  orchestrator: {
    claimed: true,
    label: "main",
    turn: { state: "idle", startedAt: null, lastActivityAt: null, agents: 0, agentsUnsure: false },
  },
  voice: { running: false, phase: null, startedBy: null },
  board: { saves: [], view: null, online: false },
  models: null,
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

  it("turns a 401 into the signed-out state and forgets the token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => jsonResponse(401, { error: "not logged in" })),
    );
    expect(await startSession(null, { login, getState })).toEqual({ kind: "out" });
    expect(getToken()).toBeNull();
    expect(await startSession("used-key", { login, getState })).toEqual({ kind: "out" });
  });
});
