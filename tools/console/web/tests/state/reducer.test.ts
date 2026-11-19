// The reducer must survive the server's replay-on-connect: duplicate ids
// collapse (first wins), time order holds, notes join the stream, and local
// delivery state outlives the echo. The boards selection follows its board,
// not its row number, across snapshots. An outage keeps its start across
// retries, and a sign-out reason survives a keyless retry. Chat's `N new` counts
// live replies and notes, never replayed history, and clears once seen. The
// wizard's page and drafts outlast a view switch, and the tour follows a tab
// that is one of its stops.
import { describe, expect, it } from "vitest";
import type { Message, Note } from "../../src/api";
import {
  boardIndexOf,
  boardRows,
  chatNewCount,
  initialState,
  reduce,
  startState,
} from "../../src/state";
import type { AppState, StoreAction } from "../../src/state";
import { savesNamed, serverState } from "./serverFixture";

function messageEvent(partial: Partial<Message> & { id: string }): StoreAction {
  const data: Message = { role: "claude", text: "", at: 0, kind: "chat", ...partial };
  return { type: "server", event: { type: "message", data }, now: 0 };
}

function noteEvent(data: Note): StoreAction {
  return { type: "server", event: { type: "note", data }, now: 0 };
}

function run(actions: StoreAction[], from: AppState = initialState): AppState {
  return actions.reduce(reduce, from);
}

describe("reduce", () => {
  it("dedupes replayed messages and notes by id (first wins) and keeps time order", () => {
    const note: Note = { id: "n", at: "2026-10-19T14:01:30Z", text: "Claude session changed" };
    const state = run([
      messageEvent({ id: "b", at: "2026-10-19T14:02:00Z", text: "second" }),
      noteEvent(note),
      messageEvent({ id: "a", at: "2026-10-19T14:01:00Z", text: "first" }),
      messageEvent({ id: "b", at: "2026-10-19T14:02:00Z", text: "second (replayed)" }),
      noteEvent(note),
    ]);
    expect(state.messages.map((m) => m.id)).toEqual(["a", "n", "b"]);
    expect(state.messages[1]).toMatchObject({ kind: "note", text: "Claude session changed" });
    expect(state.messages[2].text).toBe("second");
  });

  it("keeps local delivery through the server echo and applies the delivery event", () => {
    const sent = run([
      {
        type: "sendStarted",
        message: {
          id: "local-1",
          role: "you",
          text: "hi",
          at: 1000,
          kind: "chat",
          delivery: "sending",
          origin: { kind: "text", text: "hi" },
        },
      },
      { type: "sendAccepted", tempId: "local-1", id: "m1" },
      messageEvent({ id: "m1", role: "you", at: 1000, text: "hi" }),
    ]);
    expect(sent.messages).toHaveLength(1);
    expect(sent.messages[0]).toMatchObject({ id: "m1", localId: "local-1", delivery: "sending" });

    const failed = run(
      [
        {
          type: "server",
          event: {
            type: "delivery",
            data: { id: "d1", messageId: "m1", status: "failed", error: "No Claude session" },
          },
          now: 0,
        },
      ],
      sent,
    );
    expect(failed.messages[0]).toMatchObject({
      delivery: "failed",
      error: "No Claude session",
      origin: { kind: "text", text: "hi" },
    });
  });

  it("counts live replies and notes off Chat as new, not replayed history, until seen", () => {
    const openedAt = Date.parse("2026-11-17T10:00:00Z");
    const at = (offsetMs: number) => new Date(openedAt + offsetMs).toISOString();
    const offChat = run([
      // The page's first server event, then the history the server replays on connect.
      { type: "server", event: { type: "state", data: serverState() }, now: openedAt },
      messageEvent({ id: "old", at: at(-60_000) }),
      noteEvent({ id: "old-note", at: at(-30_000), text: "Claude session changed" }),
      { type: "view", view: "tasks" },
      // Live: a reply, a note and the owner's own message (never new to them).
      messageEvent({ id: "reply", at: at(1000) }),
      noteEvent({ id: "note", at: at(2000), text: "Voice started" }),
      messageEvent({ id: "mine", role: "you", at: at(3000) }),
      // A reconnect replays all of it again: repeats add nothing.
      messageEvent({ id: "old", at: at(-60_000) }),
      messageEvent({ id: "reply", at: at(1000) }),
    ]);
    expect(chatNewCount(offChat)).toBe(2);
    const seen = run([{ type: "view", view: "chat" }, { type: "chatSeen" }], offChat);
    expect(chatNewCount(seen)).toBe(0);
  });

  // Regression (U11): the selection was a row number, so a save arriving at the
  // top moved `▸` (and Send to projector) onto a different board.
  it("keeps the selected board when a new save arrives above it", () => {
    const snapshot = (...names: string[]): StoreAction => ({
      type: "server",
      event: { type: "state", data: serverState({ saves: savesNamed(...names) }) },
      now: 0,
    });
    const selected = (state: AppState) =>
      boardRows(state.server)[boardIndexOf(boardRows(state.server), state.boardKey)];

    expect(selected(run([snapshot("lecture")])).action).toBe("board.idle"); // starts on idle
    const picked = run([
      snapshot("lecture", "grid"),
      { type: "boardSelect", key: "board.load:grid" },
    ]);
    const moved = run([snapshot("new", "lecture", "grid")], picked);
    expect(selected(moved)).toMatchObject({ action: "board.load", args: { name: "grid" } });
    // Up moves from the board itself, not from its old row number.
    expect(selected(run([{ type: "boardCursorMove", delta: -1 }], moved)).name).toBe("lecture");
    // A board that is gone falls back to the idle row.
    expect(selected(run([snapshot("lecture")], moved)).action).toBe("board.idle");
  });

  it("keeps when the outage began across offline retries and drops it once online", () => {
    const offline = (since: number): StoreAction => ({
      type: "connection",
      connection: { status: "offline", retryAt: since + 1000, since },
    });
    const retried = run([offline(100), offline(5000)]);
    expect(retried.connection).toEqual({ status: "offline", retryAt: 6000, since: 100 });
    const back = run(
      [{ type: "connection", connection: { status: "online" } }, offline(9000)],
      retried,
    );
    expect(back.connection).toMatchObject({ since: 9000 });
  });

  // Regression: a focus retry (no key) answered the plain "not signed in" and hid
  // why the login failed.
  it("keeps the specific sign-out reason through a keyless retry, clears it on sign-in", () => {
    const reason = "that login key is wrong, used or expired";
    const retried = run([
      { type: "auth", auth: "out", reason },
      { type: "auth", auth: "checking" },
      { type: "auth", auth: "out", reason: "not signed in" },
    ]);
    expect(retried.signOutReason).toBe(reason);
    expect(run([{ type: "auth", auth: "in" }], retried).signOutReason).toBeNull();
  });

  // Regression (P15): the wizard's page and typed values lived in the view, which unmounts.
  it("keeps the wizard's page and typed values through a view switch", () => {
    // Opened by `#v=setup&t=mail`; the wizard then forgets the jump (`tool: null`).
    const state = run(
      [
        { type: "openSetup", tool: null },
        { type: "setupDraft", key: "value/mail/email", text: "me@example.com" },
        { type: "view", view: "scope" },
        { type: "view", view: "setup" },
      ],
      startState("setup", "mail"),
    );
    expect(state.setupPage).toBe("tool:mail");
    expect(state.setupDrafts).toEqual({ "value/mail/email": "me@example.com" });
  });

  // Regression (P14): a tab click left the tour bar naming the tab it was on before.
  it.each([
    ["a stop's tab moves the tour there", ["audiohub"], "tasks", "tasks"],
    ["a picked tool's tab is a stop", ["whiteboard"], "boards", "boards"],
    ["an unpicked tool's tab is not", ["whiteboard"], "voice", "chat"],
    ["Setup is not a stop", null, "setup", "chat"],
  ] as const)("%s", (_, picks, view, stop) => {
    const state = run([
      ...(picks ? [{ type: "setupPicks", picks } as const] : []),
      { type: "tour", stop: "chat" },
      { type: "view", view },
    ]);
    expect(state.view).toBe(view);
    expect(state.tourStop).toBe(stop);
  });
});
