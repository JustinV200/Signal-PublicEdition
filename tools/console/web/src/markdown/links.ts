// URL policy for Claude's markdown: only absolute http(s) URLs become links
// or image references; anything else (javascript:, data:, relative paths,
// mailto:) is dropped so the text renders plain.

const ALLOWED_PROTOCOLS = new Set(["http:", "https:"]);

/** The URL itself when it is absolute http(s), otherwise undefined. */
export function httpOnlyUrl(url: string): string | undefined {
  try {
    return ALLOWED_PROTOCOLS.has(new URL(url.trim()).protocol) ? url.trim() : undefined;
  } catch {
    // Relative or malformed: not a link we want to emit.
    return undefined;
  }
}
