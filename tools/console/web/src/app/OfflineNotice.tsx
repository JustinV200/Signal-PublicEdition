// The server-down notice at the top of the view: once the console server has
// not answered for OFFLINE_NOTICE_MS, the status line's short words get the
// reason in full and the cached `console open` command with Copy. A blip
// shorter than that (a restart, a slow wake) shows only in the status line.
import { useStore } from "../state";
import { useTicker } from "../time";
import { OpenCommand } from "../ui";
import styles from "./app.module.css";

/** How long the server must be silent before the notice shows. */
export const OFFLINE_NOTICE_MS = 10_000;
const TICK_MS = 1000;
const CAUSE = "The console server isn't answering.";
const DETAIL =
  "This page keeps retrying and reconnects by itself, still signed in, once the server is back.";
const LEAD = "If the server has stopped, this starts it again and opens a signed-in window";

/** The notice, or nothing while the server answers or has been silent under 10 s. */
export function OfflineNotice() {
  const { state } = useStore();
  const now = useTicker(TICK_MS);
  const { connection } = state;
  if (connection.status !== "offline" || now - connection.since < OFFLINE_NOTICE_MS) return null;
  return (
    // No live role: the status line's own region already speaks "Console server not answering".
    <div className={`frame ${styles.notice}`}>
      {/* Worded and bold; the warning colour only repeats it. */}
      <div className={styles.cause}>{CAUSE}</div>
      <div>{DETAIL}</div>
      <OpenCommand lead={LEAD} command={state.openCommand} />
    </div>
  );
}
