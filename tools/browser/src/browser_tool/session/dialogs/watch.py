"""DialogWatch: hold the dialogs a page opens until the model answers them.

Without a dialog listener Playwright dismisses every alert, confirm, prompt and
beforeunload on its own, so the model never learns that "Delete 3 messages?"
was asked (and declined). With this watch on a context:
- an alert is accepted at once (it has only an OK button) and noted for the
  next result;
- a confirm, prompt or beforeunload stays pending: the page is frozen until
  someone answers (Playwright's click, press and evaluate don't return), so the
  actions refuse a tab with one (actions.guards) and actions.answer_dialog
  answers it.
With holds_dialogs=False (visit mode, which has no model to answer) every
dialog is dismissed, as Playwright would without a listener.

Each pending dialog keeps the texts of the last action on its tab (its
trigger, e.g. the label of the clicked button), so accepting a bare "Are you
sure?" after clicking "Delete" is gated as a delete. It also says whether it
opened while an action was running on purpose (during_act; see race.py).
Dialog messages are page text: they are never logged.
"""

import asyncio
import logging
import weakref
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, NamedTuple

from playwright.async_api import BrowserContext, Dialog, Page

logger = logging.getLogger(__name__)

ALERT = "alert"
# Long enough for any real question, short enough to keep results small.
MAX_MESSAGE_CHARS = 500
# Alerts kept per result; a page looping on alert() only adds to a count.
MAX_ALERTS = 5


@dataclass(eq=False)
class PendingDialog:
    """A confirm, prompt or beforeunload dialog waiting for an answer.

    Attributes:
        dialog: Playwright's dialog (accept or dismiss it).
        page: Its tab.
        kind: "confirm", "prompt" or "beforeunload".
        message: Its text, capped at MAX_MESSAGE_CHARS (page-supplied).
        default_value: A prompt's preset text (page-supplied), else "".
        trigger: The texts of the last action on the tab before it opened.
        during_act: It opened while an action was acting on the tab.
    """

    dialog: Dialog
    page: Page
    kind: str
    message: str
    default_value: str
    trigger: tuple[str, ...]
    during_act: bool


class AlertNote(NamedTuple):
    """An alert that was accepted, for the next result (the message is page-supplied)."""

    page: Page
    message: str


class DialogWatch:
    """Holds each tab's open dialog, the alerts seen, and the last action's texts."""

    def __init__(self, *, holds_dialogs: bool = True) -> None:
        """Args: holds_dialogs: False dismisses every dialog (visit mode)."""
        self._holds = holds_dialogs
        # Weak keys, so closed tabs don't pile up.
        self._pending: weakref.WeakKeyDictionary[Page, PendingDialog] = weakref.WeakKeyDictionary()
        self._triggers: weakref.WeakKeyDictionary[Page, tuple[str, ...]] = (
            weakref.WeakKeyDictionary()
        )
        self._acting: weakref.WeakKeyDictionary[Page, int] = weakref.WeakKeyDictionary()
        # How many confirms, prompts and beforeunloads each tab has opened.
        self._opened: weakref.WeakKeyDictionary[Page, int] = weakref.WeakKeyDictionary()
        self._alerts: list[AlertNote] = []
        self._more_alerts = 0  # accepted past MAX_ALERTS since the last take
        self._subscribers: list[Callable[[PendingDialog], None]] = []
        # Answers and stalled actions still running; held so they aren't collected.
        self._background: set[asyncio.Future[Any]] = set()

    def watch(self, context: BrowserContext) -> None:
        """Hold the dialogs of every open and future tab of `context`."""
        context.on("dialog", self._on_dialog)

    def pending(self, page: Page) -> PendingDialog | None:
        """The dialog open on `page`, or None."""
        found = self._pending.get(page)
        return None if found is None or page.is_closed() else found

    def all_pending(self) -> list[PendingDialog]:
        """Every open dialog on a tab that is still open."""
        return [found for page, found in list(self._pending.items()) if not page.is_closed()]

    def opened_count(self, page: Page) -> int:
        """How many dialogs `page` has held so far (a change means one opened meanwhile)."""
        return self._opened.get(page, 0)

    def take(self, page: Page) -> PendingDialog | None:
        """Remove and return `page`'s open dialog (the caller answers it)."""
        return self._pending.pop(page, None)

    def restore(self, pending: PendingDialog) -> None:
        """Put back a dialog taken for an answer that was then refused."""
        if self.pending(pending.page) is None:
            self._pending[pending.page] = pending

    def take_alerts(self) -> tuple[list[AlertNote], int]:
        """The first MAX_ALERTS alerts accepted since the last call, and how many more."""
        taken = (self._alerts, self._more_alerts)
        self._alerts, self._more_alerts = [], 0
        return taken

    def note_trigger(self, page: Page, texts: tuple[str, ...]) -> None:
        """Remember the texts of the action about to run on `page` (empty keeps the old)."""
        if texts:
            self._triggers[page] = texts

    def begin_act(self, page: Page) -> None:
        """Mark `page` as being acted on: a dialog now opens during_act."""
        self._acting[page] = self._acting.get(page, 0) + 1

    def end_act(self, page: Page) -> None:
        """Undo one begin_act."""
        count = self._acting.get(page, 0) - 1
        if count > 0:
            self._acting[page] = count
        else:
            self._acting.pop(page, None)

    def subscribe(self, callback: Callable[[PendingDialog], None]) -> Callable[[], None]:
        """Call `callback` with each dialog that becomes pending; returns the unsubscribe."""
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def keep(self, work: asyncio.Future[Any]) -> None:
        """Hold a task that runs on in the background, and log (by type) how it failed."""
        self._background.add(work)
        work.add_done_callback(self._forget)

    def _forget(self, work: asyncio.Future[Any]) -> None:
        self._background.discard(work)
        if not work.cancelled() and work.exception() is not None:
            logger.info("background browser task failed: %s", type(work.exception()).__name__)

    def _run(self, answer: Coroutine[Any, Any, None]) -> None:
        self.keep(asyncio.ensure_future(answer))

    def _on_dialog(self, dialog: Dialog) -> None:
        """Accept an alert, dismiss when not holding, else hold the dialog. Never raises."""
        try:
            self._handle(dialog)
        except Exception as error:  # noqa: BLE001 - must not break Playwright's event dispatch
            logger.error("dialog handling failed (%s); dismissing", type(error).__name__)
            self._run(dialog.dismiss())

    def _handle(self, dialog: Dialog) -> None:
        page = dialog.page
        if page is None or not self._holds:  # no tab (a service worker), or visit mode
            self._run(dialog.dismiss())
            return
        message = dialog.message[:MAX_MESSAGE_CHARS]
        if dialog.type == ALERT:
            self._run(dialog.accept())
            if len(self._alerts) < MAX_ALERTS:
                self._alerts.append(AlertNote(page, message))
            else:
                self._more_alerts += 1
            return
        pending = PendingDialog(
            dialog=dialog,
            page=page,
            kind=dialog.type,
            message=message,
            default_value=dialog.default_value[:MAX_MESSAGE_CHARS],
            trigger=self._triggers.get(page, ()),
            during_act=page in self._acting,
        )
        self._pending[page] = pending
        self._opened[page] = self._opened.get(page, 0) + 1
        logger.info("a %s dialog opened; held for the model", pending.kind)
        for callback in list(self._subscribers):
            callback(pending)
