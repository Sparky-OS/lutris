"""Tells the desktop that a game's window holds full side by side stereo content

The desktop (Stereo KWin) draws the picture the display needs from a window that is declared
as full side by side, the left eye first. The declaration is made with the stereo_declare module
of libstereo-declare; without it, or on a desktop that does not take declarations, nothing here
works, and the caller is told why."""

from gettext import gettext as _
from typing import Callable, Optional, Set

from gi.repository import GLib

from lutris.exceptions import MisconfigurationError
from lutris.util.log import logger

try:
    import stereo_declare
except ImportError:  # python3-stereo-declare is optional
    stereo_declare = None

POLL_INTERVAL_MS = 100


def is_available() -> bool:
    """True if the stereo_declare module is installed"""
    return stereo_declare is not None


def open_declaration() -> "stereo_declare.Declaration":
    """Connects to the desktop; raises MisconfigurationError with the reason if that is not possible"""
    if not is_available():
        raise MisconfigurationError(_("Stereo 3D needs the python3-stereo-declare package."))
    try:
        return stereo_declare.Declaration(on_declare=lambda window: logger.info("Declared window 0x%x as stereo", window))
    except stereo_declare.StereoUnavailable as ex:
        raise MisconfigurationError(_("Stereo 3D is not available on this desktop: %s") % ex) from ex


class StereoWatcher:
    """Declares the game's window as it appears, and takes the declaration back when stopped.

    The window comes from the file in which the wrapper reports it (state_path) or, for a game that
    draws full side by side itself, from the game's processes (get_pids)."""

    def __init__(
        self,
        declaration: "stereo_declare.Declaration",
        state_path: Optional[str] = None,
        get_pids: Optional[Callable[[], Set[int]]] = None,
    ):
        self.declaration = declaration
        self.state_path = state_path
        self.get_pids = get_pids
        self.last_state = None
        self.source_id = GLib.timeout_add(POLL_INTERVAL_MS, self.poll)

    @property
    def declared_any(self) -> bool:
        return self.declaration.declared_any

    def poll(self) -> bool:
        if self.state_path:
            state = stereo_declare.window_state(self.state_path)
            if state and state != self.last_state:
                logger.info("Render resolution per eye: %dx%d", state[0] // 2, state[1])
                self.last_state = state
            wanted = self.declaration.candidates(state, self.get_pids() if self.get_pids else set())
        else:
            wanted = self.declaration.windows_of(self.get_pids())
        self.declaration.update(wanted)
        return True

    def stop(self) -> None:
        GLib.source_remove(self.source_id)
        self.declaration.close()
