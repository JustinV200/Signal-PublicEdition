# signal_brief.log

The event log (`events.jsonl`), its numbering and the bookmark.

- `append_entry(paths, new, now)`: validates (`validate.py`), then under the lock gives the line the next seq and, for a key's first line, a permanent ref (kind letter plus that letter's next count, like `D7`). Later lines for the key keep its ref. A line whose digest matches its key's current one isn't written.
- `resolve_entry(paths, key_or_ref, now)`; `append_locked` for callers holding the lock.
- `current_entries(paths)`: the folded log (each key's last line), oldest first. `find_entry` matches a ref, then a key.
- Compaction (`compact.py`): past 512 KB or weekly, keep each key's last line and drop closed keys (anything but an open wait) over 30 days old that the owner has been briefed on (at or before the bookmark). An entry past the bookmark stays however old. Counters outlive it, so refs never move.
- `read_through`, `advance_through_locked`: `bookmark.json`, only forward.

Depends on: `store`, `text`, `times`, `paths`.
