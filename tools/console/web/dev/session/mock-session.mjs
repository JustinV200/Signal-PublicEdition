// The mock's signed-out and server-down sides, for mock-server.mjs: the 401
// body the real server sends (its reason and the `console open` command
// line), and `--down-after S`, which makes the mock stop answering S seconds
// after it starts, for DOWN_FOR_MS, so the server-down notice can be seen.

// A made-up checkout path with a space in it, like the real server's own absolute path.
export const OPEN_COMMAND =
  'uv run --project "C:\\Example Folder\\Signal\\tools\\console" --frozen --no-sync console open';
export const NOT_SIGNED_IN = "not signed in";
export const BAD_LOGIN_KEY = "that login key is wrong, used or expired";
const DOWN_FOR_MS = 60_000;
const MS_PER_SECOND = 1000;

/** Answers 401 the way the real server does: the reason and the command, nothing secret. */
export function refuseSignedOut(json, res, reason) {
  json(res, 401, { error: reason, openCommand: OPEN_COMMAND });
}

/**
 * The `--down-after S` switch. `isDown()` says whether to drop a request;
 * `onDown` runs once as the outage starts (to cut the open event streams).
 * With no seconds given it never goes down.
 */
export function downSwitch(seconds, onDown) {
  let down = false;
  if (Number.isFinite(seconds)) {
    setTimeout(() => {
      down = true;
      console.log(`mock: not answering for ${DOWN_FOR_MS / MS_PER_SECOND}s`);
      onDown();
      setTimeout(() => {
        down = false;
        console.log("mock: answering again");
      }, DOWN_FOR_MS);
    }, seconds * MS_PER_SECOND);
  }
  return { isDown: () => down };
}
