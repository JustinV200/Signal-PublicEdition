// Element overrides for react-markdown. Links open in a new tab with
// noopener; images never fetch and render as a `[image] alt` link; task
// checkboxes are text; tables get a scroll wrapper; code blocks are the
// shared panel.
import type { ReactNode } from "react";
import type { Components } from "react-markdown";
import styles from "./markdown.module.css";

const IMAGE_PREFIX = "[image]";

/** A link that opens in a new tab with noopener; plain text when `href` is missing. */
export function ExternalLink({ href, children }: { href?: string; children?: ReactNode }) {
  // react-markdown already ran urlTransform, so a missing href means "not http(s)".
  if (!href) return <span>{children}</span>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" title={href}>
      {children}
    </a>
  );
}

export const markdownComponents: Components = {
  a: ({ href, children }) => <ExternalLink href={href}>{children}</ExternalLink>,
  img: ({ src, alt }) => (
    <ExternalLink href={typeof src === "string" ? src : undefined}>
      {IMAGE_PREFIX} {alt}
    </ExternalLink>
  ),
  input: ({ checked }) => <span className={styles.check}>{checked ? "[x]" : "[ ]"}</span>,
  pre: ({ children }) => <pre className="panel">{children}</pre>,
  table: ({ children }) => (
    <div className={styles.tableWrap}>
      <table>{children}</table>
    </div>
  ),
};
