from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path("data") / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {"selected_model": None}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_selected_model() -> Optional[str]:
    return load_config().get("selected_model")


def set_selected_model(path: Optional[str]) -> None:
    cfg = load_config()
    cfg["selected_model"] = path
    save_config(cfg)
