// The 401 state: a calm, left-aligned block and no input line. Login is
// retried on hashchange and window focus by the state package.
import styles from "./app.module.css";

/** Shown whenever the backend answers 401. */
export function SignIn() {
  return (
    <div className={`col ${styles.signIn}`}>
      <div className={styles.title}>signal console</div>
      <div>not signed in</div>
      <div className={styles.muted}>
        run <code>console open</code> in a terminal to open a signed-in window
      </div>
    </div>
  );
}
