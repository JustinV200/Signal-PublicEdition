// The boards buffer: a list of boards to pick from and a preview of the
// picked one with the buttons that send it to the projector. A row click
// or Up/Down only moves the `▸`; nothing loads until a preview button runs.
// The selection lives in the store, by key, so Up/Down from the input line
// move it too and a new save arriving above it leaves it on the same board.
// The header's Realign whiteboard and Full calibrate buttons re-fit the projection;
// both are off under the night view, since the markers would light the room
// (the reason is said once, in a note under the header, so the header stays
// one row; the buttons keep it as a tooltip only).
// Every button runs through the confirm gate: a full calibrate, and loading a
// save or showing its live version over a drawing (unless its refresher is
// `todo`), ask first; the console runs the rest at once.
import { useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";
import { EmptyState } from "../../empty";
import { focusInput } from "../../input";
import {
  boardIndexOf,
  boardRowKey,
  boardRows,
  FIXED_ROWS,
  boardViewWords,
  isRowShowing,
  NIGHT_REASON,
  NIGHT_VIEW,
  useConfirmGate,
  usePendingActions,
  useStore,
} from "../../state";
import type { BoardButton } from "../../state";
import { formatRelative, useTicker } from "../../time";
import { Button } from "../../ui";
import { BoardPreview } from "./BoardPreview";
import { BoardRow } from "./BoardRow";
import styles from "./boards.module.css";

const RELATIVE_TICK_MS = 60_000;
// The console lists saves by asking the whiteboard daemon; a board request starts it.
const OFF_NOTE =
  "The whiteboard is off, so its saved boards are not listed. Sending the to-do list or the idle board turns it on.";

/** The boards view. */
export function BoardsView() {
  const { state, dispatch } = useStore();
  const { request } = useConfirmGate();
  const { server, boardKey } = state;
  const view = server?.board.view ?? null;
  const whiteboardOff = server !== null && !server.board.online;
  const now = useTicker(RELATIVE_TICK_MS);
  const rows = boardRows(server);
  // The to-do row when the selected board is gone, so this row always exists.
  const selectedIndex = boardIndexOf(rows, boardKey);
  const selected = rows[selectedIndex];
  const listRef = useRef<HTMLDivElement>(null);
  const pending = usePendingActions();
  const isNight = view === NIGHT_VIEW;
  const nightReason = isNight ? NIGHT_REASON : undefined;

  // Roving focus: when the cursor moves while a row has focus, focus follows it.
  useEffect(() => {
    const list = listRef.current;
    if (!list || !list.contains(document.activeElement)) return;
    list.querySelector<HTMLElement>('[aria-selected="true"]')?.focus();
  }, [selectedIndex]);

  const onListKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "ArrowDown") dispatch({ type: "boardCursorMove", delta: 1 });
    else if (event.key === "ArrowUp") dispatch({ type: "boardCursorMove", delta: -1 });
    else return;
    event.preventDefault();
  };

  const run = (button: BoardButton) => {
    request(button.action, button.args);
    focusInput();
  };

  return (
    <div className="frame view">
      <div className="view-header">
        <span className="hud-label">Boards</span>
        <span>
          On the projector now: <span className={styles.value}>{boardViewWords(view)}</span>
        </span>
        <span className={styles.headerActions}>
          <Button
            onClick={() => request("board.realign")}
            pending={pending.has("board.realign")}
            quietReason={nightReason}
          >
            Realign whiteboard
          </Button>
          <Button
            onClick={() => request("board.calibrate")}
            pending={pending.has("board.calibrate")}
            quietReason={nightReason}
          >
            Full calibrate
          </Button>
        </span>
      </div>
      {whiteboardOff && <p className={styles.note}>{OFF_NOTE}</p>}
      {nightReason && <p className={styles.note}>{nightReason}</p>}
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
              key={boardRowKey(row)}
              name={row.name}
              meta={row.updatedAt === null ? "" : `saved ${formatRelative(row.updatedAt, now)}`}
              selected={index === selectedIndex}
              showing={isRowShowing(row, view)}
              onSelect={() => dispatch({ type: "boardSelect", key: boardRowKey(row) })}
            />
          ))}
          {rows.length === FIXED_ROWS && !whiteboardOff && (
            <div className={styles.empty}>
              <EmptyState label="No saved boards">
                Ask Claude to save a board and it&apos;s listed here.
              </EmptyState>
            </div>
          )}
        </div>
        <BoardPreview
          row={selected}
          showing={isRowShowing(selected, view)}
          now={now}
          night={isNight}
          onRun={run}
        />
      </div>
    </div>
  );
}
