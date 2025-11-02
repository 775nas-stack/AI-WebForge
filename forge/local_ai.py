"""Local inference utilities for AI-WebForge."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

try:  # pragma: no cover - optional dependency
    from transformers import AutoModelForCausalLM, AutoTokenizer
except Exception:  # pragma: no cover - optional dependency
    AutoModelForCausalLM = None  # type: ignore
    AutoTokenizer = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from ctransformers import AutoModelForCausalLM as CTransformersModel
except Exception:  # pragma: no cover - optional dependency
    CTransformersModel = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from llama_cpp import Llama
except Exception:  # pragma: no cover - optional dependency
    Llama = None  # type: ignore

from .utils import MODELS_DIR, get_active_model, set_active_model


LOGGER = logging.getLogger(__name__)


class LocalAIEngine:
    """Lightweight interface around locally hosted language models."""

    def __init__(self) -> None:
        self._model: Optional[object] = None
        self._tokenizer: Optional[object] = None
        self._generator: Callable[[str], str] = self._default_generator
        self._active_model: Optional[str] = get_active_model()
        if self._active_model:
            try:
                self.load_model(self._active_model)
            except Exception:  # pragma: no cover - best effort lazy load
                LOGGER.exception("Failed to eagerly load configured model '%s'.", self._active_model)

    # ------------------------------------------------------------------
    # model management
    # ------------------------------------------------------------------
    def load_model(self, model_name: str) -> None:
        """Load a local model and prepare an inference pipeline."""

        model_path = MODELS_DIR / model_name
        if not model_path.exists():
            raise FileNotFoundError(f"Model '{model_name}' not found in {MODELS_DIR}.")

        loader_stack = (
            self._try_load_transformers,
            self._try_load_ctransformers,
            self._try_load_llama_cpp,
        )

        last_error: Optional[Exception] = None
        for loader in loader_stack:
            try:
                generator = loader(model_path)
            except Exception as exc:  # pragma: no cover - depends on local environment
                last_error = exc
                continue
            else:
                self._generator = generator
                self._active_model = model_name
                set_active_model(model_name)
                LOGGER.info("Loaded local model '%s' using %s.", model_name, loader.__name__)
                return

        LOGGER.warning("Falling back to template responses for '%s': %s", model_name, last_error)
        self._model = None
        self._tokenizer = None
        self._generator = self._default_generator
        self._active_model = model_name
        set_active_model(model_name)

    # ------------------------------------------------------------------
    # generation
    # ------------------------------------------------------------------
    def generate_response(self, prompt: str) -> str:
        """Generate a text response using the active model."""

        if not self._active_model:
            available = sorted(p.name for p in MODELS_DIR.iterdir() if p.is_file())
            if available:
                self.load_model(available[0])
        try:
            return self._generator(prompt)
        except Exception:  # pragma: no cover - runtime guard
            LOGGER.exception("Local generation failed; using fallback response.")
            return self._default_generator(prompt)

    def clear_model(self) -> None:
        """Reset the active model and revert to template responses."""

        self._model = None
        self._tokenizer = None
        self._generator = self._default_generator
        self._active_model = None
        set_active_model(None)

    # ------------------------------------------------------------------
    # loader helpers
    # ------------------------------------------------------------------
    def _try_load_transformers(self, model_path: Path) -> Callable[[str], str]:
        if AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError("transformers not available")
        if not model_path.is_dir():
            raise ValueError("Transformers models must be provided as directories.")

        self._tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        self._model = AutoModelForCausalLM.from_pretrained(str(model_path))

        def _generate(prompt: str) -> str:
            if self._model is None or self._tokenizer is None:
                return self._default_generator(prompt)
            inputs = self._tokenizer(prompt, return_tensors="pt")
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=True,
                temperature=0.7,
            )
            return self._tokenizer.decode(outputs[0], skip_special_tokens=True)

        return _generate

    def _try_load_ctransformers(self, model_path: Path) -> Callable[[str], str]:
        if CTransformersModel is None:
            raise RuntimeError("ctransformers not available")
        if model_path.suffix.lower() not in {".gguf", ".ggml"}:
            raise ValueError("ctransformers expects GGUF/GGML weights")

        self._model = CTransformersModel.from_pretrained(
            model_type="llama",
            model_path=str(model_path),
        )

        def _generate(prompt: str) -> str:
            if self._model is None:
                return self._default_generator(prompt)
            return str(self._model(prompt, max_new_tokens=256, temperature=0.7))

        return _generate

    def _try_load_llama_cpp(self, model_path: Path) -> Callable[[str], str]:
        if Llama is None:
            raise RuntimeError("llama_cpp_python not available")
        if model_path.suffix.lower() not in {".gguf", ".ggml"}:
            raise ValueError("llama_cpp expects GGUF/GGML weights")

        self._model = Llama(model_path=str(model_path), n_ctx=4096)

        def _generate(prompt: str) -> str:
            if self._model is None:
                return self._default_generator(prompt)
            response = self._model(prompt, max_tokens=256, temperature=0.7)
            return str(response.get("choices", [{}])[0].get("text", "")).strip()

        return _generate

    # ------------------------------------------------------------------
    # fallbacks
    # ------------------------------------------------------------------
    def _default_generator(self, prompt: str) -> str:
        """Return a deterministic response when no local model is available."""

        prompt = prompt.strip()
        if not prompt:
            return "I'm ready to help describe and scaffold your next project."
        return (
            "Offline response: I noted your request and will scaffold a starter project. "
            "Upload a compatible model to enable richer conversations.\n\n"
            f"Prompt summary: {prompt[:400]}"
        )


local_ai = LocalAIEngine()

