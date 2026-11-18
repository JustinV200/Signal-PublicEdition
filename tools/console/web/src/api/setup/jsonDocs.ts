// Pulls the JSON documents out of a setup command's output lines. The CLI
// prints indented JSON (`json.dumps(..., indent=2)`), so a document starts
// with `{` or `[` at column 0 and ends with `}` or `]` at column 0; a step
// that ran a program may print that program's own lines before it.

/** One piece of a command's output: a plain line, or a whole JSON document. */
export type OutputPart = string | { json: unknown };

/**
 * `lines` in order, each JSON document folded into one `{json}` part and every
 * other line kept as it is. A start (`{` or `[` at column 0) that never parses,
 * such as a program's `[INFO] …` line, stays plain text.
 */
export function outputParts(lines: readonly string[]): OutputPart[] {
  const parts: OutputPart[] = [];
  let open: string[] | null = null;
  for (const line of lines) {
    if (line.startsWith("{") || line.startsWith("[")) {
      if (open) parts.push(...open); // the earlier start wasn't JSON after all
      open = [];
    }
    if (!open) {
      parts.push(line);
      continue;
    }
    open.push(line);
    const closes = open.length === 1 || line.startsWith("}") || line.startsWith("]");
    if (!closes) continue;
    try {
      parts.push({ json: JSON.parse(open.join("\n")) });
      open = null;
    } catch {
      // Not complete yet (a one-line start like `{`), or not JSON: keep reading.
    }
  }
  if (open) parts.push(...open);
  return parts;
}

/** Every top-level JSON document in `lines`, in order; other lines are skipped. */
export function jsonDocs(lines: readonly string[]): unknown[] {
  return outputParts(lines).flatMap((part) => (typeof part === "string" ? [] : [part.json]));
}

/** The first JSON document in `lines`; throws when there is none. */
export function firstJson(lines: readonly string[]): unknown {
  const [doc] = jsonDocs(lines);
  if (doc === undefined) throw new Error(lines.at(-1) ?? "setup printed nothing");
  return doc;
}
