// The optional tour, in two parts. "Tour the console" walks the console's
// own views (the radar, chat, tasks...) one at a time with the tour bar from
// the help package. Below it, how Signal works: GUIDE.md one section at a time
// (`setup tour --json`, the same text as the terminal tour).
import { useState } from "react";
import { firstJson, parseTour } from "../../../api";
import { Markdown } from "../../../markdown";
import { useStore } from "../../../state";
import { Button } from "../../../ui";
import styles from "../setup.module.css";
import { useSetupQuery } from "../useSetupQuery";

/** The console tour button and the GUIDE.md reader. */
export function TourScreen() {
  const { dispatch } = useStore();
  const tour = useSetupQuery("tour", { command: "tour" }, (l) => parseTour(firstJson(l)));
  const [at, setAt] = useState(0);
  const sections = tour.data ?? [];
  const section = sections[Math.min(at, sections.length - 1)];
  return (
    <section className={styles.screen}>
      <div className={styles.controls}>
        <Button primary onClick={() => dispatch({ type: "tour", step: 0 })}>
          Tour the console
        </Button>
        <span className={styles.note}>shows each view of this window and what it's for</span>
      </div>
      <h3 className={styles.subhead}>How Signal works</h3>
      {tour.error && <p className={styles.note}>✗ {tour.error}</p>}
      {section && (
        <>
          <p className={styles.note}>
            {at + 1} of {sections.length}: <strong>{section.heading}</strong>
          </p>
          <Markdown text={section.body} />
          <div className={styles.controls}>
            <Button
              onClick={() => setAt(at - 1)}
              disabledReason={at === 0 ? "first section" : undefined}
            >
              Back
            </Button>
            <Button
              onClick={() => setAt(at + 1)}
              disabledReason={at >= sections.length - 1 ? "last section" : undefined}
            >
              Next section
            </Button>
          </div>
          <div className={styles.controls}>
            {sections.map((s, index) => (
              <Button key={s.heading} onClick={() => setAt(index)}>
                {index === at ? `▸ ${s.heading}` : s.heading}
              </Button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
