# keys

`useGlobalKeys` installs the window-level shortcuts from DESIGN.md section 7: Ctrl+K, Ctrl+1 to 7, Esc (help, then input mode, then back to the scope), PageUp/PageDown/Ctrl+End from the input, and "any printable key focuses the input". Keys inside the textarea (Enter, history, palette navigation) belong to `input`.

Public API: `index.ts`. Depends on `state` (types) and `input` (focus helper).
