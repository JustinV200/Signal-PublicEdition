// The boards buffer: a list of boards to pick from and a preview of the
// picked one with the only button that sends it to the projector. A row click
// or Up/Down only moves the `▸`; nothing loads until "Send to projector".
// The cursor lives in the store so Up/Down from the input line move it too.
// The header's Realign board and Full calibrate buttons re-fit the projection
// (a full calibrate confirms first); both are off under the night view, since
// the markers would light the room. The console runs every button itself.
import { useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";
import { focusInput } from "../../input";
import {
  boardRows,
  FIXED_ROWS,
  boardViewWords,
  confirmPrompt,
  isRowShowing,
  NIGHT_REASON,
  NIGHT_VIEW,
  usePendingActions,
  useStore,
} from "../../state";
import type { BoardRowInfo } from "../../state";
import { formatRelative, useTicker } from "../../time";
import { Button } from "../../ui";
import { BoardPreview } from "./BoardPreview";
import { BoardRow } from "./BoardRow";
import styles from "./boards.module.css";

const RELATIVE_TICK_MS = 60_000;
const HINT =
  "Click a board to preview it, then send it to the projector. The console loads it at once; the result shows in Chat.";
// The console lists saves by asking the whiteboard daemon; a board request starts it.
const OFF_NOTE =
  "The whiteboard is off, so its saved boards are not listed. Sending the to-do list or the idle board turns it on.";

/** The boards view. */
export function BoardsView() {
  const { state, dispatch, sender } = useStore();
  const { server, boardCursor } = state;
  const view = server?.board.view ?? null;
  const whiteboardOff = server !== null && !server.board.online;
  const now = useTicker(RELATIVE_TICK_MS);
  const rows = boardRows(server);
  // The reducer clamps the cursor on every snapshot, so this index always exists.
  const selected = rows[Math.min(boardCursor, rows.length - 1)];
  const listRef = useRef<HTMLDivElement>(null);
  const pending = usePendingActions();
  const nightReason = view === NIGHT_VIEW ? NIGHT_REASON : undefined;
  const confirmCalibrate = () =>
    dispatch({
      type: "inputMode",
      mode: {
        kind: "confirm",
        prompt: confirmPrompt("board.calibrate"),
        action: "board.calibrate",
      },
    });

  // Roving focus: when the cursor moves while a row has focus, focus follows it.
  useEffect(() => {
    const list = listRef.current;
    if (!list || !list.contains(document.activeElement)) return;
    list.querySelector<HTMLElement>('[aria-selected="true"]')?.focus();
  }, [boardCursor]);

  const onListKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") dispatch({ type: "boardCursorMove", delta: 1 });
    else if (event.key === "ArrowUp") dispatch({ type: "boardCursorMove", delta: -1 });
    else return;
    event.preventDefault();
  };

  const send = (row: BoardRowInfo) => {
    void sender.runAction(row.action, row.args);
    focusInput();
  };

  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Boards</span>
        <span>
          On the projector now: <span className={styles.value}>{boardViewWords(view)}</span>
        </span>
        <span className={styles.headerActions}>
          <Button
            onClick={() => void sender.runAction("board.realign")}
            pending={pending.has("board.realign")}
            disabledReason={nightReason}
          >
            Realign board
          </Button>
          <Button
            onClick={confirmCalibrate}
            pending={pending.has("board.calibrate")}
            disabledReason={nightReason}
          >
            Full calibrate
          </Button>
        </span>
      </div>
      <p className={styles.hint}>{HINT}</p>
      {whiteboardOff && <p className={styles.note}>{OFF_NOTE}</p>}
      <div className={styles.columns}>
        <div
          ref={listRef}
          role="listbox"
          aria-label="boards"
          className={styles.list}
          onKeyDown={onListKeyDown}
        >
          {rows.map((row, index) => (
            <BoardRow
              key={`${row.action}:${row.name}`}
              name={row.name}
              meta={row.updatedAt === null ? "" : `saved ${formatRelative(row.updatedAt, now)}`}
              selected={index === boardCursor}
              showing={isRowShowing(row, view)}
              onSelect={() => dispatch({ type: "boardCursor", index })}
            />
          ))}
          {rows.length === FIXED_ROWS && !whiteboardOff && (
            <div className={styles.empty}>No saved boards yet.</div>
          )}
        </div>
        <BoardPreview
          row={selected}
          showing={isRowShowing(selected, view)}
          now={now}
          onSend={() => send(selected)}
          onUpdate={() => {
            if (selected.updateArgs) void sender.runAction("board.update", selected.updateArgs);
            focusInput();
          }}
        />
      </div>
    </div>
  );
}
