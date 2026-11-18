// The help panel: three short blocks, what each tab is for, the keys (the
// tabs show theirs only as tooltips, so this is the list) and what to do when
// something is wrong. Opens and closes from the status line's Help button
// (`Close help` while open) or Esc; it has no close button of its own. The
// shell puts it between the status line and the view, outside the view's
// scroller, so it shows at once wherever the view is scrolled, and it
// scrolls inside its own box past 60vh. `Take the tour` starts TourBar at its
// last stop.
import { resumeTourStop, useStore } from "../state";
import { Button, OpenCommand } from "../ui";
import styles from "./help.module.css";

/** What each tab is for, in tab order: the panel's list and the console tour's words (state's tourStops orders the tour). */
export const VIEW_HELP = [
  [
    "Scope",
    "the home view: Claude, Voice, the projector, tasks and what needs you at a glance. Click a mark or a readout row to open its tab; the controls are there.",
  ],
  [
    "Chat",
    "type and press Enter: it goes to Claude, whose replies land here. Link Claude by pasting Setup's claim sentence into your main Claude Code session. Other tabs' buttons run at once, without Claude; their results show here too. Ctrl+K opens Commands, every button by name. Hand to Claude sends a failed setup step to Claude.",
  ],
  ["Voice", "start or stop Voice, then read what it heard and said."],
  [
    "Boards",
    "pick the to-do list, the idle board or a saved board, read its preview, then Send to projector. A save with live data has Show live version (redrawn from the live tasks) and Show saved copy. Realign whiteboard re-fits the projection.",
  ],
  [
    "Tasks",
    "what Claude is working on: each task's state (needs you, review, building, queued, done), %, next step and what it needs from you.",
  ],
  [
    "System",
    "Here / Away; the console's own checks and every tool's health (a row that isn't ok says how to fix it); the devices, checked every 5 s while System is open (Open camera only shows the webcam, it moves nothing); the model and effort for new Claude sessions and for Voice (a pick saves at once); dark or light.",
  ],
  [
    "Setup",
    "the setup wizard: pick tools, run each step, fill in settings, then the tour. Progress saves as you go. Its tab shows while a picked tool is unfinished; Open setup in System reaches it any time.",
  ],
] as const;

const KEYS = [
  ["Enter", "send"],
  ["Shift+Enter", "new line"],
  ["↑ / ↓", "earlier messages"],
  ["Ctrl+K", "Commands"],
  ["Ctrl+1 to 6", "Scope / Chat / Voice / Boards / Tasks / System (Ctrl+7 and 8 also System)"],
  ["Ctrl+9", "Setup"],
  ["← / →", "on a tab: move along the tabs (Enter opens one)"],
  ["Home / End", "on a tab: the first or last tab"],
  ["y / n", "answer a question on the input line (Yes / No)"],
  ["Esc", "close Commands, a question or this help"],
] as const;

type TermRows = ReadonlyArray<readonly [string, string]>;

const WRONG_TEXT =
  'Start at System: its Console group checks the console itself and Tools checks each tool; a row that isn\'t ok says how to fix it. When the top reads "no update for 25s", Refresh re-reads everything now.';
const OPEN_LEAD =
  "If the page stays stuck or signs out, this starts the console again and opens a signed-in window";

/**
 * One block's terms and their words, in the shared label column.
 *
 * @param rows Each term with its words.
 * @param isKeys The terms are keys, so each shows as `<kbd>`.
 */
function TermList({ rows, isKeys = false }: { rows: TermRows; isKeys?: boolean }) {
  return (
    <dl className={styles.list}>
      {rows.map(([term, text]) => (
        <div key={term} className={styles.item}>
          <dt>{isKeys ? <kbd>{term}</kbd> : term}</dt>
          <dd>{text}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The panel; renders nothing while closed. */
export function HelpPanel() {
  const { state, dispatch } = useStore();
  if (!state.helpOpen) return null;
  // The tour action closes Help itself (state's reducer), and resumes at the last stop.
  const takeTour = () => dispatch({ type: "tour", stop: resumeTourStop(state.setupPicks) });
  // Close first, so Help doesn't cover System; a paused tour follows to System, one of its stops.
  const openSystem = () => {
    dispatch({ type: "help", open: false });
    dispatch({ type: "view", view: "system" });
  };
  return (
    // The inner box carries the name ("Help"), so it isn't announced twice.
    <section className={`frame anim-fade ${styles.helpFrame}`}>
      {/* Focusable, so its own scroll (past 60vh) works from the keyboard too. */}
      <div className={`col panel ${styles.help}`} tabIndex={0} role="group" aria-label="Help">
        <div className={styles.head}>
          <h2 className={styles.title}>What each tab is for</h2>
          <Button onClick={takeTour}>Take the tour</Button>
        </div>
        <TermList rows={VIEW_HELP} />
        <h2 className={styles.title}>Keys</h2>
        <TermList rows={KEYS} isKeys />
        <div className={styles.head}>
          <h2 className={styles.title}>If something is wrong</h2>
          <Button onClick={openSystem}>Open System</Button>
        </div>
        <p className={styles.note}>{WRONG_TEXT}</p>
        <OpenCommand lead={OPEN_LEAD} command={state.openCommand} />
      </div>
    </section>
  );
}
