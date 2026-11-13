// Human text for an action while its row is still `sending`. The server's
// echo replaces it with the canonical wording once the action is accepted.
import type { ActionArgs, ActionName } from "../../api";

/** Plain-language label for an action, e.g. `load board 'lecture'`. */
export function actionLabel(action: ActionName, args?: ActionArgs): string {
  switch (action) {
    case "voice.start":
      return "start the voice hub";
    case "voice.stop":
      return "stop the voice hub";
    case "board.load":
      return `load board '${args?.name ?? ""}'`;
    case "board.todo":
      return "show the todo list";
    case "board.idle":
      return "show the idle board";
    case "board.realign":
      return "realign the board";
    case "board.calibrate":
      return "fully calibrate the board";
    case "board.update":
      return args?.view === "todo" ? "update the to-do list" : `update board '${args?.name ?? ""}'`;
  }
}

/** The question shown in confirm mode before a voice action or a full calibrate runs. */
export function confirmPrompt(action: ActionName): string {
  // A full calibrate flashes bright markers across the room, so it says what it does.
  if (action === "board.calibrate") return "Flash calibration markers on the projector?";
  return `${actionLabel(action)}?`;
}
