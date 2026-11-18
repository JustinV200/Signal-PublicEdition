// Where a batch install (`setup auto`) stopped, under its log: one line per
// tool that ended early, naming the step, as a mark and words ("! needs you"
// or "✗ failed", never colour alone). Read from the JSON the command ends
// with. With `onGo`, each line has a button that opens that tool's screen.
import { jsonDocs, parseAutoStops } from "../../../api";
import type { SetupTool } from "../../../api";
import { Button, Mark } from "../../../ui";
import styles from "../setup.module.css";
import type { SetupRun } from "./useSetupRun";

interface AutoStopsProps {
  run: SetupRun;
  tools: readonly SetupTool[];
  /** Opens a tool's screen; without it there's no button (already on that screen). */
  onGo?: (toolId: string) => void;
}

/** The stops of the runner's last `setup auto`; nothing while it runs or when none stopped. */
export function AutoStops({ run, tools, onGo }: AutoStopsProps) {
  if (run.running || run.exit === null) return null;
  const stops = parseAutoStops(jsonDocs(run.lines).at(-1));
  if (stops.length === 0) return null;
  const nameOf = (id: string) => tools.find((tool) => tool.id === id)?.name ?? id;
  return (
    <ul className={styles.list} aria-label="where the install stopped">
      {stops.map((stop) => (
        <li key={stop.tool} className={`${styles.row} ${styles.controls}`}>
          <span>
            {stop.reason === "failed" ? <Mark shape="cross" /> : "!"}{" "}
            {stop.reason === "failed" ? "failed" : "needs you"}: {nameOf(stop.tool)},{" "}
            <span className={styles.stepTitle}>{stop.title}</span>
          </span>
          {onGo && <Button onClick={() => onGo(stop.tool)}>Go to {nameOf(stop.tool)}</Button>}
        </li>
      ))}
    </ul>
  );
}
