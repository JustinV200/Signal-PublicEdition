# input

The input line. `InputLine` owns the draft (placeholder "Message Claude…"), sends on Enter or the Send button (switching to Chat, where the reply lands), opens command mode from the Commands button, recalls history on Up/Down (`useHistoryRecall` over the sessionStorage list in `history.ts`), grows 1 to 8 rows (`useAutoGrow`), hosts the command palette in command mode and swaps in `ConfirmLine` (`… ? [y/n]`) for voice actions. `focusInput()` lets other packages return focus here.

Public API: `index.ts`. Depends on `state`, `palette`, `ui`, `api` (types).
