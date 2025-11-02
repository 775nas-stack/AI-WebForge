from __future__ import annotations

from pathlib import Path
from typing import Iterator, Optional

from llama_cpp import Llama

from core.config import get_selected_model


class LLMService:
    _llm: Optional[Llama] = None
    _path: Optional[str] = None

    @classmethod
    def ensure_loaded(cls) -> None:
        path = get_selected_model()
        if not path:
            raise RuntimeError("No model selected. Use /api/models/select.")
        path = str(Path(path).resolve())
        if cls._llm and cls._path == path:
            return
        cls._llm = Llama(model_path=path, n_ctx=4096, verbose=False)
        cls._path = path

    @classmethod
    def chat(cls, prompt: str) -> str:
        cls.ensure_loaded()
        res = cls._llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=0.6,
            max_tokens=512,
        )
        try:
            return res["choices"][0]["message"]["content"]
        except Exception:
            return str(res)

    @classmethod
    def stream(cls, prompt: str) -> Iterator[str]:
        cls.ensure_loaded()
        for chunk in cls._llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            temperature=0.6,
            max_tokens=512,
        ):
            delta = chunk["choices"][0]["delta"]
            if "content" in delta and delta["content"]:
                yield delta["content"]
