// Writing samples from your sent mail (`setup samples mail`, which needs the
// mail tool signed in): lists recent sent mails with only your own text,
// all ticked; untick any you don't want, then keep the rest
// (`setup samples keep <n>...`).
import { useState } from "react";
import { firstJson, jsonDocs, parseMailSamples, parseSampleCount } from "../../../api";
import type { MailSample } from "../../../api";
import { Button } from "../../../ui";
import { OutputLog, useSetupRun } from "../run";
import styles from "../setup.module.css";

// How much of each mail the list shows.
const PREVIEW_CHARS = 120;

interface MailPickerProps {
  /** Called with the new count in words after a keep. */
  onKept: (countWords: string) => void;
}

/** The "From my sent mail" button and its pick list. */
export function MailPicker({ onKept }: MailPickerProps) {
  const runner = useSetupRun();
  const [mails, setMails] = useState<MailSample[] | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());

  const load = async () => {
    const result = await runner.run({ command: "samples", action: "mail" }, "load");
    if (result?.exit !== 0) return;
    const found = parseMailSamples(firstJson(result.lines));
    setMails(found);
    setPicked(new Set(found.map((mail) => mail.number)));
  };
  const keep = async () => {
    const numbers = [...picked].sort((a, b) => a - b);
    const result = await runner.run({ command: "samples", action: "keep", numbers }, "keep");
    const last = result ? jsonDocs(result.lines).at(-1) : undefined;
    if (result?.exit !== 0 || last === undefined) return;
    const { samples, target } = parseSampleCount(last);
    onKept(`${samples} saved (aim for ${target})`);
    setMails(null);
  };
  const toggle = (number: number) =>
    setPicked((old) => {
      const next = new Set(old);
      if (!next.delete(number)) next.add(number);
      return next;
    });

  return (
    <div className={styles.form}>
      <div className={styles.controls}>
        <Button onClick={() => void load()} {...runner.button("load")}>
          From my sent mail
        </Button>
        <span className={styles.note}>needs the mail tool signed in</span>
      </div>
      {mails && (
        <>
          <ul className={styles.list}>
            {mails.map((mail) => (
              <li key={mail.number} className={styles.row}>
                <label className={styles.check}>
                  <input
                    type="checkbox"
                    checked={picked.has(mail.number)}
                    onChange={() => toggle(mail.number)}
                  />
                  {mail.number}. {mail.subject} · {mail.text.slice(0, PREVIEW_CHARS)}
                </label>
              </li>
            ))}
          </ul>
          <div className={styles.controls}>
            <Button
              onClick={() => void keep()}
              {...runner.button("keep")}
              disabledReason={picked.size ? undefined : "tick at least one"}
            >
              Keep {picked.size} ticked
            </Button>
          </div>
        </>
      )}
      <OutputLog run={runner} what="copytone: samples from sent mail" />
    </div>
  );
}
