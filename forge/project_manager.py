"""Project management utilities for AI-WebForge."""
from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from .utils import PROJECTS_DIR, collect_directory_tree


class ProjectManager:
    """Handle project lifecycle operations such as creation and retrieval."""

    def __init__(self, base_dir: Path = PROJECTS_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, name: str) -> Path:
        return self.base_dir / name

    def list_projects(self) -> List[Dict[str, str]]:
        """Return metadata about all saved projects."""
        projects: List[Dict[str, str]] = []
        for path in sorted(self.base_dir.iterdir()):
            if path.is_dir():
                manifest = path / "manifest.json"
                summary = ""
                if manifest.exists():
                    try:
                        summary = json.loads(manifest.read_text()).get("summary", "")
                    except json.JSONDecodeError:
                        summary = ""
                projects.append({
                    "name": path.name,
                    "summary": summary,
                })
        return projects

    def create_project(self, name: str, files: Dict[str, str], summary: str = "") -> Path:
        """Create a project directory populated with the provided files."""
        project_dir = self._project_path(name)
        if project_dir.exists():
            raise FileExistsError(f"Project '{name}' already exists.")

        for relative_path, content in files.items():
            file_path = project_dir / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        if summary:
            (project_dir / "manifest.json").write_text(json.dumps({"summary": summary}, indent=2), encoding="utf-8")

        return project_dir

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


project_manager = ProjectManager()
