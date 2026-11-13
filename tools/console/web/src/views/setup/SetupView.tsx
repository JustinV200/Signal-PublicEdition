// The setup wizard (the Setup tab, and where `setup` / `/setup` open the
// console): intro, pick tools, each picked tool's steps, permissions, a
// summary and the optional tour. Every action runs the setup CLI through the
// console server, so progress lives in .setup/progress.json and the wizard
// resumes at the first unfinished tool when opened again.
import { firstJson, parseTools } from "../../api";
import type { SetupTool } from "../../api";
import { Button } from "../../ui";
import { useStartScreen } from "./useStartScreen";
import { buildScreens, screenName } from "./wizardScreens";
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

const HINT =
  "Each button runs one setup step on this PC. Progress saves as you go: close the window any time and setup picks up where you stopped. Every tool and optional step can be skipped.";

/** The wizard view. */
export function SetupView() {
  const list = useSetupQuery("list", { command: "list" }, (l) => parseTools(firstJson(l)));
  const tools = list.data;
  const { index, setIndex, pickError } = useStartScreen(tools, list.reload);
  const screens = tools ? buildScreens(tools) : [];
  const at = Math.min(index ?? 0, Math.max(screens.length - 1, 0));
  const go = (to: number) => setIndex(Math.max(0, Math.min(to, screens.length - 1)));

  return (
    <div className={`col ${styles.view}`}>
      <div className={styles.header}>
        <span className="hud-label">Setup</span>
        <span className={styles.note}>
          {tools ? `step ${at + 1} of ${screens.length}` : "loading…"}
        </span>
      </div>
      <p className={styles.hint}>{HINT}</p>
      {list.error && <p className={styles.problem}>✗ {list.error}</p>}
      {pickError && <p className={styles.problem}>✗ {pickError}</p>}
      {tools && (
        <>
          <nav className={styles.strip} aria-label="setup steps">
            {screens.map((screen, i) => (
              <button
                key={i}
                type="button"
                className={`${styles.stripItem} ${i === at ? styles.stripCurrent : ""}`}
                aria-current={i === at ? "step" : undefined}
                onClick={() => go(i)}
              >
                {i === at ? "▸ " : ""}
                {i + 1}. {screenName(screen, tools)}
                {doneMark(screen, tools)}
              </button>
            ))}
          </nav>
          <h2 className={styles.screenTitle}>{screenName(screens[at], tools)}</h2>
          <ScreenBody
            screen={screens[at]}
            tools={tools}
            reload={list.reload}
            next={() => go(at + 1)}
          />
          <div className={styles.footer}>
            <Button onClick={() => go(at - 1)} disabledReason={at === 0 ? "first step" : undefined}>
              Back
            </Button>
            <Button
              onClick={() => go(at + 1)}
              disabledReason={at === screens.length - 1 ? "last step" : undefined}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/** ` ✓` after a finished tool in the strip (a mark, not a colour). */
function doneMark(screen: Screen, tools: SetupTool[]): string {
  if (screen.kind !== "tool") return "";
  return tools.find((tool) => tool.id === screen.toolId)?.status === "done" ? " ✓" : "";
}

interface ScreenBodyProps {
  screen: Screen;
  tools: SetupTool[];
  reload: () => void;
  next: () => void;
}

function ScreenBody({ screen, tools, reload, next }: ScreenBodyProps) {
  switch (screen.kind) {
    case "intro":
      return <IntroScreen next={next} />;
    case "pick":
      return <PickScreen tools={tools} reload={reload} next={next} />;
    case "tool": {
      const tool = tools.find((t) => t.id === screen.toolId);
      return tool ? <ToolScreen key={tool.id} tool={tool} tools={tools} reload={reload} /> : null;
    }
    case "permissions":
      return <PermissionsScreen next={next} />;
    case "summary":
      return <SummaryScreen tools={tools} next={next} />;
    case "tour":
      return <TourScreen />;
  }
}
