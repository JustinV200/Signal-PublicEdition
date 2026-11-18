// The setup wizard (the Setup tab, and where `setup` / `/setup` open the
// console): one page at a time (Welcome, Pick tools, each picked tool's page,
// Permissions, Summary and the optional Tour) under a strip of five sections
// (head/: `Welcome › Pick › Tools 3 of 7 ✓ › Connect › Summary`), with the
// picked tools listed beside a tool page. Every action runs the setup CLI
// through the console server, so progress lives in .setup/progress.json; the
// open page is kept in the store (useStartScreen), so leaving Setup and coming
// back lands on it, and a new window resumes at the first unfinished tool. It
// re-reads the tools whenever the window gets focus back, so a step finished
// in a terminal (Open a terminal) shows as soon as the owner returns. Back and
// Next show only on the pages whose primary button doesn't lead on (a tool
// page, the Tour). Its buttons share one running state (run/runningState.tsx):
// one command at a time, and only the clicked button reads "Working…"; while
// one runs, the header says so on every page (the other buttons are off, and a
// disabled button can't take focus to give its reason), in a span that keeps
// its place when empty so the page never shifts. When the tool list can't be
// read, the header says so beside the error, never "loading…". The Pick
// page's batch runner lives here too, so its log and where it stopped survive
// moving between pages mid-install.
import { useEffect } from "react";
import { firstJson, parseTools } from "../../api";
import type { SetupTool } from "../../api";
import { Button, Mark } from "../../ui";
import { headStyles, stripSections, ToolList, WizardStrip } from "./head";
import { RUNNING_NOTE, RunningProvider, useAddToClaude, useRunningState, useSetupRun } from "./run";
import type { AddToClaude, SetupRun } from "./run";
import { usePicksToStore } from "./usePicksToStore";
import { useStartScreen } from "./useStartScreen";
import { screenName } from "./wizardScreens";
import type { Screen } from "./wizardScreens";
import {
  IntroScreen,
  PermissionsScreen,
  PickScreen,
  SummaryScreen,
  ToolScreen,
  TourScreen,
} from "./screens";
import styles from "./setup.module.css";
import { useSetupQuery } from "./useSetupQuery";

// The pages whose primary button doesn't lead on to the next page (a tool
// page, the Tour), so the footer's Back and Next do.
const FOOTER_PAGES: ReadonlySet<Screen["kind"]> = new Set(["tool", "tour"]);

/** The wizard view. */
export function SetupView() {
  return (
    <RunningProvider>
      <Wizard />
    </RunningProvider>
  );
}

/** The header's words: the page count, or why there is none yet. */
function headerNote(pageCount: number | null, at: number, error: string | null): string {
  if (pageCount !== null) return `page ${at + 1} of ${pageCount}`;
  return error ? "couldn't read your setup: see below" : "loading…";
}

/** The wizard itself, inside the shared running state (its Add to Claude Code runner too). */
function Wizard() {
  const list = useSetupQuery("list", { command: "list" }, (l) => parseTools(firstJson(l)));
  const tools = list.data;
  const reloadList = list.reload;
  useEffect(() => {
    window.addEventListener("focus", reloadList);
    return () => window.removeEventListener("focus", reloadList);
  }, [reloadList]);
  usePicksToStore(tools);
  const { screens, index, setIndex, pickError } = useStartScreen(tools, list.reload);
  // One wire runner for every page, so Summary repeats the restart line after an add elsewhere.
  const wiring = useAddToClaude();
  const batch = useSetupRun();
  const { active } = useRunningState();
  const at = Math.min(index ?? 0, Math.max(screens.length - 1, 0));
  const go = (to: number) => setIndex(Math.max(0, Math.min(to, screens.length - 1)));
  const screen = screens[at];

  return (
    <div className="frame view">
      <div className="view-header">
        <span className="hud-label">Setup</span>
        <span className={styles.note}>
          {headerNote(tools ? screens.length : null, at, list.error)}
        </span>
        <span className={headStyles.runningNote} role="status">
          {active && RUNNING_NOTE}
        </span>
      </div>
      {list.error && (
        <p className={styles.problem}>
          <Mark shape="cross" /> {list.error}
        </p>
      )}
      {pickError && (
        <p className={styles.problem}>
          <Mark shape="cross" /> {pickError}
        </p>
      )}
      {tools && screen && (
        <>
          <WizardStrip sections={stripSections(screens, tools, at)} go={go} />
          <div className={headStyles.layout}>
            <div>
              <h2 className={styles.screenTitle}>{screenName(screen, tools)}</h2>
              <ScreenBody
                screen={screen}
                tools={tools}
                wiring={wiring}
                batch={batch}
                reload={list.reload}
                next={() => go(at + 1)}
              />
              {FOOTER_PAGES.has(screen.kind) && (
                <div className={styles.footer}>
                  <Button onClick={() => go(at - 1)}>Back</Button>
                  <Button
                    onClick={() => go(at + 1)}
                    disabledReason={at === screens.length - 1 ? "last page" : undefined}
                  >
                    Next
                  </Button>
                </div>
              )}
            </div>
            {screen.kind === "tool" && <ToolList screens={screens} tools={tools} at={at} go={go} />}
          </div>
        </>
      )}
    </div>
  );
}

interface ScreenBodyProps {
  screen: Screen;
  tools: SetupTool[];
  wiring: AddToClaude;
  /** Pick tools' Save picks and install runner. */
  batch: SetupRun;
  reload: () => void;
  next: () => void;
}

function ScreenBody({ screen, tools, wiring, batch, reload, next }: ScreenBodyProps) {
  switch (screen.kind) {
    case "intro":
      return <IntroScreen next={next} />;
    case "pick":
      return <PickScreen tools={tools} runner={batch} reload={reload} next={next} />;
    case "tool": {
      const tool = tools.find((t) => t.id === screen.toolId);
      if (!tool) return null;
      return <ToolScreen key={tool.id} tool={tool} tools={tools} wiring={wiring} reload={reload} />;
    }
    case "permissions":
      return <PermissionsScreen tools={tools} wiring={wiring} reload={reload} next={next} />;
    case "summary":
      return <SummaryScreen tools={tools} wiring={wiring} next={next} />;
    case "tour":
      return <TourScreen />;
  }
}
