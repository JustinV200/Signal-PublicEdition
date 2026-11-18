// Theme switch. Dark is the default whatever the OS says; `Light theme` in
// Commands, or System's Light button, sets data-theme on <html> and
// remembers it in localStorage.

export type Theme = "dark" | "light";

const STORAGE_KEY = "signal-console-theme";

/** The remembered theme, or dark. */
export function loadTheme(): Theme {
  try {
    return localStorage.getItem(STORAGE_KEY) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** The theme on the page now (what `setTheme` last applied). */
export function currentTheme(): Theme {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

/** Applies `theme` to the document and remembers it. */
export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage blocked: the theme still applies for this page load.
  }
}
