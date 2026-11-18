// The console tour: a bar above the view (outside its scroller, like Help)
// that walks the tour's stops (state's tourStops: Chat, Tasks, System, Scope,
// then the picked tools' tabs), switching to each and saying what it's for in
// VIEW_HELP's words, the same text Help shows. Started from the setup
// wizard's Tour page or Help's Take the tour, at the last stop it reached
// (kept in localStorage); End tour keeps that stop, Finish forgets it. A tab
// click moves the tour to that tab's stop (the store's `view` action); a tab
// that isn't a stop says so, and Back returns to the last stop. It hides while
// Help is open and comes back when Help closes. Back, Next and End tour keep
// their place at every stop: the label never shares their row's width.
import { useEffect } from "react";
import { saveTourStop, tourStops, useStore } from "../state";
import type { View } from "../state";
import { Button, Mark } from "../ui";
import styles from "./help.module.css";
import { VIEW_HELP } from "./HelpPanel";

/** A tab's name and help text from VIEW_HELP. */
function viewHelp(view: View): { name: string; text: string } {
  const entry = VIEW_HELP.find(([name]) => name.toLowerCase() === view);
  return entry ? { name: entry[0], text: entry[1] } : { name: view, text: "" };
}

/** What the bar says on a tab that isn't a stop; `next` null at the last stop. */
function offTourNote(open: string, back: string, next: string | null): string {
  const onward = next ? `Next goes on to ${next}` : "Finish ends the tour";
  return `${open} isn't a stop on the tour. Back returns to ${back}; ${onward}.`;
}

/** The bar; renders nothing unless a tour is running and Help is closed. */
export function TourBar() {
  const { state, dispatch } = useStore();
  const stop = state.tourStop;

  useEffect(() => {
    if (stop) saveTourStop(stop);
  }, [stop]);

  // Help and the tour show one at a time: while Help is open the tour keeps its stop, hidden.
  if (stop === null || state.helpOpen) return null;
  const stops = tourStops(state.setupPicks);
  // A stop the picks dropped mid-tour counts as the first.
  const at = Math.max(0, stops.indexOf(stop));
  const isOnStop = state.view === stop;
  const isLast = at >= stops.length - 1;
  const go = (to: View | null) => dispatch({ type: "tour", stop: to });
  const finish = () => {
    saveTourStop(null);
    go(null);
  };
  const open = viewHelp(state.view);
  const here = viewHelp(stops[at]);
  return (
    <section className="frame anim-fade" aria-label="console tour" role="status">
      <div className={`panel ${styles.tour}`}>
        <div className={`${styles.head} ${styles.tourHead}`}>
          <span className="hud-label">
            {isOnStop ? `Tour ${at + 1}/${stops.length} · ${here.name}` : `Tour · ${open.name}`}
          </span>
          <span className={styles.tourButtons}>
            {/* A quiet reason: a caption would push Next along at the first stop. */}
            <Button
              onClick={() => go(isOnStop ? stops[at - 1] : stops[at])}
              quietReason={isOnStop && at === 0 ? "first stop" : undefined}
            >
              Back
            </Button>
            <Button primary onClick={() => (isLast ? finish() : go(stops[at + 1]))}>
              {isLast ? "Finish" : "Next"}
            </Button>
            <Button onClick={() => go(null)}>End tour</Button>
          </span>
        </div>
        <p className={`${styles.note} ${styles.tourNote}`}>
          <Mark shape="triangle" />{" "}
          {isOnStop
            ? `The ${here.name} tab, marked tour above: ${here.text}`
            : offTourNote(open.name, here.name, isLast ? null : viewHelp(stops[at + 1]).name)}
        </p>
      </div>
    </section>
  );
}
