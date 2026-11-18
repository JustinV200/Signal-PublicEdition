// How fresh the device rows are, for the DEVICES group's header, shown only
// when it matters: `Not updating: <why>`, `checking…` before the first read, or
// `updated 20s ago` once the last read is past STALE_AFTER_MS (the poll runs
// every 5 s, so a younger age is noise). It ticks on its own, so only these
// words re-render every few seconds.
import { formatRelative, useTicker } from "../../time";
import styles from "./devices.module.css";
import type { DevicesState } from "./useDevices";

const AGE_TICK_MS = 5000;
const STALE_AFTER_MS = 15_000;

/** The header words for `useDevices`' last read, or nothing while it is fresh. */
export function DevicesMeta({ error, readAt }: Pick<DevicesState, "error" | "readAt">) {
  const now = useTicker(AGE_TICK_MS);
  if (!error && readAt !== null && now - readAt <= STALE_AFTER_MS) return null;
  return (
    <span className={styles.meta}>
      {error
        ? `Not updating: ${error}`
        : readAt
          ? `updated ${formatRelative(readAt, now)}`
          : "checking…"}
    </span>
  );
}
