# Vendored JS libraries

Served locally by the daemon so the board page never touches a CDN. Each folder holds only the dist files the page loads, plus the package's license file(s), copied unmodified from the npm registry tarball.

| Folder | Package | Version | License | Files |
|---|---|---|---|---|
| `mermaid/` | mermaid | 12.1.0 | MIT | `mermaid.min.js` (IIFE, global `mermaid`) |
| `roughjs/` | roughjs | 4.6.6 | MIT | `rough.js` (IIFE, global `rough`) |
| `katex/` | katex | 0.19.0 | MIT | `katex.min.js`, `katex.min.css`, `fonts/*.woff2` |
| `marked/` | marked | 18.0.14 | MIT | `marked.umd.js` (global `marked`) |
| `dompurify/` | dompurify | 3.4.16 | MPL-2.0 OR Apache-2.0 | `purify.min.js` (global `DOMPurify`) |

## How they were fetched

- Source: `https://registry.npmjs.org/<package>/-/<package>-<version>.tgz`. No Node was used.
- Each tarball was checked against the registry's sha512 `integrity` value before extracting.
- Versions are the newest stable release that was at least 14 days old on 2026-10-19. That way a freshly published, possibly compromised release can't slip in.
- Only woff2 KaTeX fonts are kept. `katex.min.css` lists woff2 first, and Edge always loads that one.

To upgrade, download the new tarball the same way, replace the files listed above, and update this table.
