// The status line's freshness block, shown only when something is wrong: the
// stream has gone quiet past STALL_MS (`no update for 25s`) or the server is
// not answering (`updated 3s ago` until it goes stale). It carries a labelled
// Refresh button that re-reads everything now (the state, the tasks and the
// open view's polls); while all is well both stay hidden, and the `Refresh`
// command does the same from Ctrl+K.
import { isStreamStale } from "../api";
import { useStore } from "../state";
import { shortAge } from "../time";
import { Button } from "../ui";
import styles from "./status.module.css";

/** `updated 3s ago`, `no update for 25s` once stale, or `not updated yet` before the first byte. */
function freshnessWords(syncedAt: number | null, now: number): string {
  if (syncedAt === null) return "not updated yet";
  const ageMs = Math.max(0, now - syncedAt);
  if (isStreamStale(syncedAt, now)) return `no update for ${shortAge(ageMs)}`;
  return `updated ${shortAge(ageMs)} ago`;
}

/** The words and the Refresh button, or nothing while fresh and online; `now` is the status line's ticker. */
export function Freshness({ now }: { now: number }) {
  const { state, dispatch } = useStore();
  const { syncedAt, connection } = state;
  const stale = isStreamStale(syncedAt, now);
  if (!stale && connection.status !== "offline") return null;
  return (
    <span className={styles.freshness}>
      {/* Stale is worded (`no update for`); the warning colour only repeats it. */}
      <span
        className={stale ? styles.warn : undefined}
        title="When the console last heard from its server"
      >
        {freshnessWords(syncedAt, now)}
      </span>
      <Button onClick={() => dispatch({ type: "refresh" })}>Refresh</Button>
    </span>
  );
}
