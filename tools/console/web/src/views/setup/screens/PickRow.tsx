// One tool on Pick tools: its checkbox, name, platform, status and cost tag
// (from the registry, in a bordered tag so it reads as one), its description,
// and what it builds on. A tool setup has no record of that it found already
// set up reads `done · found already set up`, as in System's Tools list.
// When a picked tool builds on one that isn't picked,
// the "! not picked" warning comes with a button that adds it ("Add Gmail too").
// Tools this OS can't run are shown but can't be picked.
import type { SetupTool } from "../../../api";
import { Button } from "../../../ui";
import styles from "../setup.module.css";

// How setup knows a tool it never ran is done; the CLI's own words (detect.FOUND_WORDS).
const FOUND_WORDS = "found already set up";

interface PickRowProps {
  tool: SetupTool;
  isPicked: boolean;
  /** Tool id to name, for what it builds on. */
  names: Record<string, string>;
  /** The tools it builds on that aren't picked. */
  missingNeeds: string[];
  onToggle: () => void;
  /** Adds the missing tools it builds on to the picks. */
  onAddNeeds: () => void;
}

/** The row. */
export function PickRow({
  tool,
  isPicked,
  names,
  missingNeeds,
  onToggle,
  onAddNeeds,
}: PickRowProps) {
  const nameOf = (id: string) => names[id] ?? id;
  return (
    <li className={styles.row}>
      <label className={styles.pick}>
        <input
          type="checkbox"
          checked={isPicked}
          disabled={!tool.supportedHere}
          onChange={onToggle}
        />
        <span>
          <span className={styles.stepTitle}>{tool.name}</span>{" "}
          <span className={styles.note}>
            [{tool.platform}] · {tool.status}
            {tool.detected && ` · ${FOUND_WORDS}`}
            {!tool.supportedHere && " · can't run on this OS"}{" "}
            {tool.cost && <span className={styles.tag}>{tool.cost}</span>}
          </span>
          <span className={styles.desc}>{tool.description}</span>
          {tool.needs.length > 0 && (
            <span className={styles.note}>
              builds on {tool.needs.map(nameOf).join(", ")}
              {isPicked && missingNeeds.length > 0 && " (! not picked)"}
            </span>
          )}
        </span>
      </label>
      {isPicked && missingNeeds.length > 0 && (
        <div className={`${styles.controls} ${styles.pickExtra}`}>
          <Button onClick={onAddNeeds}>Add {missingNeeds.map(nameOf).join(" and ")} too</Button>
        </div>
      )}
    </li>
  );
}
