// Who started Voice, in words. The server's `voice.startedBy` is `console`
// or `external` (an identifier); people read "started outside the console".
// Shared by the Voice view's header and the scope's readout.

/** `started by the console`, `started outside the console`, or "" when unknown. */
export function startedByWords(startedBy: string | null | undefined): string {
  if (startedBy === "console") return "started by the console";
  if (startedBy === "external") return "started outside the console";
  return "";
}
