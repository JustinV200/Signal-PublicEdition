// The Done group is collapsed by default, shows no button at the boundary,
// and opens to every name when the session remembers the choice.
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { TaskInfo } from "../../../src/api";
import { DoneGroup } from "../../../src/views/tasks";

const tasks = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ name: `task${i}`, pct: 100 }) as TaskInfo);
const storage = (get: () => string | null) => vi.stubGlobal("sessionStorage", { getItem: get });

afterEach(() => vi.unstubAllGlobals());

describe("DoneGroup", () => {
  it.each([
    [6, null, false],
    [7, null, true],
    [7, "boom", true],
  ])("%i done, stored %s", (n, stored, button) => {
    storage(() => {
      if (stored === "boom") throw new Error("blocked");
      return stored;
    });
    const html = renderToStaticMarkup(<DoneGroup tasks={tasks(n)} />);
    expect(html.includes(`Show all ${n} done`)).toBe(button);
    expect(html.includes("task6")).toBe(false);
  });

  it("opens to every name when remembered", () => {
    storage(() => "1");
    const html = renderToStaticMarkup(<DoneGroup tasks={tasks(8)} />);
    expect(html).toContain("task7");
    expect(html).toContain("Show fewer");
    expect(html).toContain('aria-expanded="true"');
  });
});
