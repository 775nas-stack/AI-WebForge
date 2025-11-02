"""Project management utilities for AI-WebForge."""
from __future__ import annotations

import io
import json
import shutil
import textwrap
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import PROJECTS_DIR, collect_directory_tree, slugify


class ProjectManager:
    """Handle project lifecycle operations such as creation and retrieval."""

    def __init__(self, base_dir: Path = PROJECTS_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, name: str) -> Path:
        return self.base_dir / name

    def _manifest_path(self, name: str) -> Path:
        return self._project_path(name) / "manifest.json"

    def load_manifest(self, name: str) -> Dict[str, Any]:
        """Return the stored manifest for a project, if it exists."""

        manifest_path = self._manifest_path(name)
        if not manifest_path.exists():
            return {}
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _write_manifest(self, name: str, manifest: Dict[str, Any]) -> None:
        manifest_path = self._manifest_path(name)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _default_manifest(
        self,
        name: str,
        summary: str,
        prompt: Optional[str] = None,
        stack: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a base manifest structure for a project."""

        now = datetime.utcnow().isoformat() + "Z"
        manifest: Dict[str, Any] = {
            "name": name,
            "summary": summary,
            "prompt": prompt or "",
            "created_at": now,
            "updated_at": now,
            "stack": stack or "unknown",
            "history": [],
        }
        return manifest

    def append_history(self, name: str, event: Dict[str, Any]) -> None:
        """Append an event to the project manifest history."""

        manifest = self.load_manifest(name) or self._default_manifest(name, "")
        history = manifest.setdefault("history", [])
        timestamp = datetime.utcnow().isoformat() + "Z"
        event.setdefault("timestamp", timestamp)
        history.append(event)
        manifest["updated_at"] = timestamp
        # keep history reasonable in size
        if len(history) > 200:
            manifest["history"] = history[-200:]
        self._write_manifest(name, manifest)

    def update_manifest(self, name: str, **fields: Any) -> None:
        """Update specific fields in the manifest."""

        manifest = self.load_manifest(name)
        if not manifest:
            manifest = self._default_manifest(name, fields.get("summary", ""))
        manifest.update(fields)
        manifest["updated_at"] = datetime.utcnow().isoformat() + "Z"
        self._write_manifest(name, manifest)

    def ensure_unique_name(self, desired: str) -> str:
        """Return a unique project name based on the desired slug."""

        if not desired:
            desired = "project"
        candidate = desired
        counter = 1
        while self._project_path(candidate).exists():
            counter += 1
            candidate = f"{desired}-{counter}"
        return candidate

    def list_projects(self) -> List[Dict[str, str]]:
        """Return metadata about all saved projects."""
        projects: List[Dict[str, str]] = []
        for path in sorted(self.base_dir.iterdir()):
            if path.is_dir():
                manifest = self.load_manifest(path.name)
                summary = manifest.get("summary", "") if manifest else ""
                projects.append(
                    {
                        "name": path.name,
                        "summary": summary,
                        "stack": manifest.get("stack") if manifest else None,
                        "created_at": manifest.get("created_at") if manifest else None,
                        "updated_at": manifest.get("updated_at") if manifest else None,
                    }
                )
        return projects

    def create_project(self, name: str, files: Dict[str, str], summary: str = "") -> Path:
        """Create a project directory populated with the provided files."""
        project_dir = self._project_path(name)
        if project_dir.exists():
            raise FileExistsError(f"Project '{name}' already exists.")

        project_dir.mkdir(parents=True, exist_ok=False)

        for relative_path, content in files.items():
            file_path = project_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        manifest = self._default_manifest(name, summary, stack="generated")
        self._write_manifest(name, manifest)

        return project_dir

    def initialize_project(
        self,
        name: str,
        summary: str,
        prompt: str,
        stack: str,
    ) -> Dict[str, Any]:
        """Create a new project directory and manifest ready for streaming builds."""

        project_dir = self._project_path(name)
        if project_dir.exists():
            raise FileExistsError(f"Project '{name}' already exists.")
        project_dir.mkdir(parents=True, exist_ok=False)
        manifest = self._default_manifest(name, summary, prompt=prompt, stack=stack)
        self._write_manifest(name, manifest)
        return manifest

    def create_from_prompt(self, prompt: str) -> Dict[str, object]:
        """Generate a scaffolded project using the provided natural language prompt."""

        slug = slugify(prompt)
        base_name = slug or f"project-{datetime.utcnow():%Y%m%d%H%M%S}"
        summary = f"Generated from prompt: {prompt.strip()[:140]}"
        files = self._render_scaffold(prompt)

        counter = 1
        project_name = base_name
        while True:
            try:
                self.create_project(project_name, files, summary=summary)
            except FileExistsError:
                counter += 1
                project_name = f"{base_name}-{counter}"
            else:
                self.update_manifest(project_name, prompt=prompt, stack="scaffold")
                break

        return {"name": project_name, "summary": summary, "files": files}

    def delete_project(self, name: str) -> None:
        """Delete the specified project."""
        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")
        shutil.rmtree(project_dir)

    def get_project_files(self, name: str) -> Dict[str, str]:
        """Return all file contents for a given project."""
        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")

        files: Dict[str, str] = {}
        for path in project_dir.rglob("*"):
            if path.is_file():
                files[str(path.relative_to(project_dir))] = path.read_text(encoding="utf-8", errors="ignore")
        return files

    def list_project_files(self, name: str) -> List[str]:
        """Return a list of files within the specified project."""
        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")
        return [str(path.relative_to(project_dir)) for path in project_dir.rglob("*") if path.is_file()]

    def read_file(self, name: str, relative_path: str) -> str:
        """Return the content of a single file within a project."""
        project_dir = self._project_path(name)
        file_path = project_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"File '{relative_path}' not found in project '{name}'.")
        return file_path.read_text(encoding="utf-8", errors="ignore")

    def save_file(self, name: str, relative_path: str, content: str) -> Path:
        """Persist new content to a file within the project."""
        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")
        file_path = project_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        self.update_manifest(name)
        return file_path

    def zip_project(self, name: str) -> Tuple[io.BytesIO, str]:
        """Return an in-memory zip archive for the given project."""
        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in project_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(project_dir)))
        memory_file.seek(0)
        return memory_file, f"{name}.zip"

    def describe_project_tree(self, name: str) -> Dict[str, Dict[str, str]]:
        """Return a mapping of directories to contained files for UI consumption."""
        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")
        return collect_directory_tree(project_dir)

    def preview_html(self, name: str) -> str:
        """Return HTML suitable for inline preview of a project."""

        project_dir = self._project_path(name)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project '{name}' not found.")

        candidates = [
            project_dir / "index.html",
            project_dir / "public" / "index.html",
            project_dir / "app" / "templates" / "index.html",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="ignore")

        raise FileNotFoundError("No previewable HTML file found in project.")

    # ------------------------------------------------------------------
    # scaffold helpers
    # ------------------------------------------------------------------
    def _render_scaffold(self, prompt: str) -> Dict[str, str]:
        """Return a structured project scaffold derived from the prompt."""

        title = prompt.strip().title() or "AI WebForge Project"
        slug = slugify(title)
        css_content = textwrap.dedent(
            f"""
            :root {{
                color-scheme: dark;
                font-family: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            }}

            body {{
                margin: 0;
                padding: 0;
                min-height: 100vh;
                background: radial-gradient(circle at top, #111927 0%, #05070a 100%);
                color: #f8fafc;
                display: flex;
                align-items: center;
                justify-content: center;
            }}

            .container {{
                width: min(960px, 90vw);
                padding: 3rem;
                background: rgba(15, 23, 42, 0.85);
                border-radius: 24px;
                border: 1px solid rgba(148, 163, 184, 0.12);
                box-shadow: 0 24px 60px -32px rgba(0, 0, 0, 0.75);
            }}

            .accent {{
                color: #00e19a;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.18em;
            }}

            button {{
                background: linear-gradient(120deg, #00e19a 0%, #11f0aa 100%);
                border: none;
                color: #03110d;
                padding: 0.85rem 1.6rem;
                font-weight: 600;
                border-radius: 999px;
                cursor: pointer;
                transition: transform 150ms ease, box-shadow 150ms ease;
            }}

            button:hover {{
                transform: translateY(-1px);
                box-shadow: 0 12px 20px -12px rgba(0, 225, 154, 0.55);
            }}
            """
        ).strip()

        html_content = textwrap.dedent(
            f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>{title}</title>
                <link rel="stylesheet" href="./static/style.css">
            </head>
            <body>
                <main class="container">
                    <p class="accent">{slug}</p>
                    <h1>{title}</h1>
                    <p>{prompt.strip() or 'A locally generated scaffold created by AI-WebForge.'}</p>
                    <button id="cta">Launch Experience</button>
                </main>
                <script src="./static/script.js" defer></script>
            </body>
            </html>
            """
        ).strip()

        js_content = textwrap.dedent(
            """
            document.addEventListener('DOMContentLoaded', () => {
                const button = document.querySelector('#cta');
                if (!button) return;
                button.addEventListener('click', () => {
                    button.textContent = 'Experience in progress…';
                    button.disabled = true;
                    setTimeout(() => {
                        button.textContent = 'Ready to Launch';
                        button.disabled = false;
                    }, 1200);
                });
            });
            """
        ).strip()

        api_content = textwrap.dedent(
            """
            '''Minimal FastAPI application for the generated project.'''
            from fastapi import FastAPI
            from fastapi.responses import HTMLResponse
            from pathlib import Path


            app = FastAPI(title="Generated App")


            @app.get("/", response_class=HTMLResponse)
            async def index() -> HTMLResponse:
                html_path = Path(__file__).resolve().parent.parent / "public" / "index.html"
                return HTMLResponse(html_path.read_text(encoding="utf-8"))
            """
        ).strip()

        readme_content = textwrap.dedent(
            f"""
            # {title}

            Generated locally by **AI-WebForge** on {datetime.utcnow():%Y-%m-%d %H:%M UTC}.

            ## Overview

            - Prompt: `{prompt.strip()}`
            - Framework: FastAPI + static frontend assets
            - Theme: Dark interface with neon green highlights

            ## Getting Started

            ```bash
            uvicorn app.main:app --reload
            ```

            Then open http://127.0.0.1:8000 to explore the generated experience.
            """
        ).strip()

        return {
            "public/index.html": html_content,
            "public/static/style.css": css_content,
            "public/static/script.js": js_content,
            "app/main.py": api_content,
            "README.md": readme_content,
        }


project_manager = ProjectManager()
