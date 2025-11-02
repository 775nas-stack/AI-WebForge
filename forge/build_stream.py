"""Streaming utilities for broadcasting build events to the frontend."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4


class BuildSession:
    """Container for streaming build events tied to a single request."""

    def __init__(self, prompt: str) -> None:
        self.id = uuid4().hex
        self.prompt = prompt
        self.project_name: Optional[str] = None
        self.created_at = datetime.utcnow().isoformat() + "Z"
        self.queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self.history: List[Dict[str, Any]] = []
        self.completed = False

    def snapshot(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "prompt": self.prompt,
            "project": self.project_name,
            "created_at": self.created_at,
            "completed": self.completed,
        }


class BuildStream:
    """Manage build sessions and allow websocket consumers to subscribe to events."""

    def __init__(self) -> None:
        self._sessions: Dict[str, BuildSession] = {}
        self._lock = asyncio.Lock()

    def create_session(self, prompt: str) -> BuildSession:
        session = BuildSession(prompt)
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Optional[BuildSession]:
        return self._sessions.get(session_id)

    async def stream(self, session_id: str) -> AsyncIterator[Dict[str, Any]]:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")

        while True:
            event = await session.queue.get()
            yield event
            if event.get("type") in {"complete", "error"}:
                session.completed = True
                break

    def publish(self, session_id: str, event: Dict[str, Any]) -> None:
        session = self.get_session(session_id)
        if session is None:
            return

        enriched = dict(event)
        enriched.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        session.history.append(enriched)
        session.queue.put_nowait(enriched)

    def prime(self, session_id: str, event: Dict[str, Any]) -> None:
        """Immediately add an event to the session history without queueing."""

        session = self.get_session(session_id)
        if session is None:
            return
        enriched = dict(event)
        enriched.setdefault("timestamp", datetime.utcnow().isoformat() + "Z")
        session.history.append(enriched)

    def close(self, session_id: str) -> None:
        session = self.get_session(session_id)
        if session is None:
            return
        session.completed = True

    def drop(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


build_stream = BuildStream()
