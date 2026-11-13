# life/ (optional)

An optional private knowledge base for the owner: responsibilities, weekly plans, an inbox and notes that agents read for context. Everything in this folder except this README is gitignored, so it never leaves your PC.

Tools that use it, if you set them up:
- `tools/mail-digest` adds dated lines from email to `inbox.md` and to the current week's plan (`terms/<term>/weeks/<YYYY-MM-DD>-to-<YYYY-MM-DD>/plan.md`) and course or area READMEs.
- `tools/whiteboard` shows the week plan's open `- [ ]` todos on its TODO view.
- `tools/jobhunt` keeps its runbook, profile, resume and tracker in `areas/job-search/`.
- The browser tool may upload files from here (`[uploads] roots`).

Start with an empty `inbox.md`; setup creates the folders a chosen tool needs.
