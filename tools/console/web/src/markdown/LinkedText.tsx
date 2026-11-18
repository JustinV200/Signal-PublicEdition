// Plain text with its bare http(s) URLs as links, for one-line hints such as
// where to get a missing program. The rest stays text; no Markdown is parsed.
import { ExternalLink } from "./components";
import { linkParts } from "./links";

/** `text` inline, each http(s) URL in it a new-tab link. `text` may be untrusted. */
export function LinkedText({ text }: { text: string }) {
  return (
    <>
      {linkParts(text).map((part, i) =>
        typeof part === "string" ? (
          part
        ) : (
          <ExternalLink key={i} href={part.href}>
            {part.text}
          </ExternalLink>
        ),
      )}
    </>
  );
}
