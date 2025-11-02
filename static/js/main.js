const qs = (selector, scope = document) => scope.querySelector(selector);
const qsa = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

async function requestJSON(url, { method = 'POST', data, headers = {} } = {}) {
    const options = { method, headers: { ...headers } };
    if (data !== undefined) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(data);
    }
    const response = await fetch(url, options);
    if (!response.ok) {
        let detail = 'Request failed';
        try {
            const payload = await response.json();
            detail = payload.detail || detail;
        } catch (error) {
            // ignore
        }
        throw new Error(detail);
    }
    return response.json();
}

async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error('Request failed');
    return response.json();
}

const state = {
    sessionId: null,
    websocket: null,
    files: new Map(),
    currentProject: null,
    selectedFile: null,
};

function formatTimestamp(timestamp) {
    if (!timestamp) return '';
    try {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (error) {
        return '';
    }
}

function appendChatMessage(role, text) {
    const log = qs('#chat-log');
    if (!log) return;
    const bubble = document.createElement('div');
    bubble.className = `chat-log__bubble chat-log__bubble--${role}`;
    bubble.innerHTML = role === 'ai'
        ? `<strong>AI Builder</strong><p>${text}</p>`
        : `<strong>You</strong><p>${text}</p>`;
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}

function clearConsole() {
    const consoleLog = qs('#build-stream');
    if (!consoleLog) return;
    consoleLog.innerHTML = '<div class="console-log__entry console-log__entry--placeholder">Console cleared. Start a new build to see live progress.</div>';
}

function appendConsoleEntry({ type, title, message, content, meta }) {
    const consoleLog = qs('#build-stream');
    if (!consoleLog) return;
    if (consoleLog.firstElementChild && consoleLog.firstElementChild.classList.contains('console-log__entry--placeholder')) {
        consoleLog.innerHTML = '';
    }
    const entry = document.createElement('div');
    entry.className = 'console-log__entry';
    if (type === 'status') entry.classList.add('console-log__entry--status');
    if (type === 'error') entry.classList.add('console-log__entry--error');
    const header = document.createElement('header');
    header.innerHTML = `<span>${title || type}</span>${meta ? `<span>${meta}</span>` : ''}`;
    entry.appendChild(header);
    if (message) {
        const paragraph = document.createElement('p');
        paragraph.textContent = message;
        entry.appendChild(paragraph);
    }
    if (content) {
        const pre = document.createElement('pre');
        pre.textContent = content;
        entry.appendChild(pre);
    }
    consoleLog.appendChild(entry);
    consoleLog.scrollTop = consoleLog.scrollHeight;
}

function resetFileState() {
    state.files.clear();
    state.selectedFile = null;
    const tree = qs('#file-tree');
    if (tree) tree.innerHTML = '';
    const editor = qs('#file-editor');
    if (editor) {
        editor.value = '';
        editor.disabled = true;
    }
    const save = qs('#save-active-file');
    if (save) {
        save.disabled = true;
    }
    const label = qs('#current-file-name');
    if (label) label.textContent = 'Select a file to preview';
}

function updateActiveProject(project) {
    const label = qs('#active-project-label');
    const openLink = qs('#open-project-link');
    const runLink = qs('#run-project-link');
    state.currentProject = project;
    if (!project) {
        if (label) label.textContent = 'No active project yet.';
        if (openLink) openLink.hidden = true;
        if (runLink) runLink.hidden = true;
        return;
    }
    if (label) label.textContent = `Active project · ${project}`;
    if (openLink) {
        openLink.hidden = false;
        openLink.href = `/editor/${encodeURIComponent(project)}`;
    }
    if (runLink) {
        runLink.hidden = false;
        runLink.href = `/api/projects/run/${encodeURIComponent(project)}`;
    }
}

function renderFileTree() {
    const container = qs('#file-tree');
    if (!container) return;
    container.innerHTML = '';
    const paths = Array.from(state.files.keys()).sort();
    if (!paths.length) {
        const empty = document.createElement('li');
        empty.className = 'muted';
        empty.textContent = 'Files will appear here as they are generated.';
        container.appendChild(empty);
        return;
    }
    for (const path of paths) {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = path;
        button.dataset.path = path;
        if (state.selectedFile === path) button.classList.add('is-active');
        button.addEventListener('click', () => openFile(path));
        item.appendChild(button);
        container.appendChild(item);
    }
}

function openFile(path) {
    const content = state.files.get(path) || '';
    const editor = qs('#file-editor');
    const save = qs('#save-active-file');
    const label = qs('#current-file-name');
    state.selectedFile = path;
    if (editor) {
        editor.disabled = false;
        editor.value = content;
    }
    if (save) {
        save.disabled = false;
    }
    if (label) {
        label.textContent = path;
    }
    renderFileTree();
}

async function saveActiveFile() {
    if (!state.currentProject || !state.selectedFile) return;
    const editor = qs('#file-editor');
    if (!editor) return;
    const content = editor.value;
    try {
        await requestJSON(`/api/projects/save/${encodeURIComponent(state.currentProject)}/${encodeURIComponent(state.selectedFile)}`, {
            data: { content },
        });
        state.files.set(state.selectedFile, content);
        appendConsoleEntry({ type: 'status', title: 'File saved', message: `${state.selectedFile} updated.` });
    } catch (error) {
        appendConsoleEntry({ type: 'error', title: 'Save failed', message: error.message });
    }
}

async function refreshProjects() {
    try {
        const payload = await fetchJSON('/api/projects');
        if (Array.isArray(payload.projects)) {
            renderHomeProjects(payload.projects);
        }
    } catch (error) {
        console.error(error);
    }
}

function renderHomeProjects(projects) {
    const list = qs('#project-list');
    if (!list) return;
    list.innerHTML = '';
    if (!projects.length) {
        const empty = document.createElement('li');
        empty.className = 'empty-state';
        empty.textContent = 'No projects yet. Ask the builder to create something new.';
        list.appendChild(empty);
        return;
    }
    for (const project of projects) {
        const item = document.createElement('li');
        item.className = 'project-list__item';
        item.innerHTML = `
            <div>
                <strong>${project.name}</strong>
                ${project.summary ? `<p class="muted">${project.summary}</p>` : ''}
            </div>
            <div class="project-list__actions">
                <a class="ghost-button" href="/editor/${project.name}">Open</a>
                <a class="ghost-button" href="/api/projects/run/${project.name}" target="_blank">Play</a>
                <button class="ghost-button ghost-button--danger" data-action="delete" data-project="${project.name}">Delete</button>
            </div>
        `;
        list.appendChild(item);
    }
}

function bindProjectActions(scope = document) {
    scope.addEventListener('click', async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.dataset.action !== 'delete') return;
        const name = target.dataset.project;
        if (!name) return;
        if (!confirm(`Delete project "${name}"?`)) return;
        try {
            await fetch(`/api/projects/${encodeURIComponent(name)}`, { method: 'DELETE' });
            appendConsoleEntry({ type: 'status', title: 'Project deleted', message: `${name} removed.` });
            const card = target.closest('[data-project]');
            if (card) card.remove();
            const item = target.closest('.project-list__item');
            if (item) item.remove();
            await refreshProjects();
        } catch (error) {
            alert(error.message);
        }
    });
}

function handleBuildEvent(event) {
    const { type } = event;
    const timestamp = formatTimestamp(event.timestamp);
    if (type === 'status') {
        appendConsoleEntry({ type: 'status', title: event.stage || 'Status', message: event.message, meta: timestamp });
    } else if (type === 'plan') {
        updateActiveProject(event.project);
        appendConsoleEntry({
            type: 'status',
            title: 'Plan created',
            message: event.plan.summary,
            content: event.plan.steps.map((step, index) => `${index + 1}. ${step.title} — ${step.description}`).join('\n'),
            meta: timestamp,
        });
        appendChatMessage('ai', `Here's the plan for <strong>${event.project}</strong>. Watch the build console for progress.`);
    } else if (type === 'step' && event.status === 'start') {
        appendConsoleEntry({
            type: 'status',
            title: `Step ${event.index}: ${event.title}`,
            message: event.description,
            meta: timestamp,
        });
    } else if (type === 'step' && event.status === 'complete') {
        appendConsoleEntry({
            type: 'status',
            title: `Step ${event.index} complete`,
            message: event.title,
            meta: timestamp,
        });
    } else if (type === 'file') {
        state.files.set(event.path, event.content);
        renderFileTree();
        appendConsoleEntry({
            type: 'status',
            title: `File created (${event.path})`,
            content: event.content,
            meta: timestamp,
        });
    } else if (type === 'complete') {
        appendConsoleEntry({
            type: 'status',
            title: 'Build complete',
            message: `Project ${event.project} is ready.`,
            meta: timestamp,
        });
        appendChatMessage('ai', `The build for <strong>${event.project}</strong> is complete. Open the files below or keep iterating.`);
        refreshProjects();
    } else if (type === 'error') {
        appendConsoleEntry({ type: 'error', title: 'Build error', message: event.message, meta: timestamp });
        appendChatMessage('ai', `Something went wrong: ${event.message}`);
    }
}

function connectToSession(sessionId) {
    if (!sessionId) return;
    if (state.websocket) {
        state.websocket.close();
    }
    resetFileState();
    updateActiveProject(null);
    state.sessionId = sessionId;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/build/${sessionId}`);
    state.websocket = ws;
    ws.onmessage = (event) => {
        try {
            const payload = JSON.parse(event.data);
            handleBuildEvent(payload);
        } catch (error) {
            console.error('Failed to parse build event', error);
        }
    };
    ws.onopen = () => {
        appendConsoleEntry({ type: 'status', title: 'Session connected', message: 'Streaming build events.' });
    };
    ws.onerror = (event) => {
        console.error('WebSocket error', event);
    };
}

async function startBuild(message) {
    try {
        appendChatMessage('user', message);
        const payload = await requestJSON('/api/build', { data: { message } });
        appendConsoleEntry({ type: 'status', title: 'Build queued', message: 'Preparing live build session.' });
        connectToSession(payload.session.id);
    } catch (error) {
        appendConsoleEntry({ type: 'error', title: 'Unable to start build', message: error.message });
        appendChatMessage('ai', `I couldn't start that build: ${error.message}`);
    }
}

function initHome() {
    const form = qs('#chat-form');
    const input = qs('#chat-input');
    const clearButton = qs('#clear-console');
    const saveButton = qs('#save-active-file');
    const context = window.WEBFORGE_CONTEXT || {};
    if (Array.isArray(context.projects)) {
        renderHomeProjects(context.projects);
    }
    if (form && input) {
        form.addEventListener('submit', (event) => {
            event.preventDefault();
            const value = input.value.trim();
            if (!value) return;
            startBuild(value);
            input.value = '';
            input.focus();
        });
    }
    if (clearButton) {
        clearButton.addEventListener('click', clearConsole);
    }
    if (saveButton) {
        saveButton.addEventListener('click', saveActiveFile);
    }
    bindProjectActions();
}

function initProjectsPage() {
    bindProjectActions();
}

async function refreshModels() {
    try {
        const payload = await fetchJSON('/api/models');
        const grid = qs('#model-grid');
        if (!grid) return;
        grid.innerHTML = '';
        const models = Array.isArray(payload.models) ? payload.models : [];
        if (!models.length) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.textContent = 'No models uploaded yet. Add one to experiment with local intelligence.';
            grid.appendChild(empty);
            return;
        }
        for (const model of models) {
            const card = document.createElement('article');
            card.className = 'model-card';
            card.dataset.model = model.name;
            card.innerHTML = `
                <header>
                    <h2>${model.name}</h2>
                    ${payload.active === model.name ? '<span class="badge">Active</span>' : ''}
                </header>
                <p class="muted">${(model.type || '').toUpperCase()} · ${model.size}</p>
                <p class="muted">SHA256 · ${model.hash}</p>
                ${model.parameters ? `<p class="muted">Parameters · ${model.parameters}</p>` : ''}
                ${model.uploaded_at ? `<p class="muted">Uploaded ${model.uploaded_at}</p>` : ''}
                <footer class="model-card__actions">
                    <button class="ghost-button" data-action="activate" data-model="${model.name}">Use model</button>
                    <button class="ghost-button ghost-button--danger" data-action="delete-model" data-model="${model.name}">Delete</button>
                </footer>
            `;
            grid.appendChild(card);
        }
    } catch (error) {
        console.error(error);
    }
}

function initModelsPage() {
    const form = qs('#model-upload-form');
    const grid = qs('#model-grid');
    refreshModels();
    if (form) {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();
            const fileInput = qs('input[type="file"]', form);
            if (!fileInput || !fileInput.files || !fileInput.files.length) return;
            const formData = new FormData(form);
            try {
                await fetch('/api/models/upload', { method: 'POST', body: formData });
                fileInput.value = '';
                await refreshModels();
            } catch (error) {
                alert('Upload failed');
            }
        });
    }
    if (grid) {
        grid.addEventListener('click', async (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const action = target.dataset.action;
            const model = target.dataset.model;
            if (!action || !model) return;
            try {
                if (action === 'activate') {
                    await requestJSON(`/api/models/select/${encodeURIComponent(model)}`);
                } else if (action === 'delete-model') {
                    if (!confirm(`Delete model "${model}"?`)) return;
                    await fetch(`/api/models/delete/${encodeURIComponent(model)}`, { method: 'DELETE' });
                }
                await refreshModels();
            } catch (error) {
                alert(error.message);
            }
        });
    }
}

function initEditorPage() {
    const context = window.WEBFORGE_CONTEXT || {};
    const treeData = context.tree || {};
    const project = context.project;
    const tree = qs('#file-tree');
    const editor = qs('#editor');
    const saveButton = qs('#save-file');
    const currentFile = qs('#current-file');
    if (tree) {
        tree.innerHTML = '';
        const seen = new Set();
        const allFiles = [];
        Object.values(treeData).forEach((value) => {
            Object.values(value).forEach((path) => {
                if (!seen.has(path)) {
                    seen.add(path);
                    allFiles.push(path);
                }
            });
        });
        allFiles.sort();
        for (const path of allFiles) {
            const item = document.createElement('li');
            const button = document.createElement('button');
            button.type = 'button';
            button.textContent = path;
            button.addEventListener('click', async () => {
                try {
                    const payload = await fetchJSON(`/api/projects/${encodeURIComponent(project)}/file?path=${encodeURIComponent(path)}`);
                    if (editor) {
                        editor.disabled = false;
                        editor.value = payload.content;
                    }
                    if (currentFile) currentFile.textContent = path;
                    if (saveButton) saveButton.disabled = false;
                    saveButton.dataset.path = path;
                } catch (error) {
                    alert('Unable to load file');
                }
            });
            item.appendChild(button);
            tree.appendChild(item);
        }
    }
    if (saveButton && editor) {
        saveButton.addEventListener('click', async () => {
            const path = saveButton.dataset.path;
            if (!path) return;
            try {
                await requestJSON(`/api/projects/save/${encodeURIComponent(project)}/${encodeURIComponent(path)}`, {
                    data: { content: editor.value },
                });
            } catch (error) {
                alert(error.message);
            }
        });
    }
}

function boot() {
    const context = window.WEBFORGE_CONTEXT || {};
    const page = context.page || 'home';
    if (page === 'home') {
        initHome();
    } else if (page === 'projects') {
        initProjectsPage();
    } else if (page === 'models') {
        initModelsPage();
    } else if (page === 'editor') {
        initEditorPage();
    }
}

document.addEventListener('DOMContentLoaded', boot);
