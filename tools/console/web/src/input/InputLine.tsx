// The input line at the bottom of every view: a `›` prompt, a growing
// textarea, a Send button and a Commands button. Enter sends, Shift+Enter
// breaks a line, Up/Down recall history (or move the boards cursor), Ctrl+K
// or Commands turns it into command mode (`:` plus the palette) and a palette
// voice command turns it into the y/n confirm line.
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import type { ActionName } from "../api";
import { buildCommands, filterCommands, Palette } from "../palette";
import type { Command } from "../palette";
import { confirmPrompt, isTodoAvailable, NIGHT_VIEW, setTheme, useStore } from "../state";
import { Button } from "../ui";
import { ConfirmLine } from "./ConfirmLine";
import { INPUT_ID } from "./focusInput";
import styles from "./input.module.css";
import { useAutoGrow } from "./useAutoGrow";
import { useHistoryRecall } from "./useHistoryRecall";

const MAX_ROWS = 8;
const PROMPT_GLYPH = "›";
const COMMAND_GLYPH = ":";
const PLACEHOLDER = "Message Claude…";
const COMMAND_PLACEHOLDER = "Type to filter commands";
const EMPTY_DRAFT_REASON = "type a message first";

/** The input line; reads mode, view and boards cursor from the store. */
export function InputLine() {
  const { state, dispatch, sender } = useStore();
  const { inputMode: mode, view, server } = state;
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [paletteIndex, setPaletteIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recall = useHistoryRecall(draft, setDraft);
  const isCommand = mode.kind === "command";
  useAutoGrow(textareaRef, isCommand ? query : draft, MAX_ROWS);

  // Leaving command mode (Enter, Esc or a click) forgets the query.
  const [seenMode, setSeenMode] = useState(mode.kind);
  if (seenMode !== mode.kind) {
    setSeenMode(mode.kind);
    setQuery("");
    setPaletteIndex(0);
  }

  // Focus returns to the input after any action, confirm or view switch.
  useEffect(() => {
    if (mode.kind !== "confirm") textareaRef.current?.focus();
  }, [mode.kind, view]);

  const closeMode = () => dispatch({ type: "inputMode", mode: { kind: "text" } });
  const openCommands = () => dispatch({ type: "inputMode", mode: { kind: "command" } });

  const commands = useMemo(() => {
    const confirmAction = (action: ActionName) =>
      dispatch({
        type: "inputMode",
        mode: { kind: "confirm", prompt: confirmPrompt(action), action },
      });
    return buildCommands({
      saves: server?.board.saves.map((save) => save.name) ?? [],
      todoAvailable: isTodoAvailable(server),
      nightView: server?.board.view === NIGHT_VIEW,
      runAction: (action, args) => void sender.runAction(action, args),
      confirmAction,
      setView: (next) => dispatch({ type: "view", view: next }),
      setTheme,
    });
  }, [server, sender, dispatch]);
  const matches = useMemo(() => filterCommands(commands, query), [commands, query]);
  const selectedIndex = Math.min(paletteIndex, Math.max(0, matches.length - 1));

  const runCommand = (command: Command) => {
    closeMode();
    command.run();
  };

  // The reply lands in chat, so a message sent from another view switches there.
  const sendDraft = (): boolean => {
    const text = draft.trim();
    if (!text) return false;
    void sender.send(text);
    recall.remember(text);
    setDraft("");
    if (view !== "chat") dispatch({ type: "view", view: "chat" });
    return true;
  };

  const onPaletteKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "ArrowDown") setPaletteIndex(Math.min(selectedIndex + 1, matches.length - 1));
    else if (event.key === "ArrowUp") setPaletteIndex(Math.max(selectedIndex - 1, 0));
    else if (event.key === "Enter" && matches[selectedIndex]) runCommand(matches[selectedIndex]);
    else return;
    event.preventDefault();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isCommand) return onPaletteKey(event);
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendDraft();
      return;
    }
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    const up = event.key === "ArrowUp";
    if (view === "boards" && draft === "") {
      dispatch({ type: "boardCursorMove", delta: up ? -1 : 1 });
      event.preventDefault();
      return;
    }
    if (up ? recall.recallOlder() : recall.recallNewer()) event.preventDefault();
  };

  return (
    <footer className={styles.line}>
      {isCommand && <Palette matches={matches} selectedIndex={selectedIndex} onPick={runCommand} />}
      <div className={`col ${styles.row}`}>
        <span className={styles.prompt} aria-hidden="true">
          {isCommand ? COMMAND_GLYPH : PROMPT_GLYPH}
        </span>
        {mode.kind === "confirm" ? (
          <ConfirmLine
            prompt={mode.prompt}
            onYes={() => {
              void sender.runAction(mode.action);
              closeMode();
            }}
            onNo={closeMode}
          />
        ) : (
          <textarea
            id={INPUT_ID}
            ref={textareaRef}
            className={styles.textarea}
            rows={1}
            value={isCommand ? query : draft}
            onChange={(event) =>
              isCommand ? setQuery(event.target.value) : setDraft(event.target.value)
            }
            onKeyDown={onKeyDown}
            placeholder={isCommand ? COMMAND_PLACEHOLDER : PLACEHOLDER}
            aria-label={isCommand ? "command" : "message to Claude"}
            autoComplete="off"
            spellCheck={false}
          />
        )}
        {mode.kind === "text" && (
          <span className={styles.buttons}>
            <Button hint="Ctrl+K" onClick={openCommands}>
              Commands
            </Button>
            <Button
              primary
              hint="Enter"
              onClick={sendDraft}
              disabledReason={draft.trim() ? undefined : EMPTY_DRAFT_REASON}
            >
              Send
            </Button>
          </span>
        )}
      </div>
    </footer>
  );
}
