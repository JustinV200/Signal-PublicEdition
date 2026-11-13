# Drop your writing here

Put your own real writing in this folder. The copytone skill reads every file here to build `../voice-profile.md`. Everything in this folder except this README is gitignored, so your writing stays on your PC.

The easy way is `setup copytone` (or ask Claude to "set up copytone"): it imports files (.docx, .pdf, .txt, .md), takes pasted text, and can pull your own recent sent emails (your words only, quoted replies cut) for you to pick from.

What works best:
- 5 to 15 samples, across the kinds of thing you want written: emails, longer writing (essays, reports, posts), casual messages, and code if you want code in your style. 3 to 5 per kind is plenty.
- Raw and unedited by an AI model. Spell-checker-level polish is fine. Anything a model rewrote pulls the profile toward model voice, so leave it out.
- Casual messages are fine. The skill keeps your voice and lifts the register a notch on its own. One or two more formal pieces help it find your ceiling.
- Code with your original comments left in.
- Plain formats: .md, .txt, or code files. Paste .docx or .pdf content into a .txt or .md (setup does this for you).

Naming: `<kind>-<short-name>.<ext>`, for example `email-landlord.md`, `writing-report.md`, `message-team.md`, `code-sorting.py`. The kind prefix helps the skill match the right sample to the right task.

The skill ignores this README.
