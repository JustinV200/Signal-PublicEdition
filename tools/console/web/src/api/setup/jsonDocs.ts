// Pulls the JSON documents out of a setup command's output lines. The CLI
// prints indented JSON (`json.dumps(..., indent=2)`), so a document starts
// with `{` or `[` at column 0 and ends with `}` or `]` at column 0; a step
// that ran a program may print that program's own lines before it.

/** Every top-level JSON document in `lines`, in order; other lines are skipped. */
export function jsonDocs(lines: readonly string[]): unknown[] {
  const docs: unknown[] = [];
  let open: string[] | null = null;
  for (const line of lines) {
    if (line.startsWith("{") || line.startsWith("[")) open = [];
    if (!open) continue;
    open.push(line);
    const closes = open.length === 1 || line.startsWith("}") || line.startsWith("]");
    if (!closes) continue;
    try {
      docs.push(JSON.parse(open.join("\n")));
      open = null;
    } catch {
      // Not complete yet (a one-line start like `{`), or not JSON: keep reading.
    }
  }
  return docs;
}

/** The first JSON document in `lines`; throws when there is none. */
export function firstJson(lines: readonly string[]): unknown {
  const [doc] = jsonDocs(lines);
  if (doc === undefined) throw new Error(lines.at(-1) ?? "setup printed nothing");
  return doc;
}
