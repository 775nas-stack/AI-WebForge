# AI-WebForge

AI-WebForge is a private, FastAPI-powered workbench that lets you describe web or app ideas, generate full project scaffolds, manage the generated code, and curate AI models — all from a unified dark-themed interface.

## Features

- **Conversational builder** – describe what you need and optionally scaffold new FastAPI + frontend projects automatically.
- **Project manager** – inspect, download, edit, and delete locally stored scaffolds.
- **Built-in editor** – browse project files and edit them directly in the browser.
- **Model lab** – upload `.pt`, `.onnx`, `.gguf`, and `.safetensors` assets, review metadata, and run placeholder comparisons/optimisations.
- **Offline fallback** – when the OpenAI API key is unavailable, the app still generates a sensible starter template.

## Getting Started

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **Configure OpenAI (optional)**

   ```bash
   export OPENAI_API_KEY="sk-..."  # Windows: set OPENAI_API_KEY=sk-...
   ```

   Without a key the app operates in offline mode and uses a deterministic scaffold template.

3. **Run the application**

   ```bash
   python app.py
   ```

   Visit [http://127.0.0.1:8004](http://127.0.0.1:8004) to access the interface.

## Project Structure

```
app.py
forge/
├── ai_builder.py
├── model_lab.py
├── project_manager.py
└── utils.py
static/
├── css/style.css
└── js/main.js
templates/
├── base.html
├── editor.html
├── index.html
├── models.html
└── projects.html
data/
├── models/
└── projects/
```

## Data Storage

- Generated projects live under `data/projects/<project-name>`.
- Uploaded models live under `data/models/<file-name>` and include JSON metadata.
- Everything is local; no external database is required.

## API Overview

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/chat` | POST | Chat with the AI assistant and auto-generate projects when prompted. |
| `/api/projects` | GET/POST | List or manually create projects. |
| `/api/projects/{name}` | DELETE | Remove a stored project. |
| `/api/projects/{name}/files` | GET | List files within a project. |
| `/api/projects/{name}/file` | GET | Fetch the contents of a project file. |
| `/api/projects/save` | POST | Save an updated project file. |
| `/api/projects/download/{name}` | GET | Download a project as a ZIP archive. |
| `/api/models/upload` | POST | Upload a model file. |
| `/api/models` | GET | List uploaded models. |
| `/api/models/compare` | POST | Compare two stored models. |
| `/api/models/optimize` | POST | Run the placeholder optimisation routine. |

## Notes

- The UI uses a consistent dark aesthetic with a green accent (`#00E19A`).
- The editor relies on plain `<textarea>` to keep dependencies light; feel free to integrate Monaco or CodeMirror later.
- The `forge/ai_builder.py` module handles OpenAI interactions and gracefully degrades when the API is unavailable.

Enjoy forging new ideas!
