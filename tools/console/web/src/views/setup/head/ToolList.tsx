// The picked tools beside a tool page: one button per tool page, marked by
// its state (✓ done, ✗ failed, ○ not done yet; ▸ and bold for the open one).
// The marks are shapes; the state is also the tooltip and in the button's
// accessible name, so it never rests on the mark or colour alone.
import type { SetupTool } from "../../../api";
import { Mark } from "../../../ui";
import type { MarkShape } from "../../../ui";
import { screenName } from "../wizardScreens";
import type { Screen } from "../wizardScreens";
import styles from "./wizardHead.module.css";

interface ToolListProps {
  screens: readonly Screen[];
  tools: readonly SetupTool[];
  /** The open page's index. */
  at: number;
  go: (page: number) => void;
}

/** A tool's mark by its `setup list` status. */
function statusShape(status: string | undefined): MarkShape {
  if (status === "done") return "check";
  if (status === "failed") return "cross";
  return "ring";
}

/** The list; one button per picked tool. */
export function ToolList({ screens, tools, at, go }: ToolListProps) {
  return (
    <ul className={styles.tools} aria-label="picked tools">
      {screens.map((screen, index) => {
        if (screen.kind !== "tool") return null;
        const status = tools.find((tool) => tool.id === screen.toolId)?.status ?? "not set up";
        const name = screenName(screen, tools);
        const isOpen = index === at;
        return (
          <li key={screen.toolId}>
            <button
              type="button"
              className={`${styles.toolItem} ${isOpen ? styles.stripCurrent : ""}`}
              aria-current={isOpen ? "page" : undefined}
              aria-label={`${name}, ${status}`}
              title={status}
              onClick={() => go(index)}
            >
              <Mark shape={isOpen ? "triangle" : statusShape(status)} /> {name}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
