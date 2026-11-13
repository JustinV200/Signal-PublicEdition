"""SessionError: an operation on a managed session that can't be done, with the reason.

The daemon's server turns it into an error reply; the message is written for
the caller (often a model), so it says what to do instead.
"""


class SessionError(ValueError):
    """The requested session operation isn't possible in the session's current state."""
