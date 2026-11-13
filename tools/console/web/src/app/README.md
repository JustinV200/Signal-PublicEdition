# app

The top of the tree. `App` mounts the store and gates on the session: `SignIn` on 401, nothing while checking, otherwise `Shell` (status line, help panel, one scrolling view, input line, global keys).

Public API: `index.ts`. Depends on `state`, `status`, `help`, `views/*` (scope is the landing view), `input`, `keys`.
