# whiteboard.cli.commands.views

The subcommands that switch or redraw what the board shows, each a `Command` registered in `cli/commands/__init__.py`:

- `todo.py`: `whiteboard todo sync|show|hide|done|undone` (the TODO view; `sync --if-running` is the 06:00 task).
- `idle.py`: `whiteboard idle show|hide|sync` (the idle view, the default when nothing is drawn).
- `tasks.py`: `whiteboard tasks show` (the task grid).
- `night.py`: `whiteboard night show|hide` (sleep mode's night view).
- `keynotes.py`: `whiteboard keynotes` (write today's keynotes with Claude, then a TODO sync on a running daemon; the 06:00 task's first step).

Each goes through the daemon's API (`whiteboard.daemon_client`) and starts the daemon if it isn't running, except `todo sync --if-running` and `keynotes`, which never start it. Heavy imports stay inside `run()` so the CLI starts quick.
