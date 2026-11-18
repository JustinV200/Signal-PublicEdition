// URL policy for Claude's markdown (and the bare URLs LinkedText finds in
// plain text): only absolute http(s) URLs become links or image references;
// anything else (javascript:, data:, relative paths, mailto:) is dropped so
// the text renders plain.

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

// A bare URL in plain text runs to the next space.
const BARE_URL = /https?:\/\/\S+/g;
// Sentence punctuation after a URL ("see https://x.org.", "(https://x.org)") isn't part of it.
const TRAILING_PUNCTUATION = /[.,;:!?)\]]+$/;

/** A run of plain text, or a URL found in it that may become a link. */
export type TextPart = string | { href: string; text: string };

/** `text` split into plain runs and the http(s) URLs in it that httpOnlyUrl allows. */
export function linkParts(text: string): TextPart[] {
  const parts: TextPart[] = [];
  let at = 0;
  for (const match of text.matchAll(BARE_URL)) {
    const url = match[0].replace(TRAILING_PUNCTUATION, "");
    const href = httpOnlyUrl(url);
    if (!href) continue; // stays in the plain run after it
    if (match.index > at) parts.push(text.slice(at, match.index));
    parts.push({ href, text: url });
    at = match.index + url.length;
  }
  if (at < text.length) parts.push(text.slice(at));
  return parts;
}
