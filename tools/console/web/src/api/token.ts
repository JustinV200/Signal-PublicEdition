// The per-login token from POST /api/login. Kept in memory and in
// sessionStorage (per origin including the port, survives a reload in the
// same tab). Cookies were ruled out: every 127.0.0.1 port would share them.

const STORAGE_KEY = "signal-console-token";
export const TOKEN_HEADER = "X-Console-Token";

let memory: string | null = null;

/** The current token, or null when not logged in. */
export function getToken(): string | null {
  if (memory) return memory;
  try {
    memory = sessionStorage.getItem(STORAGE_KEY);
  } catch {
    // Storage blocked: the in-memory copy still works for this page load.
  }
  return memory;
}

/** Stores a new token, or clears it with null (on 401). */
export function setToken(token: string | null): void {
  memory = token;
  try {
    if (token) sessionStorage.setItem(STORAGE_KEY, token);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage blocked: see getToken.
  }
}

/** Request headers carrying the token, if there is one. */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { [TOKEN_HEADER]: token } : {};
}
