"""Model management utilities for AI-WebForge."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import torch
except Exception:  # pragma: no cover - optional dependency
    torch = None  # type: ignore

from .utils import MODELS_DIR, get_active_model, human_readable_size, set_active_model


SUPPORTED_EXTENSIONS = {".pt", ".onnx", ".gguf", ".safetensors"}


@dataclass
class ModelMetadata:
    """Structured information about a stored model."""

    name: str
    path: Path
    size: int
    hash: str

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "size": human_readable_size(self.size),
            "hash": self.hash,
            "type": self.extension.lstrip("."),
            "path": str(self.path),
        }


class ModelLab:
    """Handle storing, listing, and comparing machine learning models."""

    def __init__(self, base_dir: Path = MODELS_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _metadata_path(self, filename: str) -> Path:
        return self.base_dir / f"{filename}.meta.json"

    def _hash_file(self, file_path: Path) -> str:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def save_model(self, filename: str, data: bytes) -> Dict[str, str]:
        """Persist a new model file to disk and return its metadata."""
        target_path = self.base_dir / filename
        target_path.write_bytes(data)
        file_hash = self._hash_file(target_path)
        metadata = ModelMetadata(
            name=filename,
            path=target_path,
            size=target_path.stat().st_size,
            hash=file_hash,
        )
        record = metadata.to_dict()
        record["uploaded_at"] = datetime.utcnow().isoformat()
        record["parameters"] = self._estimate_parameters(target_path)
        self._metadata_path(filename).write_text(json.dumps(record, indent=2), encoding="utf-8")
        if not get_active_model():
            set_active_model(filename)
        record["active"] = record["name"] == get_active_model()
        return record

    def list_models(self) -> List[Dict[str, str]]:
        """Return metadata for all stored models."""
        models: List[Dict[str, str]] = []
        for path in sorted(self.base_dir.iterdir()):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                metadata_path = self._metadata_path(path.name)
                if metadata_path.exists():
                    try:
                        payload = json.loads(metadata_path.read_text())
                        payload.setdefault("active", payload.get("name") == get_active_model())
                        models.append(payload)
                        continue
                    except json.JSONDecodeError:
                        pass
                file_hash = self._hash_file(path)
                payload = ModelMetadata(
                    name=path.name,
                    path=path,
                    size=path.stat().st_size,
                    hash=file_hash,
                ).to_dict()
                payload["uploaded_at"] = datetime.utcnow().isoformat()
                payload["parameters"] = self._estimate_parameters(path)
                payload["active"] = payload["name"] == get_active_model()
                models.append(payload)
        return models

    def compare_models(self, first: str, second: str) -> Dict[str, Optional[str]]:
        """Return a simple comparison between two models."""
        first_path = self.base_dir / first
        second_path = self.base_dir / second
        if not first_path.exists() or not second_path.exists():
            raise FileNotFoundError("Both models must exist to run a comparison.")

        first_meta = ModelMetadata(
            name=first,
            path=first_path,
            size=first_path.stat().st_size,
            hash=self._hash_file(first_path),
        )
        second_meta = ModelMetadata(
            name=second,
            path=second_path,
            size=second_path.stat().st_size,
            hash=self._hash_file(second_path),
        )

        comparison = {
            "first": first_meta.to_dict(),
            "second": second_meta.to_dict(),
            "size_difference": human_readable_size(abs(first_meta.size - second_meta.size)),
            "matching_hash": str(first_meta.hash == second_meta.hash),
        }
        return comparison

    def optimize_model(self, first: str, second: str) -> str:
        """Placeholder optimisation that pretends to merge two models."""
        first_path = self.base_dir / first
        second_path = self.base_dir / second
        if not first_path.exists() or not second_path.exists():
            raise FileNotFoundError("Both models must exist to run optimisation.")

        merged_name = f"merged_{first_path.stem}_{second_path.stem}{first_path.suffix}"
        merged_path = self.base_dir / merged_name
        merged_path.write_bytes(first_path.read_bytes())
        return merged_name

    def select_model(self, filename: str) -> Dict[str, str]:
        """Mark the provided model as active for inference."""

        target = self.base_dir / filename
        if not target.exists():
            raise FileNotFoundError(f"Model '{filename}' not found.")
        set_active_model(filename)
        return {"active_model": filename}

    def delete_model(self, filename: str) -> None:
        """Remove a stored model and associated metadata."""

        target = self.base_dir / filename
        if not target.exists():
            raise FileNotFoundError(f"Model '{filename}' not found.")
        target.unlink()
        meta = self._metadata_path(filename)
        if meta.exists():
            meta.unlink()
        if get_active_model() == filename:
            set_active_model(None)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _estimate_parameters(self, path: Path) -> Optional[str]:
        """Return a lightweight parameter estimate for PyTorch models."""

        if torch is None or path.suffix.lower() not in {".pt", ".pth", ".safetensors"}:
            return None
        try:
            weights = torch.load(path, map_location="cpu")  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - best effort
            return None
        if isinstance(weights, dict) and "state_dict" in weights:
            weights = weights["state_dict"]
        if isinstance(weights, dict):
            total = sum(param.numel() if hasattr(param, "numel") else 0 for param in weights.values())
            if total:
                return f"{total:,}"
        return None


model_lab = ModelLab()
