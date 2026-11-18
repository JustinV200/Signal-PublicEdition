// The mock console's action words, kept in step with the real server
// (signal_console.actions): what each button echoes into chat, which board
// step it runs, and what it says when done. Pure; mock-server.mjs owns the state.

// The real server's words for a message with no Claude session to go to.
export const NOT_LINKED = "No Claude session yet. Run `console claim` in Claude Code to link one.";

// The real server's 409 words for a second action on a busy lock (server/action_runner.py).
export const BUSY_WORDS = {
  voice: "Voice is still starting or stopping; wait for that to finish.",
  board: "The whiteboard is still busy with the last button; wait for that to finish.",
};

/**
 * The chat row a button's action echoes, like the real server's labels.
 * @param {string} action e.g. "board.load".
 * @param {string | undefined} name The saved board's name, for load and update.
 * @returns {string | undefined} The echo, or undefined for an unknown action.
 */
export function actionEcho(action, name) {
  const echoes = {
    "voice.start": "Start voice",
    "voice.stop": "Stop voice",
    "board.load": `Send to projector: "${name}"`,
    "board.todo": "Send to projector: to-do list",
    "board.idle": "Send to projector: idle board",
    "board.realign": "Realign whiteboard",
    "board.calibrate": "Full calibrate",
    "board.update": name ? `Show live version: "${name}"` : "Update the to-do list",
  };
  return echoes[action];
}

/**
 * The board step an action runs: like the real server, Update with no save
 * name redraws the to-do list, so it runs as a board.todo (kept because a page
 * tab loaded before the update could still send it).
 * @param {string} action A board action.
 * @param {string | undefined} name The saved board's name, if any.
 * @returns {string} The action to run.
 */
export function boardStep(action, name) {
  return action === "board.update" && !name ? "board.todo" : action;
}

/**
 * The daemon's view after a board step: `todo`, `idle` or `items`.
 * @param {string} step From boardStep.
 * @returns {string} The view.
 */
export function boardView(step) {
  return { "board.todo": "todo", "board.idle": "idle" }[step] ?? "items";
}

/**
 * The server's done words for a board step.
 * @param {string} step From boardStep.
 * @param {string | undefined} name The saved board's name, for load.
 * @returns {string} The result line.
 */
export function boardResult(step, name) {
  const results = {
    "board.load": `Sent "${name}" to the projector.`,
    "board.todo": "The to-do list is on the projector.",
    "board.idle": "The idle board is on the projector.",
    "board.realign": "Realign finished. calibrated: reprojection error 0.38 px",
    "board.calibrate": "Calibration finished. calibrated: reprojection error 0.41 px",
  };
  // The only refresher save in the mock's saves is the task grid.
  return results[step] ?? "Redrew the task grid.";
}
