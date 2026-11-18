// The status line: the quiet app name and the connection in words (inert text; the
// full words and the claimed session's label are in its tooltip), the owner's
// away state while not Here (`Away until Thu 17:00`, `Away`, `Asleep`), the pointer
// to System while one of the console's checks isn't ok, how fresh the data is
// with the Refresh button (only when stale or offline), and the Help button
// on the right; then the tab row (TabRow), whose short status
// words keep it to one row at 1280px and 1024px.
import { Fragment } from "react";
import { useStore } from "../state";
import { useTicker } from "../time";
import { Button } from "../ui";
import { titleAwayWords } from "./awayWords";
import { connectionWords } from "./connectionWords";
import { Freshness } from "./Freshness";
import { HealthPointer } from "./HealthPointer";
import styles from "./status.module.css";
import { TabRow } from "./tabs/TabRow";
import { APP_NAME } from "./titleWords";

const TICK_MS = 1000;

/** The connection words, each part after the first behind a faint `·`. */
function ConnectionParts({ parts }: { parts: string[] }) {
  return parts.map((part, index) => (
    <Fragment key={index}>
      {index > 0 && <span className={styles.sep}> · </span>}
      {part}
    </Fragment>
  ));
}

/**
 * The status line; Help toggles the panel.
 *
 * @param showSetupTab The Setup tab shows (the shell works it out from the picks).
 */
export function StatusLine({ showSetupTab }: { showSetupTab: boolean }) {
  const { state, dispatch } = useStore();
  const now = useTicker(TICK_MS);
  const connection = connectionWords(state, now);
  const away = titleAwayWords(state.server?.away);

  return (
    <header className={styles.bar}>
      <div className="frame">
        <div className={styles.titleRow}>
          <span className={styles.appName}>{APP_NAME}</span>
          <span className={styles.connection} title={connection.title}>
            <span key={connection.key} className={connection.warn ? styles.warn : undefined}>
              <ConnectionParts parts={connection.parts} />
            </span>
          </span>
          {/* The live region speaks the state without its clock, so it isn't re-read every second. */}
          <span role="status" className={styles.srOnly}>
            {connection.spoken}
          </span>
          {away && (
            <span className={styles.away} title={away.tooltip}>
              {away.word}
              {away.until && <span className={styles.awayUntil}>{away.until}</span>}
            </span>
          )}
          <span className={styles.help}>
            <span className={styles.pointer}>
              <HealthPointer />
            </span>
            <Freshness now={now} />
            <Button onClick={() => dispatch({ type: "help", open: !state.helpOpen })}>
              {state.helpOpen ? "Close help" : "? Help"}
            </Button>
          </span>
        </div>
        <TabRow showSetupTab={showSetupTab} />
      </div>
    </header>
  );
}
