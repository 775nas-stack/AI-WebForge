"""Utilities for applying build steps and writing code safely."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from .project_manager import project_manager


@dataclass
class ExecutionContext:
    session_id: str
    project_name: str


class CodeExecutor:
    """Apply build steps by writing files and simulating runtime actions."""

    async def apply_files(
        self,
        context: ExecutionContext,
        files: Dict[str, str],
        *,
        delay: float = 0.05,
        on_write: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ) -> None:
        """Write a bundle of files to disk with optional delay for streaming."""

        for path, content in files.items():
            project_manager.save_file(context.project_name, path, content)
            if on_write is not None:
                await on_write(path, content)
            await asyncio.sleep(delay)


code_executor = CodeExecutor()
