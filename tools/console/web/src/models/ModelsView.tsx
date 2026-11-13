// The Models page (Ctrl+7): a header and a hint, then the model strip with
// its orchestrator and voice pickers. It used to sit under the status line on
// every view; it lives on its own tab so the main views stay uncluttered.
import { ModelStrip } from "./ModelStrip";
import styles from "./models.module.css";

const HINT =
  "Pick the model and thinking effort for new orchestrator sessions and for voice. A pick saves at once, without asking Claude.";

/** The models view. */
export function ModelsView() {
  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Models</span>
      </div>
      <p className={styles.viewHint}>{HINT}</p>
      <ModelStrip />
    </div>
  );
}
