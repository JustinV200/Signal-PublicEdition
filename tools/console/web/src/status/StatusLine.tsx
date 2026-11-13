// The status line: the app name and the connection in words (inert text; the
// claimed session's label is in its tooltip), how fresh the data is with the
// Refresh button, and the Help button on the right; then the nine view tabs
// (the one the console tour is showing is marked `◂ tour`).
import type { ReactNode } from "react";
import { boardViewWords, useStore } from "../state";
import type { AppState, View } from "../state";
import { useTicker } from "../time";
import { Button } from "../ui";
import { Freshness } from "./Freshness";
import { PhaseDot, toDotPhase } from "./PhaseDot";
import styles from "./status.module.css";
import { Tab } from "./Tab";
import { turnWords } from "./turnWords";

const TICK_MS = 1000;
const MS_PER_SECOND = 1000;
const APP_NAME = "Signal console";
const NO_SESSION_DETAIL = "No Claude Code session has claimed the console";

interface ConnectionText {
  /** Changes when the wording changes (not on every clock tick). */
  key: string;
  node: ReactNode;
  /** Secondary detail for the tooltip. */
  detail: string;
  warn?: boolean;
}

function connectionText(state: AppState, now: number): ConnectionText {
  const { connection, server } = state;
  if (connection.status === "offline") {
    const seconds = Math.max(0, Math.ceil((connection.retryAt - now) / MS_PER_SECOND));
    const node = (
      <>
        Not connected <span className={styles.sep}>·</span> retrying in {seconds}s
      </>
    );
    return { key: "offline", node, detail: "The console backend is not answering", warn: true };
  }
  if (!server) return { key: "connecting", node: "Connecting…", detail: "" };
  if (!server.orchestrator.claimed) {
    return { key: "none", node: "Not connected", detail: NO_SESSION_DETAIL, warn: true };
  }
  const detail = `Session: ${server.orchestrator.label}`;
  const { turn } = server.orchestrator;
  if (turn.state === "idle") return { key: "idle", node: "Connected to Claude", detail };
  const node = (
    <>
      Connected to Claude <span className={styles.sep}>·</span> {turnWords(turn, now)}
    </>
  );
  // Stale is a warning: worded, and in the warning colour as well.
  return { key: turn.state, node, detail, warn: turn.state === "stale" };
}

/** The Tasks tab's words: `3 active · 1 needs you`, or `none active`. */
function taskTabWords({ tasks }: AppState): string {
  if (!tasks || tasks.active.length === 0) return "none active";
  const needs = tasks.needsYou ? ` · ${tasks.needsYou} needs you` : "";
  return `${tasks.active.length} active${needs}`;
}

/** The status line; a tab click switches the view, Help toggles the panel. */
export function StatusLine() {
  const { state, dispatch } = useStore();
  const now = useTicker(TICK_MS);
  const connection = connectionText(state, now);
  const phase = toDotPhase(state.server?.voice);
  const boardView = state.server?.board.view;
  const tasksWords = taskTabWords(state);
  const show = (view: View) => () => dispatch({ type: "view", view });

  return (
    <header className={styles.bar}>
      <div className="col">
        <div className={styles.titleRow}>
          <span className={`hud-label ${styles.appName}`}>{APP_NAME}</span>
          <span
            key={connection.key}
            className={`${styles.connection} ${connection.warn ? styles.warn : ""}`}
            title={connection.detail || undefined}
          >
            {connection.node}
          </span>
          <span className={styles.help}>
            <Freshness now={now} />
            <Button onClick={() => dispatch({ type: "help", open: !state.helpOpen })}>
              {state.helpOpen ? "Close help" : "? Help"}
            </Button>
          </span>
        </div>
        <div className={styles.tabs} role="tablist" aria-label="views">
          <Tab
            name="Scope"
            hint="Ctrl+1"
            active={state.view === "scope"}
            onClick={show("scope")}
            textKey="scope"
          />
          <Tab
            name="Chat"
            hint="Ctrl+2"
            active={state.view === "chat"}
            onClick={show("chat")}
            textKey="chat"
          />
          <Tab
            name="Voice"
            hint="Ctrl+3"
            active={state.view === "voice"}
            onClick={show("voice")}
            textKey={phase}
          >
            <PhaseDot phase={phase} />
            {phase}
          </Tab>
          <Tab
            name="Boards"
            hint="Ctrl+4"
            active={state.view === "boards"}
            onClick={show("boards")}
            textKey={boardView ?? "none"}
          >
            {boardView ? `showing ${boardViewWords(boardView)}` : "nothing showing"}
          </Tab>
          <Tab
            name="Tasks"
            hint="Ctrl+5"
            active={state.view === "tasks"}
            onClick={show("tasks")}
            textKey={tasksWords}
          >
            {tasksWords}
          </Tab>
          <Tab
            name="Devices"
            hint="Ctrl+6"
            active={state.view === "devices"}
            onClick={show("devices")}
            textKey="devices"
          />
          <Tab
            name="Models"
            hint="Ctrl+7"
            active={state.view === "models"}
            onClick={show("models")}
            textKey="models"
          />
          <Tab
            name="Tools"
            hint="Ctrl+8"
            active={state.view === "tools"}
            onClick={show("tools")}
            textKey="tools"
          />
          <Tab
            name="Setup"
            hint="Ctrl+9"
            active={state.view === "setup"}
            onClick={show("setup")}
            textKey="setup"
          />
        </div>
      </div>
    </header>
  );
}
