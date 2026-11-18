// The status line's tab row: Scope, Chat (`2 new` while it has unseen
// rows), Voice, Boards, Tasks and System, plus Setup while the shell says it
// shows; the console tour's stop reads `◂ tour` while its bar shows. A
// tablist with a roving tabindex: Tab reaches the row as one stop
// (the active tab), Left/Right move focus along it (wrapping), Home/End jump
// to the ends, and Enter or Space opens the focused tab. Arrows only move
// focus, so passing over System doesn't start its polls and the input line
// doesn't take focus back mid-row.
import { useRef } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { boardTabWords, chatNewCount, useStore } from "../../state";
import type { AppState, View } from "../../state";
import { PhaseDot, toDotPhase } from "../PhaseDot";
import styles from "../status.module.css";
import { needsYouWords, newWords } from "../titleWords";
import { Tab } from "./Tab";

interface TabSpec {
  view: View;
  name: string;
  /** The tooltip's shortcut text. */
  shortcut: string;
  /** Changes when the status words change; the view id for a tab with none. */
  textKey: string;
  words?: ReactNode;
}

/** The Tasks tab's words: `1 needs you` first, else `3 active`, else `none active`. */
function taskTabWords({ tasks }: AppState): string {
  const needsYou = needsYouWords(tasks?.needsYou ?? 0);
  if (needsYou) return needsYou;
  if (!tasks || tasks.active.length === 0) return "none active";
  return `${tasks.active.length} active`;
}

/** The tabs in order, with their live words. */
function tabSpecs(state: AppState, showSetupTab: boolean): TabSpec[] {
  const phase = toDotPhase(state.server?.voice);
  const boardWords = boardTabWords(state.server?.board);
  const tasksWords = taskTabWords(state);
  // `2 new` while Chat has rows the owner hasn't seen; no words otherwise.
  const chatWords = newWords(chatNewCount(state)) ?? undefined;
  const voiceWords = (
    <>
      <PhaseDot phase={phase} />
      {phase}
    </>
  );
  const tabs: TabSpec[] = [
    { view: "scope", name: "Scope", shortcut: "Ctrl+1", textKey: "scope" },
    {
      view: "chat",
      name: "Chat",
      shortcut: "Ctrl+2",
      textKey: chatWords ?? "chat",
      words: chatWords,
    },
    { view: "voice", name: "Voice", shortcut: "Ctrl+3", textKey: phase, words: voiceWords },
    { view: "boards", name: "Boards", shortcut: "Ctrl+4", textKey: boardWords, words: boardWords },
    { view: "tasks", name: "Tasks", shortcut: "Ctrl+5", textKey: tasksWords, words: tasksWords },
    { view: "system", name: "System", shortcut: "Ctrl+6 (or Ctrl+7, Ctrl+8)", textKey: "system" },
  ];
  if (showSetupTab)
    tabs.push({ view: "setup", name: "Setup", shortcut: "Ctrl+9", textKey: "setup" });
  return tabs;
}

/** Where an arrow, Home or End key moves focus from tab `at` of `count`; null for other keys. */
function nextTabIndex(key: string, at: number, count: number): number | null {
  if (key === "ArrowRight") return (at + 1) % count;
  if (key === "ArrowLeft") return (at - 1 + count) % count;
  if (key === "Home") return 0;
  if (key === "End") return count - 1;
  return null;
}

/** The tab row; a click (or Enter / Space on a focused tab) switches the view. */
export function TabRow({ showSetupTab }: { showSetupTab: boolean }) {
  const { state, dispatch } = useStore();
  const rowRef = useRef<HTMLDivElement>(null);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const tabs = [...(rowRef.current?.querySelectorAll<HTMLElement>('[role="tab"]') ?? [])];
    const at = tabs.indexOf(event.target as HTMLElement);
    const next = at < 0 ? null : nextTabIndex(event.key, at, tabs.length);
    if (next === null) return;
    event.preventDefault();
    tabs[next].focus();
  };

  return (
    <div
      ref={rowRef}
      className={styles.tabs}
      role="tablist"
      aria-label="views"
      onKeyDown={onKeyDown}
    >
      {tabSpecs(state, showSetupTab).map((tab) => (
        <Tab
          key={tab.view}
          name={tab.name}
          shortcut={tab.shortcut}
          active={state.view === tab.view}
          onClick={() => dispatch({ type: "view", view: tab.view })}
          textKey={tab.textKey}
          isTourStop={!state.helpOpen && state.tourStop === tab.view}
        >
          {tab.words}
        </Tab>
      ))}
    </div>
  );
}
