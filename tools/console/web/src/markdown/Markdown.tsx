// Renders Claude's text as React elements. Raw HTML stays literal text
// (react-markdown's default without rehype-raw), URLs pass httpOnlyUrl, and
// nothing ever goes through innerHTML.
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { markdownComponents } from "./components";
import { httpOnlyUrl } from "./links";
import styles from "./markdown.module.css";

const plugins = [remarkGfm];

/** One markdown body. `text` is untrusted server text. */
export function Markdown({ text }: { text: string }) {
  return (
    <div className={styles.body}>
      <ReactMarkdown
        remarkPlugins={plugins}
        urlTransform={httpOnlyUrl}
        components={markdownComponents}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
