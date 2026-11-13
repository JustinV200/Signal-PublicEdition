// The markdown renderer is the one place untrusted text becomes elements:
// only http(s) links survive, and raw HTML must come out as literal text.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Markdown } from "../../src/markdown";

const SAMPLE = [
  "[ok](https://example.com/a)",
  "[bad](javascript:alert(1))",
  "[rel](/local/path)",
  "![pic](data:image/png;base64,AAAA)",
  '<b onclick="x()">bold</b>',
  "<script>alert(2)</script>",
].join(" ");

describe("Markdown", () => {
  it("keeps http(s) links, drops other schemes and shows raw HTML as text", () => {
    const html = renderToStaticMarkup(<Markdown text={SAMPLE} />);
    expect(html).toContain('href="https://example.com/a"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain('href="/local/path"');
    expect(html).not.toContain("<img");
    expect(html).toContain("[image] pic");
    expect(html).not.toContain("<b ");
    expect(html).not.toContain("<script");
    expect(html).toContain("&lt;b onclick=");
    expect(html).toContain("&lt;script&gt;");
  });
});
