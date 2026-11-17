Report phase. Write the report and the writeup, following $playbook/reporting.md.

1. Pick the report format that fits the topic: $formats. Write `report.html` (html or artifact, self-contained), `report.md` (with PNGs in `figures/`) or `report.ipynb` (executed, outputs saved). $artifact_note
   The report must include: sources with links, data dates and access dates (the recorded sources below, plus any you used since); methods and why they were chosen, alternatives tried and validation scores; packages installed for the run ($installs); each finding's confidence as the word High, Medium or Low, with caveats; and a critic review section summarising `critique.md`.
2. Write `writeup.md`: a 1-2 page plain briefing to the user. Findings first, then a recommendation, then what would change the conclusion. Keep overlap with the report small.

Recorded sources (name | url | status | note | fetched):

$sources

End your reply with these two lines:
REPORT_FORMAT: <the format you chose>
TOP_FINDING: <the single most important finding, one sentence>
