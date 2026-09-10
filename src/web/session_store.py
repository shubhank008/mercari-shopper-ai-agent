"""In-memory browser-session ownership for the web demonstration."""

import time
from dataclasses import dataclass
from typing import Callable

from src.agent.harness import AgentHarness


@dataclass
class HarnessSession:
    """A harness and its last-use timestamp."""

    harness: AgentHarness
    last_used_at: float


class HarnessSessionStore:
    """Stores page-scoped harnesses and removes idle sessions opportunistically."""

    def __init__(self, factory: Callable[[], AgentHarness] = AgentHarness, idle_seconds: int = 1_800):
        self._factory = factory
        self._idle_seconds = idle_seconds
        self._sessions: dict[str, HarnessSession] = {}

    def get(self, session_id: str) -> tuple[AgentHarness, bool]:
        """Return the session harness and whether this request created it."""
        now = time.monotonic()
        self._evict_idle(now)
        session = self._sessions.get(session_id)
        if session is None:
            session = HarnessSession(harness=self._factory(), last_used_at=now)
            self._sessions[session_id] = session
            return session.harness, True
        session.last_used_at = now
        return session.harness, False

    def _evict_idle(self, now: float) -> None:
        """Drop expired in-memory state without exposing prior session data."""
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_used_at > self._idle_seconds
        ]
        for session_id in expired:
            del self._sessions[session_id]
