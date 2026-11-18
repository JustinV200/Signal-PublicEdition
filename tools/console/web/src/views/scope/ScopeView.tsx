// The scope buffer, the landing view: the radar on the left and a readout on
// the right that starts with what needs the owner (NEEDS YOU, CHAT, CLAUDE,
// VOICE, BOARD, YOU, and RUNNING while a button runs). Each readout row is a
// button that opens its view, as a click on a blip does; the tabs hold the controls.
import { useStore } from "../../state";
import type { View } from "../../state";
import { useTicker } from "../../time";
import { usePageVisible } from "../../ui";
import { buildBlips } from "./blips";
import { signalWords } from "./radar";
import { buildReadout } from "./readout";
import { Scope } from "./Scope";
import styles from "./scope.module.css";

const TICK_MS = 1000;

/** The scope view. */
export function ScopeView() {
  const { state, dispatch } = useStore();
  const now = useTicker(TICK_MS);
  const visible = usePageVisible();
  // The server's keepalive drives the sweep: a stale or dropped stream stops it, with words.
  const signal = signalWords(state.syncedAt, state.connection.status === "offline", now);
  const open = (view: View) => dispatch({ type: "view", view });
  return (
    <div className="frame view">
      <div className="view-header">
        <span className="hud-label">Scope</span>
      </div>
      <div className={styles.columns}>
        <Scope
          blips={buildBlips(state, now)}
          signal={signal}
          sweeping={visible && signal === null}
          onOpen={open}
        />
        <nav className={styles.readout} aria-label="live state">
          {buildReadout(state, now).map((row) => (
            <button
              key={row.key}
              type="button"
              className={styles.row}
              // The full value, for when a long one is cut short with an ellipsis.
              title={row.value}
              onClick={() => open(row.view)}
            >
              <span className="hud-label">{row.label}</span>
              <span className={styles.value}>{row.value}</span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
