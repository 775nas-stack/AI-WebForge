from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from core.config import get_selected_model, set_selected_model

MODELS_DIR = Path("data/models")

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
def list_models():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(str(path) for path in MODELS_DIR.glob("*.gguf"))
    return {"models": files, "selected": get_selected_model()}


@router.post("/scan")
def scan_models():
    return list_models()


@router.post("/select")
def select_model(path: str):
    model_path = Path(path)
    if not model_path.exists():
        return {"status": "error", "message": "Model file not found"}
    resolved = str(model_path.resolve())
    set_selected_model(resolved)
    return {"status": "ok", "selected": resolved}
