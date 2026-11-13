// The last row while the orchestrator is busy: `claude  working m:ss`. The
// clock is the signal; no spinner. It fades in on appear and out on leave.
import { useEffect, useState } from "react";
import { formatClock, formatElapsed, useTicker } from "../../time";
import styles from "./chat.module.css";

const TICK_MS = 1000;
const LEAVE_MS = 120;
const GUTTER_GAP = "  ";

/** Shows while `busySince` is set, then lingers 120ms to fade out. */
export function WorkingRow({ busySince }: { busySince: number | null }) {
  // Keep the last start time through the fade-out so the row can still render.
  const [shownSince, setShownSince] = useState(busySince);
  const [leaving, setLeaving] = useState(false);
  if (busySince !== null && busySince !== shownSince) {
    setShownSince(busySince);
    setLeaving(false);
  }
  if (busySince === null && shownSince !== null && !leaving) setLeaving(true);

  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => {
      setShownSince(null);
      setLeaving(false);
    }, LEAVE_MS);
    return () => clearTimeout(timer);
  }, [leaving]);

  const now = useTicker(TICK_MS);
  if (shownSince === null) return null;
  return (
    <div className={`${styles.msg} ${styles.working} ${leaving ? "anim-fade-out" : "anim-fade"}`}>
      <div className={styles.gutter}>
        {formatClock(shownSince)}
        {GUTTER_GAP}claude
      </div>
      <div>
        working <span className={styles.clock}>{formatElapsed(now - shownSince)}</span>
      </div>
    </div>
  );
}
