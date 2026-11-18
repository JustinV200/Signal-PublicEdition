// Sent-message history for Up/Down recall, kept in localStorage so it
// survives closing the window (`console open` starts a new one). Storage can
// be unavailable or throw (private windows, blocked site data), so every
// access is guarded.

const STORAGE_KEY = "signal-console-history";
const MAX_ENTRIES = 50;

/** The last sent messages, oldest first. Empty if storage is unavailable. */
export function readHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((e): e is string => typeof e === "string") : [];
  } catch {
    return [];
  }
}

/** Appends `text` (dropping an identical previous entry) and trims to 50. */
export function pushHistory(text: string): string[] {
  const next = [...readHistory().filter((entry) => entry !== text), text].slice(-MAX_ENTRIES);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Storage blocked: recall still works for this page load via the returned list.
  }
  return next;
}
