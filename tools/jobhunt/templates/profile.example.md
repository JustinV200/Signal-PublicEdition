# Applicant profile

Setup copies this file to `life/areas/job-search/profile.md` (gitignored, never commit it). It is the only source for factual and legal answers on application forms. If a required question isn't answered here, the job is skipped as `needs-info` (see `runbook.md`). Lines marked `TODO(owner)` are not answers: runs treat them as missing. Digests and flag emails go to the email you apply with.

## Identity and contact
- Name: TODO(owner)
- Pronouns: TODO(owner) (or "decline")
- Email to apply with: TODO(owner)
- Phone: TODO(owner)
- Mailing address: TODO(owner)
- City for "current location" fields: TODO(owner)
- Website / portfolio: TODO(owner) (or "none"; separate several with commas)
- LinkedIn: TODO(owner) (or "none")
- GitHub: TODO(owner) (or "none")

## Resume
Put your resume PDF in `resume/`; runs upload it. Resume tailoring (the runbook's `Tailor resume` setting, Windows only) also needs the Word (.docx) file it was made from, in `resume/` too: give its file name below, or "none". Tailoring reads your website(s), GitHub and LinkedIn above for real facts to use.
- Resume Word file: none

## Education
- School, degree, major: TODO(owner)
- Start and graduation dates: TODO(owner)
- GPA (only if you want it given): TODO(owner)

## Work eligibility
- Authorized to work in: TODO(owner)
- Requires visa sponsorship now or in the future: TODO(owner)
- Non-compete or similar agreements: TODO(owner)
- Relatives or close contacts at the company: TODO(owner)

## Availability and location
- Earliest start date: TODO(owner)
- Target roles: TODO(owner) (e.g. "backend software engineer, new grad")
- Location preference: TODO(owner) (e.g. "New York City or remote")
- Willing to relocate: TODO(owner)
- Travel OK up to: TODO(owner)
- In office 5 days a week OK: TODO(owner)

## Pay
- Salary field required: TODO(owner) (a range, and one number for single-value fields)
- Salary field optional: leave blank.

## Short answers
- Short-answer and essay questions: TODO(owner) "draft" (the run drafts a truthful answer from the resume and this file, reviewed by a fresh subagent) or "skip" (log `needs-info`). Default: skip.
- A question or attestation this file doesn't answer: log the job `needs-info`. Never give a false answer or tick a statement that isn't true.

## EEO and demographics
Answer only what you list here. Every other demographic question gets the decline option.
- EEO answers: TODO(owner) (e.g. "Veteran status: not a protected veteran", or "none")

## Accounts
- Create job-site accounts when a site requires one: TODO(owner) "yes" or "no". Default: no (the job is logged `skipped-needs-account`). Only say yes if the sites' terms allow it.

## One application only
Companies that accept one application per candidate (the run keeps the one already in the tracker):
- (none)

## Already applied by owner
Companies to skip entirely because you applied yourself:
- (none)

## Never apply
Companies the run must never apply to; matches are flagged to you by email instead:
- (none)
