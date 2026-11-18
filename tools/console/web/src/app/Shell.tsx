// The signed-in window: status line, the band holding Help and the tour bar
// when they show (outside the scroller, so they show at once however far the
// view is scrolled), the server-down notice and the active view in one
// scrolling <main>, the result strip (every view but Chat) and the input
// line. It works out whether the Setup tab shows (views/setup's useSetupTab)
// for the status line, and keeps the console's health checks read (useConsoleHealth) for
// the status line and System. A view switch fades the incoming view in (the
// first paint does not animate) and opens it at its top, except Chat and
// Voice, which follow their own end. The window title carries the counts
// (`(2 new, 1 needs you) Signal console`), so they show from another
// browser tab.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { HelpPanel, TourBar } from "../help";
import { InputLine } from "../input";
import { useGlobalKeys } from "../keys";
import { chatNewCount, useConfirmGate, useStore } from "../state";
import type { View } from "../state";
import { APP_NAME, StatusLine, windowTitle } from "../status";
import { BoardsView } from "../views/boards";
import { ChatView } from "../views/chat";
import { ScopeView } from "../views/scope";
import { SetupView, useSetupTab } from "../views/setup";
import { SystemView } from "../views/system";
import { TasksView } from "../views/tasks";
import { VoiceView } from "../views/voice";
import styles from "./app.module.css";
import { OfflineNotice } from "./OfflineNotice";
import { ResultStrip } from "./ResultStrip";
import { useConsoleHealth } from "./useConsoleHealth";

// The logs pin themselves to their end (scroll's useFollow); every other view opens at its top.
const FOLLOWING_VIEWS: ReadonlySet<View> = new Set(["chat", "voice"]);

/** Keeps `document.title` on the counts; back to the plain name when the shell goes (signed out). */
function useWindowTitle(chatNew: number, needsYou: number): void {
  useEffect(() => {
    document.title = windowTitle(chatNew, needsYou);
    return () => {
      document.title = APP_NAME;
    };
  }, [chatNew, needsYou]);
}

/** Status / Help and tour / view / result strip (not on Chat) / input. */
export function Shell() {
  const { state, dispatch } = useStore();
  const scrollRef = useRef<HTMLElement>(null);
  const { answer } = useConfirmGate();
  useGlobalKeys({
    dispatch,
    mode: state.inputMode,
    helpOpen: state.helpOpen,
    scrollRef,
    answerConfirm: answer,
  });
  const showSetupTab = useSetupTab(state.view === "setup");
  useConsoleHealth(state.view === "system");
  useWindowTitle(chatNewCount(state), state.tasks?.needsYou ?? 0);

  // The views share one scroller, which would otherwise keep the last view's offset (a long Chat's end).
  useLayoutEffect(() => {
    if (!FOLLOWING_VIEWS.has(state.view) && scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [state.view]);

  const [seenView, setSeenView] = useState(state.view);
  const [hasSwitched, setHasSwitched] = useState(false);
  // Held here, not in the strip, so a dismissed failure stays dismissed across a visit to Chat.
  const [dismissedId, setDismissedId] = useState<string | null>(null);
  if (seenView !== state.view) {
    setSeenView(state.view);
    setHasSwitched(true);
  }

  return (
    <>
      <StatusLine showSetupTab={showSetupTab} />
      {/* Always rendered, empty when both are closed, so the grid keeps its rows. */}
      <div className={styles.band}>
        <HelpPanel />
        <TourBar />
      </div>
      <main ref={scrollRef} className={styles.main}>
        <OfflineNotice />
        <div key={state.view} className={hasSwitched ? "anim-view" : undefined}>
          {state.view === "scope" && <ScopeView />}
          {state.view === "chat" && <ChatView scrollRef={scrollRef} />}
          {state.view === "voice" && <VoiceView scrollRef={scrollRef} />}
          {state.view === "boards" && <BoardsView />}
          {state.view === "tasks" && <TasksView />}
          {state.view === "system" && <SystemView />}
          {state.view === "setup" && <SetupView />}
        </div>
      </main>
      {state.view !== "chat" && (
        <ResultStrip dismissedId={dismissedId} onDismiss={setDismissedId} />
      )}
      <InputLine />
    </>
  );
}
