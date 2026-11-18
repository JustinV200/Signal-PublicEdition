// The preview of the picked board: name, description, save time, whether it
// is on the projector, and its buttons (state's boardButtons): one primary
// "Send to projector", or for a save drawn from live data (a task grid)
// "Show live version" first and "Show saved copy" beside it. One caption says
// what the primary button does (for a live save, from what its refresher
// redraws it from); under the night view it says instead that a
// board sent stays hidden until the night ends (the whiteboard keeps it under
// the night sky). Text only: the whiteboard has no thumbnail endpoint yet.
// TODO: show a thumbnail when the daemon serves one.
import { boardButtons, usePendingActions } from "../../state";
import type { BoardButton, BoardRowInfo } from "../../state";
import { formatRelative } from "../../time";
import { Button } from "../../ui";
import styles from "./boards.module.css";

interface BoardPreviewProps {
  row: BoardRowInfo;
  showing: boolean;
  now: number;
  /** Whether the projector shows the night view, so a board sent stays hidden. */
  night: boolean;
  /** Run one of the preview's buttons. */
  onRun: (button: BoardButton) => void;
}

const SEND_CAPTION = "Puts this board on the projector now, replacing what is showing.";
const TASKS_CAPTION = "Redraws it from the live tasks and puts it on the projector.";
const TODO_CAPTION = "Redraws it from the live to-do list and puts it on the projector.";
const LIVE_CAPTION = "Redraws it from live data and puts it on the projector.";
const NIGHT_CAPTION = "Night view is on: boards you send stay hidden until it ends.";

/** What the primary button does for `row`, in the words of its refresher. */
function captionFor(row: BoardRowInfo, night: boolean): string {
  if (night) return NIGHT_CAPTION;
  if (!row.updateArgs) return SEND_CAPTION;
  if (row.refresher === "tasks") return TASKS_CAPTION;
  if (row.refresher === "todo") return TODO_CAPTION;
  return LIVE_CAPTION;
}

/** The preview panel beside the list (sticky, so it stays in view while a long list scrolls). */
export function BoardPreview({ row, showing, now, night, onRun }: BoardPreviewProps) {
  const pending = usePendingActions();
  const caption = captionFor(row, night);
  return (
    <section className={`panel ${styles.preview}`} aria-label="board preview">
      <div className={styles.previewName}>
        {row.name}
        {showing && <span className={styles.tag}>on the projector now</span>}
      </div>
      <p className={styles.description}>{row.description ?? "No description saved."}</p>
      {row.updatedAt !== null && (
        <p className={styles.meta}>saved {formatRelative(row.updatedAt, now)}</p>
      )}
      <div className={styles.actions}>
        {boardButtons(row).map((button) => (
          <Button
            key={button.label}
            primary={button.primary}
            onClick={() => onRun(button)}
            pending={pending.has(button.action)}
            disabledReason={row.disabledReason}
          >
            {button.label}
          </Button>
        ))}
      </div>
      {!row.disabledReason && <p className={styles.caption}>{caption}</p>}
    </section>
  );
}
