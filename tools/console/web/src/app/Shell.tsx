// The signed-in window: status line, the help panel when open and the active
// view in one scrolling <main>, and the input line. A view switch fades the
// incoming view in; the first paint does not animate.
import { useRef, useState } from "react";
import { HelpPanel, TourBar } from "../help";
import { InputLine } from "../input";
import { useGlobalKeys } from "../keys";
import { ModelsView } from "../models";
import { useStore } from "../state";
import { StatusLine } from "../status";
import { BoardsView } from "../views/boards";
import { ChatView } from "../views/chat";
import { DevicesView } from "../views/devices";
import { ScopeView } from "../views/scope";
import { SetupView } from "../views/setup";
import { TasksView } from "../views/tasks";
import { ToolsView } from "../views/tools";
import { VoiceView } from "../views/voice";
import styles from "./app.module.css";

/** Three rows: status / view / input. */
export function Shell() {
  const { state, dispatch } = useStore();
  const scrollRef = useRef<HTMLElement>(null);
  useGlobalKeys({ dispatch, mode: state.inputMode, helpOpen: state.helpOpen, scrollRef });

  const [seenView, setSeenView] = useState(state.view);
  const [hasSwitched, setHasSwitched] = useState(false);
  if (seenView !== state.view) {
    setSeenView(state.view);
    setHasSwitched(true);
  }

  return (
    <>
      <StatusLine />
      <main ref={scrollRef} className={styles.main}>
        <HelpPanel />
        <TourBar />
        <div key={state.view} className={hasSwitched ? "anim-view" : undefined}>
          {state.view === "scope" && <ScopeView />}
          {state.view === "chat" && <ChatView scrollRef={scrollRef} />}
          {state.view === "voice" && <VoiceView scrollRef={scrollRef} />}
          {state.view === "boards" && <BoardsView />}
          {state.view === "tasks" && <TasksView />}
          {state.view === "devices" && <DevicesView />}
          {state.view === "models" && <ModelsView />}
          {state.view === "tools" && <ToolsView />}
          {state.view === "setup" && <SetupView />}
        </div>
      </main>
      <InputLine />
    </>
  );
}
