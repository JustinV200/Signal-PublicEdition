// Optimistic send flow: a local `sending` row appears at once, takes the
// server's id when the POST resolves, and turns `failed` with `[retry]` if
// the request itself fails. Text and actions share one path.
import type { Dispatch } from "react";
import { sendAction, sendText, UnauthorizedError } from "../../api";
import type { ActionArgs, ActionName } from "../../api";
import type { LocalMessage, Origin, StoreAction } from "../types";
import { actionLabel } from "./actionLabels";

export interface Sender {
  /** Sends a chat message to the orchestrator. */
  send: (text: string) => Promise<void>;
  /** Runs one of the fixed actions through the backend. */
  runAction: (action: ActionName, args?: ActionArgs) => Promise<void>;
  /** Re-sends a failed message's origin as a new message. */
  retry: (origin: Origin) => Promise<void>;
}

let localCounter = 0;

function localId(): string {
  localCounter += 1;
  return `local-${Date.now()}-${localCounter}`;
}

function postOrigin(origin: Origin): Promise<{ id: string }> {
  return origin.kind === "text" ? sendText(origin.text) : sendAction(origin.action, origin.args);
}

function describe(origin: Origin): Pick<LocalMessage, "text" | "kind"> {
  return origin.kind === "text"
    ? { text: origin.text, kind: "chat" }
    : { text: actionLabel(origin.action, origin.args), kind: "action" };
}

/** Builds the sender bound to the store's dispatch. */
export function createSender(dispatch: Dispatch<StoreAction>): Sender {
  async function deliver(origin: Origin): Promise<void> {
    const tempId = localId();
    dispatch({
      type: "sendStarted",
      message: {
        id: tempId,
        role: "you",
        at: Date.now(),
        delivery: "sending",
        origin,
        ...describe(origin),
      },
    });
    try {
      const { id } = await postOrigin(origin);
      dispatch({ type: "sendAccepted", tempId, id });
    } catch (error) {
      if (error instanceof UnauthorizedError) dispatch({ type: "auth", auth: "out" });
      const message = error instanceof Error ? error.message : String(error);
      dispatch({ type: "sendFailed", tempId, error: message });
    }
  }

  return {
    send: (text) => deliver({ kind: "text", text }),
    runAction: (action, args) => deliver({ kind: "action", action, args }),
    retry: (origin) => deliver(origin),
  };
}
