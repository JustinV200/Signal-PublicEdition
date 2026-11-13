---
name: copytone
description: Write or rewrite prose and code in the user's own voice, learned from real samples in this skill's samples/ folder. Use for outbound writing (emails, messages, posts, documents for other people), when the user asks for something "in my voice", "like I'd write it", "make it sound like me", says "test my copytone voice", or invokes /copytone. Matches the user's own style from their samples, down to habits like punctuation, sentence rhythm and comment density.
argument-hint: [what to write, or the path of a draft to rewrite]
---

# copytone

Produce writing or code that reads like the user wrote it.

Files in `.claude/skills/copytone/`:
- `samples/` : the user's real writing and code. The source of truth. Gitignored except its README.
- `voice-profile.md` : the distilled voice, built from the samples (from `voice-profile.template.md`). Gitignored too.
- `tells.md` : generic habits to avoid in prose and code, so the result reads as the user's own. Hard rules unless the profile says the user does one of them.

Task: $ARGUMENTS
(If blank, the task is whatever the user just asked for in the conversation.)

## 1. Load the voice

1. If `voice-profile.md` doesn't exist, copy `voice-profile.template.md` to it. Read `voice-profile.md` and `tells.md`.
2. Rebuild the profile if its `status` is `unbuilt`, if the number of files in `samples/` (not counting its README) differs from `samples-read`, if any sample is newer than the `built` date, or if the user asks for a rebuild. To rebuild:
   - Read every file in `samples/` except its README. All of them, not a subset.
   - Fill in every section of the profile under the headings already there. Be specific and quote the samples. Vague entries like "casual tone" are useless. "Starts most paragraphs with 'So' or 'I think', never with a transition word" is what you want.
   - Keep any line in the old profile marked `keep`.
   - Set `status: built`, `built: <today's date>`, `samples-read: <count>`. Overwrite the file.
   - Tell the user in one line that the profile was rebuilt.
3. If `samples/` has nothing but its README, stop and offer to collect samples (`setup copytone`, or the `setup samples` commands in the setup skill). Do not build a voice from this conversation's messages. Chat messages the user saves as sample files are fine.

## 2. Pick the register, then lift it one notch

Samples are often casual: chat messages, quick emails. Unless the task says otherwise, aim a bit more polished than the closest sample while still sounding like the user: the register of a decent email to someone they respect. Not a cover letter, not a corporate memo.

Scale, low to high: chat message, everyday email, report or post, formal document. Default target is one step above the closest sample. If the task names its register, go there, but the voice comes along and the chat-isms do not. Only mention the register choice before the output if the samples give no footing for the task at all.

The profile's "Lifting the register" section adds specifics once built.

Keep when lifting:
- Sentence rhythm, with fewer run-ons per paragraph if the samples run long.
- Contractions, person and plain verbs the samples use, and the user's way of asking for things.
- Habits like admitting uncertainty or adding an afterthought, toned down to one instance.
- Consistent spelling or punctuation quirks from the profile, but rarer, and none in anything formal.

Drop when lifting:
- Texting abbreviations (u, tmrw, idk, lol, thx). Spell them out.
- Stacked questions in one breath. One question per sentence, at most two per piece.
- Lowercase sentence starts, missing apostrophes, and filler openers.
- More than one filler hedge ("basically", "kinda") per piece.

Do not overshoot:
- No formal vocabulary the samples never use (regarding, please advise, as per, I am writing to).
- No sign-off ceremony past what the samples show.
- No smoothing every sentence into the same shape. The lift removes chat-isms. It does not add polish.
- The test: if the user read it back, the reaction should be "that's me on a good day", not "who wrote this".

## 3. Write it

- The profile beats your defaults on every axis: sentence length, paragraph length, vocabulary, punctuation, openers, closers, hedging, structure, polish.
- Match the polish of the samples plus the one-notch lift from step 2. A repeated word or a slightly loose sentence is fine. Match the user's own level and style on a careful day.
- Reproduce the consistent quirks in the profile, lightly. One or two per page, not every sentence.
- Stay inside what the user would plausibly know and say. No vocabulary or references the samples and the task don't support.
- Length: what was asked for. If nothing was said, the typical length in the samples for that register.
- Code: follow the "Code habits" section of the profile and the Code half of `tells.md`.
- Rewriting an existing draft: keep the argument, facts, and order. Change the voice, not the substance.

## 4. Check it

Go through `tells.md` line by line against the output and fix every hit. Then check against the profile: openers, closers, sentence length mix, vocabulary, structure. Then read it once as the intended reader would. Any sentence that doesn't sound like the user gets rewritten.

## 5. Return only the piece

Output the text or code by itself. No "Here's a version in your voice", no notes on what changed, no recap after. If you had to assume something (register, length, missing detail), one line before the piece.

## Voice test ("test my copytone voice")

Load the voice (step 1, rebuilding if needed). Write one neutral paragraph of about 80 words (for example, telling a friend about a change of plans), then rewrite it in the user's voice following steps 2 to 4. Show both and ask whether the second sounds like them. If not, ask what's off, add a `keep` line to the profile for each correction, and try once more.
