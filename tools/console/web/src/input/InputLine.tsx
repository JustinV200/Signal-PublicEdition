// The input line at the bottom of every view: a `›` prompt, a growing
// textarea, a Commands button and a Send button (off while no Claude session
// is linked, the draft is empty or Commands is open, the reason a tooltip
// only, so typing never shifts the buttons). Enter sends, Shift+Enter
// breaks a line, Up/Down recall history (or move the boards cursor), Ctrl+K
// or Commands turns it into command mode (`:` plus the palette, the textarea
// its combobox; Commands, still in place, closes it again), and an
// action that asks first (the confirm gate) turns it into the Yes / No line.
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { filterCommands, Palette, PALETTE_LIST_ID, paletteOptionId, useCommands } from "../palette";
import type { Command } from "../palette";
import { sendBlockedReason, useConfirmGate, useStore } from "../state";
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
const COMMAND_MODE_REASON = "Commands is open: Enter runs the picked command";

/** The input line; reads mode, view and boards cursor from the store. */
export function InputLine() {
  const { state, dispatch, sender } = useStore();
  const { answer } = useConfirmGate();
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
  // Leaving a confirm, the textarea is new and its caret would sit before the
  // draft, so a typed letter would land first: the caret goes to the end then
  // (only then, so a view switch keeps a caret left mid-draft).
  const wasConfirm = useRef(false);
  useEffect(() => {
    const textarea = textareaRef.current;
    const isLeavingConfirm = wasConfirm.current;
    wasConfirm.current = mode.kind === "confirm";
    if (mode.kind === "confirm" || !textarea) return;
    textarea.focus();
    if (isLeavingConfirm) textarea.setSelectionRange(textarea.value.length, textarea.value.length);
  }, [mode.kind, view]);

  const closeMode = () => dispatch({ type: "inputMode", mode: { kind: "text" } });
  const openCommands = () => dispatch({ type: "inputMode", mode: { kind: "command" } });

  // Palette actions go through the same gate as the buttons, so both ask the same things.
  const commands = useCommands(isCommand);
  const matches = useMemo(() => filterCommands(commands, query), [commands, query]);
  // No Claude session to send to (never claimed, or it closed): Send and Enter are off.
  const blockedReason = sendBlockedReason(server);
  const selectedIndex = Math.min(paletteIndex, Math.max(0, matches.length - 1));

  // A new query starts at its best (first) match, not wherever Down had got to.
  const changeQuery = (next: string) => {
    setQuery(next);
    setPaletteIndex(0);
  };

  // Why Send is off, as its tooltip: no session, Commands open, or nothing typed yet.
  const sendOffReason = (): string | undefined => {
    if (blockedReason) return blockedReason;
    if (isCommand) return COMMAND_MODE_REASON;
    return draft.trim() ? undefined : EMPTY_DRAFT_REASON;
  };

  const runCommand = (command: Command) => {
    closeMode();
    command.run();
  };

  // The reply lands in chat, so a message sent from another view switches there.
  const sendDraft = (): boolean => {
    const text = draft.trim();
    if (!text || blockedReason) return false;
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
      <div className={`frame ${styles.row}`}>
        <span className={styles.prompt} aria-hidden="true">
          {isCommand ? COMMAND_GLYPH : PROMPT_GLYPH}
        </span>
        {mode.kind === "confirm" ? (
          <ConfirmLine prompt={mode.prompt} onYes={() => answer(true)} onNo={() => answer(false)} />
        ) : (
          <textarea
            id={INPUT_ID}
            ref={textareaRef}
            className={styles.textarea}
            rows={1}
            value={isCommand ? query : draft}
            onChange={(event) =>
              isCommand ? changeQuery(event.target.value) : setDraft(event.target.value)
            }
            onKeyDown={onKeyDown}
            placeholder={isCommand ? COMMAND_PLACEHOLDER : PLACEHOLDER}
            aria-label={isCommand ? "command" : "message to Claude"}
            role={isCommand ? "combobox" : undefined}
            aria-expanded={isCommand ? true : undefined}
            aria-controls={isCommand ? PALETTE_LIST_ID : undefined}
            aria-autocomplete={isCommand ? "list" : undefined}
            aria-activedescendant={
              isCommand && matches.length ? paletteOptionId(selectedIndex) : undefined
            }
            autoComplete="off"
            spellCheck={false}
          />
        )}
        {/* Both buttons stay in command mode, so opening Commands moves nothing. */}
        {mode.kind !== "confirm" && (
          <span className={styles.buttons}>
            <Button
              hint="Ctrl+K"
              onClick={isCommand ? closeMode : openCommands}
              expanded={isCommand}
            >
              Commands
            </Button>
            {/* An empty draft only waits for typing, so its border stays solid. */}
            <Button
              primary
              hint="Enter"
              onClick={sendDraft}
              quietReason={sendOffReason()}
              awaitsInput={!blockedReason && !isCommand}
            >
              Send
            </Button>
          </span>
        )}
      </div>
    </footer>
  );
}
