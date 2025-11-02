"""AI builder that interfaces with language models to scaffold projects."""
from __future__ import annotations

import json
import os
from typing import Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional dependency import guard
    OpenAI = None  # type: ignore

from .project_manager import project_manager
from .utils import slugify


DEFAULT_PROJECT_STRUCTURE = {
    "app/main.py": """from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get('/')\nasync def read_root():\n    return {'message': 'Hello from your generated app!'}\n""",
    "app/templates/index.html": """<!DOCTYPE html>\n<html lang='en'>\n<head>\n    <meta charset='UTF-8' />\n    <title>Generated App</title>\n</head>\n<body>\n    <h1>{{ title }}</h1>\n</body>\n</html>\n""",
    "app/static/style.css": "body { font-family: Inter, sans-serif; background: #0f172a; color: white; }\n",
}


class AIBuilder:
    """High level interface for AI-assisted project scaffolding."""

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.enabled = bool(api_key and OpenAI is not None)
        self._client: Optional[OpenAI] = OpenAI(api_key=api_key) if self.enabled else None

    def _call_openai(self, prompt: str) -> str:
        if not self.enabled or self._client is None:
            raise RuntimeError("OpenAI client not configured.")

        response = self._client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )
        if hasattr(response, "output_text") and response.output_text:  # type: ignore[attr-defined]
            return str(response.output_text)  # type: ignore[attr-defined]
        if hasattr(response, "choices"):
            return "\n".join(choice.message.get("content", "") for choice in getattr(response, "choices", []))
        return ""

    def _fallback_project(self, prompt: str) -> Dict[str, str]:
        title = prompt.title()[:50] or "AI WebForge"
        files = DEFAULT_PROJECT_STRUCTURE.copy()
        index_html = files["app/templates/index.html"].replace("{{ title }}", title)
        files["app/templates/index.html"] = index_html
        return files

    def generate_project(self, prompt: str) -> Dict[str, object]:
        """Generate a new project structure based on the provided prompt."""
        slug = slugify(prompt)
        project_name = slug or "webforge-project"

        ai_response = ""
        if self.enabled:
            try:
                ai_response = self._call_openai(
                    "Create a minimal full-stack FastAPI project with HTML, CSS, and JS.\n"
                    f"User prompt: {prompt}\n"
                    "Respond with a JSON object mapping file paths to file contents."
                )
            except Exception:
                ai_response = ""

        files: Dict[str, str] = {}
        if ai_response:
            try:
                parsed = json.loads(ai_response)
                if isinstance(parsed, dict):
                    files = {str(key): str(value) for key, value in parsed.items()}
            except Exception:
                files = {}

        if not files:
            files = self._fallback_project(prompt)

        summary = f"Project scaffold generated for: {prompt}"
        suffix = 1
        final_name = project_name
        while True:
            try:
                project_manager.create_project(final_name, files, summary=summary)
                break
            except FileExistsError:
                suffix += 1
                final_name = f"{project_name}-{suffix}"
        return {
            "name": final_name,
            "files": files,
            "summary": summary,
        }

    def chat(self, prompt: str) -> Dict[str, object]:
        """Return a chat response and optionally trigger project generation."""
        prompt_lower = prompt.lower().strip()
        should_generate = prompt_lower.startswith("create") or prompt_lower.startswith("build")

        generated_project: Optional[Dict[str, object]] = None
        if should_generate:
            generated_project = self.generate_project(prompt)
            message = (
                "Project generated successfully!"
                f"\nName: {generated_project['name']}"
                "\nFiles created: " + ", ".join(generated_project["files"].keys())
            )
        else:
            if self.enabled and self._client is not None:
                try:
                    message = self._call_openai(prompt)
                except Exception:
                    message = "AI response unavailable."
            else:
                message = (
                    "AI builder is running in offline mode. Use prompts starting with "
                    "'create' or 'build' to scaffold a project."
                )

        return {
            "message": message,
            "generated": generated_project,
        }


ai_builder = AIBuilder()
