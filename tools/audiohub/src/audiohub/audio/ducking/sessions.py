"""Find Windows per-app audio sessions (the Volume Mixer entries) via pycaw.

Sessions are gathered from every active render endpoint, not just the
default one, so music playing to a non-default device is still found.

COM rules this module follows:
- Callers wrap use in `com_initialized()`, because comtypes only initialises
  COM on the thread that first imported it and Ducker may run on executor threads.
- COM objects are never kept past that block. Once a thread uninitialises
  COM, interface pointers created there are invalid. So Ducker re-finds
  sessions on every call and keys its saved volumes by app id.
"""

import contextlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

import comtypes
import psutil
from pycaw.api.audioclient import ISimpleAudioVolume
from pycaw.api.audiopolicy import IAudioSessionControl2, IAudioSessionManager2
from pycaw.constants import DEVICE_STATE, EDataFlow
from pycaw.utils import AudioUtilities

# HRESULT 0x80010106: COM is already initialised on this thread in another
# apartment mode. COM is still usable; the failed call must not be balanced.
RPC_E_CHANGED_MODE = -2147417850

# Process id of the shared "System Sounds" session, which has no process.
SYSTEM_SOUNDS_PROCESS_ID = 0


class SessionVolume(Protocol):
    """The part of pycaw's ISimpleAudioVolume that Ducker uses."""

    def GetMasterVolume(self) -> float: ...  # noqa: N802 - COM method name

    def SetMasterVolume(self, level: float, event_context: Any) -> None: ...  # noqa: N802


@dataclass(frozen=True)
class AppSession:
    """One app's audio session on one endpoint.

    `app_id` is the session identifier. It names the app and endpoint without a
    process id, so it survives restarts; several sessions can share it.
    """

    app_id: str
    process_name: str
    process_id: int
    volume: SessionVolume


@contextlib.contextmanager
def com_initialized() -> Iterator[None]:
    """Make COM usable on the current thread for the duration of the block.

    Safe to nest and to use on a thread where COM is already initialised.

    Raises:
        OSError: If COM initialisation fails for any reason other than
            RPC_E_CHANGED_MODE.
    """
    must_uninitialize = _initialize_com()
    try:
        yield
    finally:
        if must_uninitialize:
            comtypes.CoUninitialize()


def find_sessions(process_names: Iterable[str]) -> list[AppSession]:
    """Return the audio sessions whose process name is in `process_names`.

    Call inside `com_initialized()`, and don't keep the results past it.

    Args:
        process_names: Executable names such as "Spotify.exe" (case-insensitive).

    Returns:
        Matching sessions across all active render endpoints. Empty if none match.

    Raises:
        COMError | OSError: If Windows Core Audio calls fail.
    """
    wanted = {name.casefold() for name in process_names}
    return [session for session in _all_app_sessions() if session.process_name.casefold() in wanted]


def list_session_process_names() -> list[str]:
    """Return the sorted, de-duplicated process names of every current audio session.

    Handles COM initialisation itself. Meant for diagnostics.

    Raises:
        COMError | OSError: If Windows Core Audio calls fail.
    """
    with com_initialized():
        return sorted({session.process_name for session in _all_app_sessions()})


def _initialize_com() -> bool:
    try:
        comtypes.CoInitialize()
    except OSError as error:
        if error.winerror != RPC_E_CHANGED_MODE:
            raise
        return False
    # S_OK and S_FALSE (already initialised) both need a matching CoUninitialize.
    return True


def _all_app_sessions() -> list[AppSession]:
    sessions = [_to_app_session(control) for control in _session_controls()]
    return [session for session in sessions if session is not None]


def _session_controls() -> Iterator[Any]:
    for manager in _render_session_managers():
        enumerator = manager.GetSessionEnumerator()
        for position in range(enumerator.GetCount()):
            control = enumerator.GetSession(position)
            if control is not None:
                yield control.QueryInterface(IAudioSessionControl2)


def _render_session_managers() -> Iterator[Any]:
    device_enumerator = AudioUtilities.GetDeviceEnumerator()
    endpoints = device_enumerator.EnumAudioEndpoints(
        EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
    )
    for position in range(endpoints.GetCount()):
        endpoint = endpoints.Item(position)
        manager = endpoint.Activate(IAudioSessionManager2._iid_, comtypes.CLSCTX_ALL, None)
        yield manager.QueryInterface(IAudioSessionManager2)


def _to_app_session(control: Any) -> AppSession | None:
    process_id = control.GetProcessId()
    if process_id == SYSTEM_SOUNDS_PROCESS_ID:
        return None
    try:
        process_name = psutil.Process(process_id).name()
    except psutil.Error:
        # The process exited or can't be inspected, so it can't be a duck target.
        return None
    return AppSession(
        app_id=control.GetSessionIdentifier(),
        process_name=process_name,
        process_id=process_id,
        volume=control.QueryInterface(ISimpleAudioVolume),
    )
