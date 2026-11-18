// Pick tools: every tool in the registry under its group (Core, Everyday,
// Hardware, Extras), each a checkbox row (PickRow) with its cost tag, plus
// Pick all and None. Before any pick the Task console comes ticked (the window
// itself runs on it). "Save N picks and install" saves the picks with
// `setup choose` (the rest are skipped and get nothing), then runs every
// pick's automatic steps in one log (`setup auto`: required installs that need
// nobody; optional steps wait for their own click) and names where each tool
// stopped, with a button to its screen. The runner is the wizard's, so the
// log stays when the owner looks at another screen mid-install.
import { useState } from "react";
import type { SetupTool } from "../../../api";
import { useStore } from "../../../state";
import { Button } from "../../../ui";
import { AutoStops, OutputLog } from "../run";
import type { SetupRun } from "../run";
import { initialPicks } from "../wizardScreens";
import styles from "../setup.module.css";
import { groupTools, saveLabel } from "./pickGroups";
import { PickRow } from "./PickRow";

interface PickScreenProps {
  tools: SetupTool[];
  /** The batch runner, held by the wizard so its log outlives this screen. */
  runner: SetupRun;
  reload: () => void;
  next: () => void;
}

/** The grouped checklist, Pick all / None, and Save picks and install. */
export function PickScreen({ tools, runner, reload, next }: PickScreenProps) {
  const { dispatch } = useStore();
  const [picked, setPicked] = useState(() => initialPicks(tools));
  const names = Object.fromEntries(tools.map((t) => [t.id, t.name]));
  const runnable = new Set(tools.filter((t) => t.supportedHere).map((t) => t.id));
  const toggle = (id: string) =>
    setPicked((old) => {
      const updated = new Set(old);
      if (!updated.delete(id)) updated.add(id);
      return updated;
    });
  const add = (ids: string[]) => setPicked((old) => new Set([...old, ...ids]));
  const saveAndInstall = async () => {
    const ids = tools.filter((t) => picked.has(t.id)).map((t) => t.id);
    const chosen = await runner.run({ command: "choose", tools: ids });
    reload();
    if (chosen?.exit !== 0) return;
    await runner.run({ command: "auto", tools: [] });
    reload();
  };

  return (
    <section className={styles.screen}>
      <p className={styles.note}>
        Pick the tools you want. Anything left out gets no config, server, permissions or hooks, and
        you can add it later. Saving installs what needs nobody; optional steps wait for you.
      </p>
      <div className={styles.controls}>
        <Button onClick={() => setPicked(new Set(runnable))}>Pick all</Button>
        <Button onClick={() => setPicked(new Set())}>None</Button>
      </div>
      {groupTools(tools).map((group) => (
        <div key={group.name}>
          <h3 className={styles.subhead}>{group.name}</h3>
          <ul className={styles.list}>
            {group.tools.map((tool) => {
              const missingNeeds = tool.needs.filter((n) => !picked.has(n) && runnable.has(n));
              return (
                <PickRow
                  key={tool.id}
                  tool={tool}
                  isPicked={picked.has(tool.id)}
                  names={names}
                  missingNeeds={missingNeeds}
                  onToggle={() => toggle(tool.id)}
                  onAddNeeds={() => add(missingNeeds)}
                />
              );
            })}
          </ul>
        </div>
      ))}
      <div className={styles.controls}>
        <Button primary onClick={() => void saveAndInstall()} {...runner.button()}>
          {saveLabel(picked.size)}
        </Button>
        <Button onClick={next}>Skip: keep my picks</Button>
      </div>
      <OutputLog run={runner} what="Saving the picks and installing them" hasStopsBelow />
      <AutoStops
        run={runner}
        tools={tools}
        onGo={(toolId) => dispatch({ type: "openSetup", tool: toolId })}
      />
    </section>
  );
}
