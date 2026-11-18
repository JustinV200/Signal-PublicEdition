// The wizard's strip under its header: `Welcome › Pick › Tools 3 of 7 ✓ ›
// Connect › Summary`, each section a button to its page, the open one bold
// with ▸ (a shape and weight, not only the accent colour). The ✓ after the
// Tools count is hidden from screen readers, so the button's name says "done".
import { Mark } from "../../../ui";
import type { StripSection } from "./stripSections";
import styles from "./wizardHead.module.css";

interface WizardStripProps {
  sections: StripSection[];
  /** Opens the page at this index. */
  go: (page: number) => void;
}

/** The section's words, e.g. "Tools 3 of 7", and its accessible name. */
function sectionWords({ name, count }: StripSection): { text: string; label: string } {
  if (!count) return { text: name, label: name };
  const counted = `${count.done} of ${count.total}`;
  return { text: `${name} ${counted}`, label: `${name}, ${counted} done` };
}

/** The strip; a click opens the section's page. */
export function WizardStrip({ sections, go }: WizardStripProps) {
  return (
    <nav className={styles.strip} aria-label="setup pages">
      {sections.map((section, index) => {
        const { text, label } = sectionWords(section);
        // Each button keeps the › after it, so a wrapped row never starts or ends on a stray one.
        return (
          <span key={section.name} className={styles.stripStep}>
            <button
              type="button"
              className={`${styles.stripItem} ${section.isCurrent ? styles.stripCurrent : ""}`}
              aria-current={section.isCurrent ? "page" : undefined}
              aria-label={label}
              onClick={() => go(section.target)}
            >
              {section.isCurrent && <Mark shape="triangle" />}
              {section.isCurrent && " "}
              {text}
              {section.count && " "}
              {section.count && <Mark shape="check" />}
            </button>
            {index < sections.length - 1 && (
              <span className={styles.sep} aria-hidden="true">
                ›
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
