// Static file serving for the dev mock server: hands out dist/ with SPA
// fallback to index.html. Development only; the Python backend serves dist/
// for real.
import { readFile } from "node:fs/promises";
import path from "node:path";

const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

/**
 * Serves `urlPath` from `root`. Paths without an extension get index.html so
 * the app's routes (there are none, but `/`) work. Refuses to leave `root`.
 */
export async function serveStatic(res, root, urlPath) {
  const rootDir = path.resolve(root);
  const wanted = path.extname(urlPath) ? urlPath : "/index.html";
  const file = path.resolve(rootDir, `.${wanted}`);
  if (!file.startsWith(rootDir + path.sep)) {
    res.writeHead(403).end("forbidden");
    return;
  }
  try {
    const body = await readFile(file);
    res.writeHead(200, {
      "content-type": CONTENT_TYPES[path.extname(file)] ?? "application/octet-stream",
    });
    res.end(body);
  } catch {
    res.writeHead(404).end("not found");
  }
}
