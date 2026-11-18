// The 401 state, in the app's frame: the app name, why the page is signed
// out (the server's words, so an expired key reads differently from a
// missing token), then the command that opens a signed-in window, with Copy.
// No input line. Login is retried on hashchange and window focus by the
// state package.
import { NOT_SIGNED_IN } from "../api";
import { useStore } from "../state";
import { APP_NAME } from "../status";
import { OpenCommand } from "../ui";
import styles from "./app.module.css";

// `console open` opens a window of its own; whether Edge reuses this one is not verified.
const LEAD = "Run this in a terminal. It starts the console if needed and opens a signed-in window";

/** The server's reason as a sentence: capital first letter, full stop. */
function asSentence(reason: string): string {
  return `${reason.charAt(0).toUpperCase()}${reason.slice(1)}.`;
}

/** Shown whenever the backend answers 401. */
export function SignIn() {
  const { state } = useStore();
  return (
    <div className={`frame view ${styles.signIn}`}>
      <div className="hud-label">{APP_NAME}</div>
      {/* Worded and bold; the warning colour only repeats it. */}
      <div className={styles.cause}>{asSentence(state.signOutReason ?? NOT_SIGNED_IN)}</div>
      <OpenCommand lead={LEAD} command={state.openCommand} />
    </div>
  );
}
