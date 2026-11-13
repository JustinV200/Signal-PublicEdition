# signal_brief.compose

- `compose(paths, kind="general") -> Brief`: entries past the bookmark plus every open wait, in section order, then priority, then newest. `Brief.id` is `b-<hash>` of the kind and covered refs and seqs. Only the general brief exists in phase 1.
- `render_model(brief, max_chars=6000, titles_only=False)`: the data for one `untrusted_brief_content` frame, at most `max_chars` framed (the prompt hook uses refs and titles in 2,000).
- `render_text(brief, max_chars=6000)`: markdown for a terminal.
- Each returns a `Render` with `body`, `shown` and `cut`, cut from the lowest-ranked end.

Depends on: `log`, `signal_untrusted`.
