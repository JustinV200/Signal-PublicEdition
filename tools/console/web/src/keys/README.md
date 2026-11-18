# keys

`useGlobalKeys` installs the window-level shortcuts from DESIGN.md section 7: Ctrl+K, Ctrl+1 to 9, Esc, y / n while the input line asks a question (wherever focus is; the caller passes the confirm gate's `answer`; a held y or n answers once and its repeats never type into the input that comes back), PageUp/PageDown/Ctrl+End from the input, and "a typed key goes to the input". Keys inside the textarea (Enter, history, palette navigation) belong to `input`; the tab row's arrow keys belong to `status`.

`keyRoutes.ts` holds the decisions, free of the DOM: `sendsToInput` sends any printable key but Space to the input unless focus is in a text-like input, a textarea or a select (a checkbox or radio doesn't count; so after clicking a button, tab, board row or Retry, typing carries on in the input, while Space and Enter still press the focused control), and `escapeCloses` says what Esc closes, nearest first: the palette or confirm question, else help, else nothing (Esc then only focuses the input; it never changes view, and Ctrl+1 is home).

`viewForDigit` (`viewKeys.ts`) maps Ctrl+digit to a view: Ctrl+1 to Ctrl+6 are the six tabs (Scope, Chat, Voice, Boards, Tasks, System), Ctrl+7 and Ctrl+8 stay aliases for System (Models and Tools moved there), and Ctrl+9 opens Setup whether or not its tab shows.

Public API: `index.ts`. Depends on `state` (types) and `input` (focus helper).
