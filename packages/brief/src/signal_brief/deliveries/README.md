# signal_brief.deliveries

What the owner was given (`shown.json`) and acking it.

- `record_delivery(paths, brief, render, origin, now)`: one render on one surface becomes `b-<hash>.<n>` with its refs and `through` (newest seq shown, or just before the oldest cut entry past the bookmark). It also records whether the render cut any entry past the bookmark (`cut_new`). A prompt hook's records its session id and the due brief it answered.
- `ack_delivery(paths, id, through, now)`: moves the bookmark at most to the delivery's through, records the ack and drops the due brief if the delivery was given at or after it was marked. An unknown id acks nothing.
- `relayed_through(delivery, replies, bookmark)`: the Claude session rule. A ref counts when a reply line names it with one of its title words (not filler); only refs past the bookmark can hold the ack back. None unless a ref past the bookmark was relayed (any ref if the delivery has none), and always None for a delivery that showed no new ref but cut some.

Depends on: `compose`, `log`, `presence`, `store`.
