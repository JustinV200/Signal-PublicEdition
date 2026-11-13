"""Public API of whiteboard.daemon.idle: the idle view inside the running daemon.

IdleController keeps its data fresh and applies the default rule; InkWatch feeds it the
change watcher's ink reports; add_idle_routes exposes it under /api/idle.
"""

from whiteboard.daemon.idle.controller import IdleController, IdleHooks
from whiteboard.daemon.idle.ink_watch import InkWatch
from whiteboard.daemon.idle.local_sources import IdleFiles
from whiteboard.daemon.idle.network import Lookups
from whiteboard.daemon.idle.routes import add_idle_routes

__all__ = ["IdleController", "IdleFiles", "IdleHooks", "InkWatch", "Lookups", "add_idle_routes"]
