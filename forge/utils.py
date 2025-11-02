"""Utility helpers for AI-WebForge."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
MODELS_DIR = DATA_DIR / "models"
CONFIG_PATH = DATA_DIR / "config.json"

_DEFAULT_CONFIG: Dict[str, Any] = {"active_model": None}


def ensure_directories() -> None:
    """Ensure that the data directories and configuration file exist."""

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(_DEFAULT_CONFIG, indent=2), encoding="utf-8")


def load_config() -> Dict[str, Any]:
    """Return the persisted configuration dictionary."""

    ensure_directories()
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        CONFIG_PATH.write_text(json.dumps(_DEFAULT_CONFIG, indent=2), encoding="utf-8")
        return dict(_DEFAULT_CONFIG)


def save_config(config: Dict[str, Any]) -> None:
    """Persist the provided configuration dictionary."""

    ensure_directories()
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")


def get_active_model() -> Optional[str]:
    """Return the configured active model name, if any."""

    return load_config().get("active_model")


def set_active_model(name: Optional[str]) -> None:
    """Update the active model name in configuration."""

    config = load_config()
    config["active_model"] = name
    save_config(config)


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
