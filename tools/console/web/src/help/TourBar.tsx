// The console tour: a bar above the view that walks through each view in tab
// order, switching to it and saying what it's for (the help panel's words).
// Started from the setup wizard's Tour screen; End tour or Finish closes it.
// The view's own tab is the active one, so where you are shows in
// the tab row too.
import { useEffect } from "react";
import { useStore } from "../state";
import type { View } from "../state";
import { Button } from "../ui";
import styles from "./help.module.css";
import { VIEW_HELP } from "./HelpPanel";

/** The tour's stops: each view with its help text. */
const STOPS = VIEW_HELP.map(([name, text]) => ({ name, text, view: name.toLowerCase() as View }));

/** The bar; renders nothing unless a tour is running. */
export function TourBar() {
  const { state, dispatch } = useStore();
  const step = state.tourStep;
  const stop = step === null ? null : STOPS[Math.min(step, STOPS.length - 1)];

  useEffect(() => {
    if (stop) dispatch({ type: "view", view: stop.view });
  }, [stop, dispatch]);

  if (step === null || !stop) return null;
  const go = (to: number | null) => dispatch({ type: "tour", step: to });
  const isLast = step >= STOPS.length - 1;
  return (
    <section className={`col ${styles.tour} anim-fade`} aria-label="console tour" role="status">
      <div className={styles.head}>
        <span className="hud-label">
          Tour {step + 1}/{STOPS.length} · {stop.name}
        </span>
        <span className={styles.tourButtons}>
          <Button
            onClick={() => go(step - 1)}
            disabledReason={step === 0 ? "first stop" : undefined}
          >
            Back
          </Button>
          <Button primary onClick={() => go(isLast ? null : step + 1)}>
            {isLast ? "Finish" : "Next"}
          </Button>
          <Button onClick={() => go(null)}>End tour</Button>
        </span>
      </div>
      <p className={styles.note}>
        ▸ The {stop.name} tab is the one lit up above: {stop.text}
      </p>
    </section>
  );
}
