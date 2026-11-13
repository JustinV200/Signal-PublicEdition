// The scope buffer, the landing view: the radar on the left and a text
// readout of the same facts on the right (Claude, voice hub, board, pending
// requests). No controls here; the tabs hold them.
import { useStore } from "../../state";
import { useTicker } from "../../time";
import { usePageVisible } from "../../ui";
import { buildBlips, buildReadout } from "./blips";
import { Scope } from "./Scope";
import styles from "./scope.module.css";

const TICK_MS = 1000;
const HINT = "Live state at a glance. The controls are in Chat, Voice and Boards.";

/** The scope view. */
export function ScopeView() {
  const { state } = useStore();
  const now = useTicker(TICK_MS);
  const visible = usePageVisible();
  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Scope</span>
        <span className={styles.hint}>{HINT}</span>
      </div>
      <div className={styles.columns}>
        <Scope blips={buildBlips(state, now)} sweeping={visible} />
        <dl className={styles.readout} aria-label="live state">
          {buildReadout(state, now).map((row) => (
            <div key={row.label} className={styles.readoutRow}>
              <dt className="hud-label">{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
