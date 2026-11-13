// The help panel: what each view does, what buttons and messages do, and the
// shortcuts. Opens from the status line's Help button, closes from its own
// button or Esc.
import { useStore } from "../state";
import { Button } from "../ui";
import styles from "./help.module.css";

/** What each view is for: the panel's list and the console tour's stops, in tab order. */
export const VIEW_HELP = [
  ["Scope", "the radar: Claude, the voice hub, the board and pending requests at a glance."],
  [
    "Chat",
    "type a message and press Enter. Claude's replies land here, including work it finished on its own.",
  ],
  ["Voice", "start or stop the voice hub and read what it heard and said."],
  [
    "Boards",
    "pick a saved board, read its preview, then send it to the projector. Realign re-fits the board; Update redraws it from live data.",
  ],
  [
    "Tasks",
    "what Claude is working on: each task's status number, %, next step and what it needs from you.",
  ],
  [
    "Devices",
    "the projector, webcam, voice hub, glasses, browsers and Docker, live; Open camera shows the webcam. Your Away/Here switch acts at once, without Claude.",
  ],
  [
    "Models",
    "the model and thinking effort for new orchestrator sessions and for voice. A pick saves at once, without Claude.",
  ],
  [
    "Tools",
    "every Signal tool: Active, Down or Not set up, with a button that opens setup at that tool.",
  ],
  [
    "Setup",
    "the setup wizard: pick tools, run each step, fill in settings, then the tour. Progress saves as you go.",
  ],
] as const;

const SHORTCUTS = [
  ["Enter", "send"],
  ["Shift+Enter", "new line"],
  ["↑ / ↓", "earlier messages"],
  ["Ctrl+K", "command list"],
  ["Ctrl+1 to 9", "Scope / Chat / Voice / Boards / Tasks / Devices / Models / Tools / Setup"],
  ["Esc", "close this, else back to the Scope"],
] as const;

/** The panel; renders nothing while closed. */
export function HelpPanel() {
  const { state, dispatch } = useStore();
  if (!state.helpOpen) return null;
  return (
    <section className={`col ${styles.panel} anim-fade`} aria-label="help">
      <div className={styles.head}>
        <span className={styles.title}>What the console does</span>
        <Button onClick={() => dispatch({ type: "help", open: false })} hint="Esc">
          Close
        </Button>
      </div>
      <dl className={styles.list}>
        {VIEW_HELP.map(([name, text]) => (
          <div key={name} className={styles.item}>
            <dt>{name}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
      <p className={styles.note}>
        Messages you type go to Claude. Buttons run at once in the console, without Claude:
        "Working…" means it is running, and the action's row in Chat then reads done with what
        happened, or failed with why. The page updates by itself; "updated 3s ago" at the top says
        how fresh it is, and Refresh re-reads everything now.
      </p>
      <dl className={styles.list}>
        {SHORTCUTS.map(([keys, text]) => (
          <div key={keys} className={styles.item}>
            <dt>
              <kbd>{keys}</kbd>
            </dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
