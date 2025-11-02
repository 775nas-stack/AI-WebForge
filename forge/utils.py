"""Utility helpers for AI-WebForge."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
MODELS_DIR = DATA_DIR / "models"


def ensure_directories() -> None:
    """Ensure that the data directories required by the application exist."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    """Return a filesystem-friendly slug for the provided value."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\-\s]+", "", value)
    value = re.sub(r"[\s\-]+", "-", value)
    return value or "project"


def human_readable_size(num_bytes: int) -> str:
    """Convert a byte value into a human-readable string."""
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num_bytes < step:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= step
    return f"{num_bytes:.1f} PB"


def collect_directory_tree(root: Path) -> Dict[str, Dict[str, str]]:
    """Return a representation of a project's directory tree."""
    tree: Dict[str, Dict[str, str]] = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        relative_dir = Path(dirpath).relative_to(root)
        tree[str(relative_dir)] = {name: str(Path(dirpath, name).relative_to(root)) for name in filenames}
    return tree


ensure_directories()
