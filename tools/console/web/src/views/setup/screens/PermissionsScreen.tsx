// Permissions, the page that connects Claude Code: what setup will add to
// Claude Code for the finished tools, from `setup plan`, before the one
// confirmation. First one plain line per tool (what Claude may do without
// asking), then the exact entries (MCP servers, permission rules, hooks)
// folded under Show exact entries. `Add to Claude Code` runs `setup wire` (it
// never sets a permission mode). It doesn't move on by itself: the restart line
// stays until the owner clicks `Next: check everything`. Below, when the console
// is picked, its claim link, which ticks itself when a session links.
import type { SetupTool } from "../../../api";
import { Button, Mark } from "../../../ui";
import { ADD_TO_CLAUDE, AddResult } from "../run";
import type { AddToClaude } from "../run";
import styles from "../setup.module.css";
import { CLAIM_STEP_ID, ClaimLink } from "../steps";
import { useSetupQuery } from "../useSetupQuery";
import { CONSOLE_ID, isChosen } from "../wizardScreens";
import { splitPlan } from "./consentPlan";

/** A plain line with its tool's name in 600, so the eye finds each tool. */
function ConsentLine({ line }: { line: string }) {
  const cut = line.indexOf(": ");
  if (cut < 0) return <li>{line}</li>;
  return (
    <li>
      <strong>{line.slice(0, cut)}:</strong>
      {line.slice(cut + 1)}
    </li>
  );
}

interface PermissionsScreenProps {
  tools: SetupTool[];
  /** The wizard's wire runner, so Summary knows a wire worked. */
  wiring: AddToClaude;
  reload: () => void;
  next: () => void;
}

/** The plan, Add to Claude Code or Not now, the result, the claim link, then Next. */
export function PermissionsScreen({ tools, wiring, reload, next }: PermissionsScreenProps) {
  const plan = useSetupQuery("plan", { command: "plan" }, splitPlan);
  // A failed fetch or a plan that exited non-zero: never shown as consent.
  const failure = plan.error ?? plan.data?.error ?? null;
  // Only for a picked console: an unpicked one must not get a step marked done.
  const claim = tools
    .find((tool) => tool.id === CONSOLE_ID && isChosen(tool))
    ?.steps.find((step) => step.id === CLAIM_STEP_ID);
  // Consent needs the plan on screen: off while it loads or after it failed.
  const planReason = failure
    ? "the plan didn't load"
    : plan.data
      ? undefined
      : "wait for the plan to load";
  const add = async () => {
    await wiring.add();
    plan.reload();
    reload();
  };
  return (
    <section className={styles.screen}>
      <p className={styles.note}>
        What setup will add to Claude Code for the tools that are done. Your own entries in
        .mcp.json and .claude/settings.local.json are kept.
      </p>
      {failure ? (
        <p className={styles.problem}>
          <Mark shape="cross" /> Couldn't read what setup will add: {failure}
        </p>
      ) : plan.data ? (
        <ul className={styles.consent}>
          {plan.data.plain.map((line) => (
            <ConsentLine key={line} line={line} />
          ))}
        </ul>
      ) : (
        <p className={styles.note}>… reading what setup will add</p>
      )}
      {!failure && plan.data?.exact && (
        <details className={styles.disclosure}>
          <summary className={styles.note}>Show exact entries</summary>
          <pre className={`panel ${styles.log}`}>{plan.data.exact}</pre>
        </details>
      )}
      {!wiring.added && (
        <div className={styles.controls}>
          <Button
            primary
            onClick={() => void add()}
            disabledReason={planReason}
            {...wiring.runner.button()}
          >
            {ADD_TO_CLAUDE}
          </Button>
          <Button onClick={next}>Not now</Button>
        </div>
      )}
      <AddResult wiring={wiring} />
      {claim && (
        <>
          <h3 className={styles.subhead}>Link Claude Code to this console</h3>
          <ClaimLink isClaimDone={claim.status === "done"} onMarked={reload} />
        </>
      )}
      {wiring.added && (
        <div className={styles.controls}>
          <Button primary onClick={next}>
            Next: check everything
          </Button>
        </div>
      )}
    </section>
  );
}
