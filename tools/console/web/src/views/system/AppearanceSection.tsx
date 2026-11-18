// System's APPEARANCE group: Dark and Light buttons (the same switch as the
// `Dark theme` / `Light theme` commands). The theme in use reads in words and
// its button is off, so the state is never colour alone.
import { useReducer } from "react";
import { currentTheme, setTheme } from "../../state";
import type { Theme } from "../../state";
import { Button } from "../../ui";
import { Section } from "./Section";
import styles from "./system.module.css";

const THEMES: readonly { theme: Theme; label: string }[] = [
  { theme: "dark", label: "Dark" },
  { theme: "light", label: "Light" },
];

/** The appearance group. */
export function AppearanceSection() {
  // The theme lives on <html>, not in the store (Commands can change it too),
  // so this reads it each render and a click just asks for a fresh render.
  const [, rerender] = useReducer((count: number) => count + 1, 0);
  const theme = currentTheme();
  const pick = (next: Theme) => {
    setTheme(next);
    rerender();
  };
  return (
    <Section title="Appearance" meta={<span className={styles.meta}>now: {theme}</span>}>
      <div className={styles.buttons}>
        {THEMES.map((option) => (
          <Button
            key={option.theme}
            onClick={() => pick(option.theme)}
            quietReason={option.theme === theme ? "in use now" : undefined}
          >
            {option.label}
          </Button>
        ))}
      </div>
    </Section>
  );
}
