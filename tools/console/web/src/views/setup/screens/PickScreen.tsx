// Pick tools: every tool in the registry with its description, platform label
// and what it builds on. Each one is a checkbox, so any can be left out; the
// picks are saved with `setup choose` (the rest are skipped and get nothing).
// Tools this OS can't run are shown but can't be picked.
import { useState } from "react";
import type { SetupTool } from "../../../api";
import { Button } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import { isChosen } from "../wizardScreens";
import styles from "../setup.module.css";

interface PickScreenProps {
  tools: SetupTool[];
  reload: () => void;
  next: () => void;
}

/** The checklist and Save picks. */
export function PickScreen({ tools, reload, next }: PickScreenProps) {
  const runner = useSetupRun();
  const [picked, setPicked] = useState(() => new Set(tools.filter(isChosen).map((t) => t.id)));
  const names = Object.fromEntries(tools.map((t) => [t.id, t.name]));
  const toggle = (id: string) =>
    setPicked((old) => {
      const updated = new Set(old);
      if (!updated.delete(id)) updated.add(id);
      return updated;
    });
  const save = async () => {
    const ids = tools.filter((t) => picked.has(t.id)).map((t) => t.id);
    const result = await runner.run({ command: "choose", tools: ids });
    reload();
    if (result?.exit === 0) next();
  };

  return (
    <section className={styles.screen}>
      <p className={styles.note}>
        Pick the tools you want. Anything left out gets no config, server, permissions or hooks, and
        you can add it later.
      </p>
      <ul className={styles.list}>
        {tools.map((tool) => {
          const missingNeeds = tool.needs.filter((need) => !picked.has(need));
          return (
            <li key={tool.id} className={styles.row}>
              <label className={styles.pick}>
                <input
                  type="checkbox"
                  checked={picked.has(tool.id)}
                  disabled={!tool.supportedHere}
                  onChange={() => toggle(tool.id)}
                />
                <span>
                  <span className={styles.stepTitle}>{tool.name}</span>{" "}
                  <span className={styles.note}>
                    [{tool.platform}] · {tool.status}
                    {!tool.supportedHere && " · can't run on this OS"}
                  </span>
                  <span className={styles.desc}>{tool.description}</span>
                  {tool.needs.length > 0 && (
                    <span className={styles.note}>
                      builds on {tool.needs.map((need) => names[need] ?? need).join(", ")}
                      {picked.has(tool.id) && missingNeeds.length > 0 && " (! not picked)"}
                    </span>
                  )}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
      <div className={styles.controls}>
        <Button primary onClick={() => void save()} pending={runner.running}>
          Save {picked.size} picks
        </Button>
        <Button onClick={next}>Skip: keep my picks</Button>
      </div>
      <OutputLog run={runner} what="Saving the tool picks" />
    </section>
  );
}
