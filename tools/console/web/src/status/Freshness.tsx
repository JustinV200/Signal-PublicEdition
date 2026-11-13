// The status line's freshness block: `updated 3s ago` (when the server last
// sent anything, keepalives included) and a labelled Refresh button that
// re-reads everything now (the state, the tasks and the open view's polls).
import { STALL_MS } from "../api";
import { useStore } from "../state";
import { formatRelative } from "../time";
import { Button } from "../ui";
import styles from "./status.module.css";

const MS_PER_SECOND = 1000;
const SECONDS_PER_MINUTE = 60;

/** `updated 3s ago`, `updated 5m ago`, or `not updated yet` before the first byte. */
export function freshnessWords(syncedAt: number | null, now: number): string {
  if (syncedAt === null) return "not updated yet";
  const seconds = Math.max(0, Math.floor((now - syncedAt) / MS_PER_SECOND));
  if (seconds < SECONDS_PER_MINUTE) return `updated ${seconds}s ago`;
  return `updated ${formatRelative(syncedAt, now)}`;
}

/** The words and the Refresh button; `now` comes from the status line's ticker. */
export function Freshness({ now }: { now: number }) {
  const { state, dispatch } = useStore();
  const { syncedAt } = state;
  // Past the stall limit the stream is being reopened: the words say how old, the colour repeats it.
  const isStale = syncedAt === null || now - syncedAt > STALL_MS;
  return (
    <span className={styles.freshness}>
      <span
        className={isStale ? styles.warn : undefined}
        title="When the console last heard from its server"
      >
        {freshnessWords(syncedAt, now)}
      </span>
      <Button onClick={() => dispatch({ type: "refresh" })}>Refresh</Button>
    </span>
  );
}
