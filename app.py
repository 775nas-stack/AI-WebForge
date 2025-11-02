"""Entry point for the AI-WebForge FastAPI application."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.exceptions import WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from core.db import init_db
from domains.chat.router import router as chat_router
from domains.models.router import router as models_router
from forge.ai_controller import ai_controller
from forge.build_stream import build_stream
from forge.local_ai import local_ai
from forge.model_lab import SUPPORTED_EXTENSIONS, model_lab
from forge.project_manager import project_manager
from forge.utils import MODELS_DIR, PROJECTS_DIR, get_active_model, set_active_model


class BuildRequest(BaseModel):
    """Payload schema for initiating a build session."""

    message: str


class ProjectCreationRequest(BaseModel):
    """Schema for manual project creation requests."""

    name: str
    files: Dict[str, str]
    summary: Optional[str] = None


class ProjectFilePayload(BaseModel):
    """Schema for saving a single project file."""

    content: str


class ModelCompareRequest(BaseModel):
    """Schema for comparing two stored models."""

    first: str
    second: str


app = FastAPI(title="AI-WebForge", description="Private AI-assisted web scaffold generator.")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def _startup() -> None:
    init_db()


app.include_router(chat_router)
app.include_router(models_router)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Render the chat dashboard."""
    projects = project_manager.list_projects()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "projects": projects},
    )


@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request) -> HTMLResponse:
    """Render the projects dashboard."""
    projects = project_manager.list_projects()
    return templates.TemplateResponse("projects.html", {"request": request, "projects": projects})


@app.get("/models", response_class=HTMLResponse)
async def models_page(request: Request) -> HTMLResponse:
    """Render the model management dashboard."""
    models = model_lab.list_models()
    active = get_active_model()
    return templates.TemplateResponse("models.html", {"request": request, "models": models, "active_model": active})


@app.get("/editor", response_class=HTMLResponse)
async def editor_landing(request: Request) -> HTMLResponse:
    """Display available projects for selection."""

    projects = project_manager.list_projects()
    return templates.TemplateResponse("editor_select.html", {"request": request, "projects": projects})


@app.get("/editor/{project}", response_class=HTMLResponse)
async def editor_page(request: Request, project: str) -> HTMLResponse:
    """Render the code editor for the selected project."""
    try:
        tree = project_manager.describe_project_tree(project)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "project": project,
            "tree": json.dumps(tree),
        },
    )


@app.post("/api/build")
async def api_build(payload: BuildRequest) -> Dict[str, object]:
    """Create a new build session and start streaming events."""

    prompt = payload.message.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    session = build_stream.create_session(prompt)
    build_stream.publish(
        session.id,
        {
            "type": "status",
            "stage": "queued",
            "message": "Build session created",
            "prompt": prompt,
        },
    )
    asyncio.create_task(ai_controller.run_build(session.id))

    return {"session": session.snapshot()}


@app.websocket("/ws/build/{session_id}")
async def ws_build(websocket: WebSocket, session_id: str) -> None:
    """Stream build events to the connected client."""

    session = build_stream.get_session(session_id)
    if session is None:
        await websocket.close(code=4404)
        return

    await websocket.accept()

    # replay existing history first
    for event in session.history:
        await websocket.send_json(event)

    while True:
        try:
            session.queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    try:
        async for event in build_stream.stream(session_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        return


@app.get("/api/projects")
async def api_list_projects() -> Dict[str, object]:
    """Return metadata about all projects."""
    return {"projects": project_manager.list_projects()}


@app.post("/api/projects")
async def api_create_project(request: ProjectCreationRequest) -> Dict[str, object]:
    """Create a new project from the provided file mapping."""
    try:
        project_manager.create_project(request.name, request.files, summary=request.summary or "")
    except FileExistsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "created"}


@app.delete("/api/projects/{project}")
async def api_delete_project(project: str) -> Dict[str, str]:
    """Delete a stored project."""
    try:
        project_manager.delete_project(project)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}


@app.get("/api/projects/{project}/files")
async def api_project_files(project: str) -> Dict[str, object]:
    """List files belonging to a project."""
    try:
        files = project_manager.list_project_files(project)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"files": files}


@app.get("/api/projects/{project}/file")
async def api_project_file(project: str, path: str) -> Dict[str, str]:
    """Return file content for a project file."""
    try:
        content = project_manager.read_file(project, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"path": path, "content": content}


@app.post("/api/projects/save/{project}/{file_path:path}")
async def api_save_project_file(project: str, file_path: str, payload: ProjectFilePayload) -> Dict[str, str]:
    """Persist a file update to disk."""

    try:
        project_manager.save_file(project, file_path, payload.content)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "saved"}


@app.get("/api/projects/{project}/manifest")
async def api_project_manifest(project: str) -> Dict[str, object]:
    """Return manifest metadata and history for a project."""

    manifest = project_manager.load_manifest(project)
    if not manifest:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return {"manifest": manifest}


@app.get("/api/projects/download/{project}")
async def api_download_project(project: str) -> StreamingResponse:
    """Return a zip archive for the specified project."""
    try:
        memory_file, filename = project_manager.zip_project(project)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(memory_file, media_type="application/zip", headers=headers)


@app.get("/api/projects/run/{project}", response_class=HTMLResponse)
async def api_run_project(project: str) -> HTMLResponse:
    """Return HTML markup to preview a generated project."""

    try:
        html = project_manager.preview_html(project)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HTMLResponse(html)


@app.post("/api/models/upload")
async def api_upload_model(file: UploadFile = File(...)) -> Dict[str, object]:
    """Upload a model file into local storage."""
    extension = Path(file.filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported model format: {extension}")

    data = await file.read()
    record = model_lab.save_model(file.filename, data)
    return {"model": record}


@app.get("/api/models")
async def api_list_models() -> Dict[str, object]:
    """Return metadata about stored models."""

    return {"models": model_lab.list_models(), "active": get_active_model()}


@app.post("/api/models/select/{name}")
async def api_select_model(name: str) -> Dict[str, str]:
    """Set the active model for the local inference engine."""

    previous = get_active_model()
    try:
        model_lab.select_model(name)
        local_ai.load_model(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - loader specific errors
        if previous:
            set_active_model(previous)
        else:
            set_active_model(None)
        local_ai.clear_model()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"active_model": name}


@app.delete("/api/models/delete/{name}")
async def api_delete_model(name: str) -> Dict[str, str]:
    """Delete a stored model."""

    try:
        model_lab.delete_model(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if get_active_model() is None:
        local_ai.clear_model()
    return {"status": "deleted"}


@app.post("/api/models/compare")
async def api_compare_models(payload: ModelCompareRequest) -> Dict[str, object]:
    """Compare two stored models."""
    try:
        comparison = model_lab.compare_models(payload.first, payload.second)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"comparison": comparison}


@app.post("/api/models/optimize")
async def api_optimize_models(payload: ModelCompareRequest) -> Dict[str, object]:
    """Run the placeholder optimisation routine."""
    try:
        merged_name = model_lab.optimize_model(payload.first, payload.second)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"merged_model": merged_name}


@app.get("/health")
async def healthcheck() -> Dict[str, str]:
    """Simple health endpoint for monitoring."""
    return {"status": "ok", "projects_dir": str(PROJECTS_DIR), "models_dir": str(MODELS_DIR)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8004, reload=False)
