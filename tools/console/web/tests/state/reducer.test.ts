// The reducer must survive the server's replay-on-connect: duplicate ids
// collapse (first wins), time order holds, notes join the stream, and local
// delivery state outlives the echo.
import { describe, expect, it } from "vitest";
import type { Message, Note } from "../../src/api";
import { initialState, reduce } from "../../src/state";
import type { AppState, StoreAction } from "../../src/state";

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
    const note: Note = { id: "n", at: "2026-10-19T14:01:30Z", text: "orchestrator changed" };
    const state = run([
      messageEvent({ id: "b", at: "2026-10-19T14:02:00Z", text: "second" }),
      noteEvent(note),
      messageEvent({ id: "a", at: "2026-10-19T14:01:00Z", text: "first" }),
      messageEvent({ id: "b", at: "2026-10-19T14:02:00Z", text: "second (replayed)" }),
      noteEvent(note),
    ]);
    expect(state.messages.map((m) => m.id)).toEqual(["a", "n", "b"]);
    expect(state.messages[1]).toMatchObject({ kind: "note", text: "orchestrator changed" });
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
            data: { id: "d1", messageId: "m1", status: "failed", error: "no orchestrator" },
          },
          now: 0,
        },
      ],
      sent,
    );
    expect(failed.messages[0]).toMatchObject({
      delivery: "failed",
      error: "no orchestrator",
      origin: { kind: "text", text: "hi" },
    });
  });
});
