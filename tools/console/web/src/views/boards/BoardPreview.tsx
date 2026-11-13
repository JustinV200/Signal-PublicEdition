// The preview of the picked board: name, description, save time, whether it
// is on the projector, and the "Send to projector" button with its warning
// that this replaces what is showing, plus Update for a board drawn from live
// data (a task grid or the to-do list). Text only: the whiteboard has no
// thumbnail endpoint yet. TODO: show a thumbnail when the daemon serves one.
import { usePendingActions } from "../../state";
import type { BoardRowInfo } from "../../state";
import { formatRelative } from "../../time";
import { Button } from "../../ui";
import styles from "./boards.module.css";

interface BoardPreviewProps {
  row: BoardRowInfo;
  showing: boolean;
  now: number;
  onSend: () => void;
  /** Redraw this board from its live source; shown only when it has one. */
  onUpdate: () => void;
}

const SEND_CAPTION = "Puts this board on the projector now, replacing what is showing.";
const UPDATE_CAPTION = "Update redraws it from the live tasks or plans, not the old save.";

/** The preview panel beside the list. */
export function BoardPreview({ row, showing, now, onSend, onUpdate }: BoardPreviewProps) {
  const pending = usePendingActions();
  return (
    <section className={styles.preview} aria-label="board preview">
      <div className={styles.previewName}>
        {row.name}
        {showing && <span className={styles.tag}>on the projector now</span>}
      </div>
      <p className={styles.description}>{row.description ?? "No description saved."}</p>
      {row.updatedAt !== null && (
        <p className={styles.meta}>saved {formatRelative(row.updatedAt, now)}</p>
      )}
      <div className={styles.actions}>
        <Button
          primary
          onClick={onSend}
          pending={pending.has(row.action)}
          disabledReason={row.disabledReason}
        >
          Send to projector
        </Button>
        {row.updateArgs && (
          <Button onClick={onUpdate} pending={pending.has("board.update")}>
            Update
          </Button>
        )}
      </div>
      {!row.disabledReason && <p className={styles.caption}>{SEND_CAPTION}</p>}
      {row.updateArgs && <p className={styles.caption}>{UPDATE_CAPTION}</p>}
    </section>
  );
}
