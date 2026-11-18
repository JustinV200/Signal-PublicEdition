// The first screen: the intro paragraph (tools/setup data/intro.txt via
// `setup intro`, the same text the terminal setup and the README open with)
// and the programs still missing (`setup prereqs`), with where to get them
// (a URL there is a link).
import { parsePrereqs, firstJson } from "../../../api";
import { LinkedText } from "../../../markdown";
import { Button, Mark } from "../../../ui";
import styles from "../setup.module.css";
import { useSetupQuery } from "../useSetupQuery";

/** Welcome: the intro, what's missing, and Start. */
export function IntroScreen({ next }: { next: () => void }) {
  const intro = useSetupQuery("intro", { command: "intro" }, (lines) => lines.join("\n").trim());
  const missing = useSetupQuery("prereqs", { command: "prereqs", tools: [] }, (lines) =>
    parsePrereqs(firstJson(lines)),
  );
  return (
    <section className={styles.screen}>
      <p className={styles.prose}>{intro.data ?? intro.error ?? "…"}</p>
      <h3 className={styles.subhead}>Programs</h3>
      {missing.error && (
        <p className={styles.note}>
          <Mark shape="cross" /> {missing.error}
        </p>
      )}
      {missing.data?.length === 0 && (
        <p className={styles.note}>
          <Mark shape="check" /> Everything the tools need is installed.
        </p>
      )}
      {missing.data && missing.data.length > 0 && (
        <ul className={styles.summary}>
          {missing.data.map((prereq) => (
            <li key={prereq.name}>
              ! missing: {prereq.name} · get it from <LinkedText text={prereq.getIt} />
            </li>
          ))}
          <li className={styles.note}>Only the tools that use a missing program need it.</li>
        </ul>
      )}
      <div className={styles.controls}>
        <Button primary onClick={next}>
          Start
        </Button>
      </div>
    </section>
  );
}
