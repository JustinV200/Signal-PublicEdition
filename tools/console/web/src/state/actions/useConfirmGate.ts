// The one way a button or a palette command runs an action: it asks on the
// input line first when the confirm rule says so, else it runs at once. The
// answer is here too, so the Yes / No buttons and the y / n keys share it.
import { useCallback, useMemo } from "react";
import type { ActionArgs, ActionName } from "../../api";
import { useStore } from "../store";
import { confirmPrompt } from "./confirmRule";

export interface ConfirmGate {
  /** Runs `action` at once, or puts its question on the input line first. */
  request: (action: ActionName, args?: ActionArgs) => void;
  /** Answers the open question: yes runs its action; either way the line closes. */
  answer: (yes: boolean) => void;
}

/** The gate bound to the store's board state, input mode and sender. */
export function useConfirmGate(): ConfirmGate {
  const { state, dispatch, sender } = useStore();
  const board = state.server?.board;
  const mode = state.inputMode;

  const request = useCallback(
    (action: ActionName, args?: ActionArgs) => {
      const prompt = confirmPrompt(action, args, board);
      if (prompt) dispatch({ type: "inputMode", mode: { kind: "confirm", prompt, action, args } });
      else void sender.runAction(action, args);
    },
    [board, dispatch, sender],
  );

  const answer = useCallback(
    (yes: boolean) => {
      if (yes && mode.kind === "confirm") void sender.runAction(mode.action, mode.args);
      dispatch({ type: "inputMode", mode: { kind: "text" } });
    },
    [mode, dispatch, sender],
  );

  return useMemo(() => ({ request, answer }), [request, answer]);
}
