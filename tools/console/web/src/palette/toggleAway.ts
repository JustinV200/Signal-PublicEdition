// What `I'm away` and `I'm back` in Commands do: the same POST /api/away as
// System's YOU buttons, for the brief's default 3 days. The new state comes
// back on the event stream (the server re-reads away mode every second), so
// the title row and the next Commands list follow by themselves. A failure
// lands in Chat as a console note, since Commands has closed by then.
import type { Dispatch } from "react";
import { setAway, UnauthorizedError } from "../api";
import type { StoreAction } from "../state";

/**
 * Turns away mode on or off.
 *
 * @param isAway True for `I'm away`, false for `I'm back`.
 * @param dispatch The store's dispatch, for a sign-out or the failure note.
 */
export async function toggleAway(isAway: boolean, dispatch: Dispatch<StoreAction>): Promise<void> {
  try {
    await setAway(isAway, "");
  } catch (failure) {
    // Signed out: the sign-in page replaces everything, so a note would only wait unseen.
    if (failure instanceof UnauthorizedError) {
      dispatch({ type: "auth", auth: "out" });
      return;
    }
    const reason = failure instanceof Error ? failure.message : String(failure);
    const command = isAway ? "I'm away" : "I'm back";
    const now = Date.now();
    // A note row, like the server's own notices, so the failure stays in words.
    dispatch({
      type: "server",
      event: {
        type: "note",
        data: {
          id: `local-away-${crypto.randomUUID()}`,
          text: `${command} failed: ${reason}. Try again from System's YOU group.`,
          at: now,
        },
      },
      now,
    });
  }
}
