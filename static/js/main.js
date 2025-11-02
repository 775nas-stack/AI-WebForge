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
            // ignore JSON parse errors
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

function appendChatMessage(role, text) {
    const log = qs('#chat-log');
    if (!log) return;
    const bubble = document.createElement('div');
    bubble.className = `wf-chat__message wf-chat__message--${role}`;
    bubble.textContent = String(text || '').trim();
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}

function renderProjectList(projects) {
    const container = qs('#project-list');
    if (!container) return;
    container.innerHTML = '';
    if (!projects.length) {
        const empty = document.createElement('li');
        empty.className = 'wf-empty';
        empty.textContent = 'No projects yet. Start by chatting with the builder.';
        container.appendChild(empty);
        return;
    }

    for (const project of projects) {
        const li = document.createElement('li');
        li.className = 'wf-list__item';
        li.dataset.project = project.name;
        li.innerHTML = `
            <div>
                <strong>${project.name}</strong>
                ${project.summary ? `<p class="wf-muted">${project.summary}</p>` : ''}
            </div>
            <div class="wf-actions">
                <a class="wf-link" href="/api/projects/run/${project.name}" target="_blank">Preview</a>
                <a class="wf-link" href="/editor/${project.name}">Open</a>
                <a class="wf-link" href="/api/projects/download/${project.name}">Download</a>
                <button class="wf-link wf-link--danger" data-action="delete" data-project="${project.name}">Delete</button>
            </div>
        `;
        container.appendChild(li);
    }
}

async function deleteProject(name) {
    await fetch(`/api/projects/${encodeURIComponent(name)}`, { method: 'DELETE' });
}

function bindProjectDeletion(scope = document) {
    scope.addEventListener('click', async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.dataset.action !== 'delete') return;
        const name = target.dataset.project;
        if (!name) return;
        if (!confirm(`Delete project "${name}"?`)) return;
        try {
            await deleteProject(name);
            const projectItem = target.closest('[data-project]');
            if (projectItem) projectItem.remove();
            const card = target.closest('.wf-card');
            if (card) card.remove();
            await refreshProjects();
        } catch (error) {
            alert(error.message);
        }
    });
}

async function refreshProjects() {
    try {
        const payload = await fetchJSON('/api/projects');
        if (Array.isArray(payload.projects)) {
            renderProjectList(payload.projects);
        }
    } catch (error) {
        console.error(error);
    }
}

function renderModelSummary(models, active) {
    const list = qs('#model-list');
    if (!list) return;
    list.innerHTML = '';
    if (!models.length) {
        const empty = document.createElement('li');
        empty.className = 'wf-empty';
        empty.textContent = 'No models uploaded yet.';
        list.appendChild(empty);
        return;
    }
    for (const model of models) {
        const item = document.createElement('li');
        item.className = 'wf-list__item';
        item.innerHTML = `
            <div>
                <strong>${model.name}</strong>
                <p class="wf-muted">${(model.type || '').toUpperCase()} · ${model.size}${model.name === active ? ' · Active' : ''}</p>
            </div>
        `;
        list.appendChild(item);
    }
}

function renderModelGrid(models, active) {
    const grid = qs('#model-grid');
    if (!grid) return;
    grid.dataset.active = active || '';
    grid.innerHTML = '';
    if (!models.length) {
        const empty = document.createElement('div');
        empty.className = 'wf-empty';
        empty.textContent = 'No models uploaded yet. Upload your first model to begin.';
        grid.appendChild(empty);
        return;
    }

    for (const model of models) {
        const card = document.createElement('article');
        card.className = 'wf-card';
        card.dataset.model = model.name;
        const isActive = model.name === active;
        card.innerHTML = `
            <header class="wf-card__header">
                <h2>${model.name}</h2>
                ${isActive ? '<span class="wf-badge">Active</span>' : ''}
            </header>
            <p class="wf-muted">${(model.type || '').toUpperCase()} · ${model.size}</p>
            <p class="wf-hash">SHA256: ${model.hash}</p>
            ${model.parameters ? `<p class="wf-muted">Parameters: ${model.parameters}</p>` : ''}
            ${model.uploaded_at ? `<p class="wf-muted">Uploaded ${model.uploaded_at}</p>` : ''}
            <div class="wf-card__actions">
                <button class="wf-link" data-action="activate" data-model="${model.name}">Use model</button>
                <button class="wf-link wf-link--danger" data-action="delete-model" data-model="${model.name}">Delete</button>
            </div>
        `;
        grid.appendChild(card);
    }
}

async function refreshModels() {
    try {
        const payload = await fetchJSON('/api/models');
        const models = Array.isArray(payload.models) ? payload.models : [];
        const active = payload.active || null;
        renderModelSummary(models, active);
        renderModelGrid(models, active);
    } catch (error) {
        console.error(error);
    }
}

async function handleModelAction(event) {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.dataset.action;
    if (!action) return;
    const name = target.dataset.model;
    if (!name) return;

    try {
        if (action === 'activate') {
            await requestJSON(`/api/models/select/${encodeURIComponent(name)}`);
            appendChatMessage('ai', `Model "${name}" activated.`);
        } else if (action === 'delete-model') {
            if (!confirm(`Delete model "${name}"?`)) return;
            await fetch(`/api/models/delete/${encodeURIComponent(name)}`, { method: 'DELETE' });
        }
        await refreshModels();
    } catch (error) {
        alert(error.message);
    }
}

function bindModelUpload() {
    const form = qs('#model-upload-form');
    if (!form) return;
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        try {
            const response = await fetch('/api/models/upload', {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.detail || 'Upload failed');
            }
            await response.json();
            form.reset();
            await refreshModels();
        } catch (error) {
            alert(error.message);
        }
    });
}

function bindModelActions() {
    document.addEventListener('click', handleModelAction);
}

function splitPath(path) {
    return path.split('/').map((segment) => encodeURIComponent(segment)).join('/');
}

function bindEditor() {
    const context = window.WEBFORGE_CONTEXT;
    if (!context || context.page !== 'editor') return;
    buildFileTree(context.tree || {});

    const editor = qs('#editor');
    const saveButton = qs('#save-file');
    const currentFile = qs('#current-file');

    let activePath = null;
    let dirty = false;

    async function loadFile(path) {
        const response = await fetch(`/api/projects/${encodeURIComponent(context.project)}/file?path=${encodeURIComponent(path)}`);
        if (!response.ok) throw new Error('Failed to load file');
        const payload = await response.json();
        editor.value = payload.content;
        editor.disabled = false;
        saveButton.disabled = false;
        currentFile.textContent = path;
        activePath = path;
        dirty = false;
    }

    qs('#file-tree').addEventListener('click', async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        const path = target.dataset.path;
        if (!path) return;
        qsa('.wf-tree__item').forEach((item) => item.classList.remove('wf-tree__item--active'));
        target.classList.add('wf-tree__item--active');
        try {
            await loadFile(path);
        } catch (error) {
            alert(error.message);
        }
    });

    editor.addEventListener('input', () => {
        if (!dirty) {
            dirty = true;
            if (currentFile && !currentFile.textContent.endsWith('*')) {
                currentFile.textContent += ' *';
            }
        }
    });

    saveButton.addEventListener('click', async () => {
        if (!activePath) return;
        try {
            await requestJSON(`/api/projects/save/${encodeURIComponent(context.project)}/${splitPath(activePath)}`, {
                data: { content: editor.value },
            });
            dirty = false;
            currentFile.textContent = activePath;
        } catch (error) {
            alert(error.message);
        }
    });
}

function buildFileTree(tree) {
    const fileTree = qs('#file-tree');
    if (!fileTree) return;
    fileTree.innerHTML = '';

    Object.entries(tree).forEach(([directory, files]) => {
        const dirLabel = document.createElement('li');
        dirLabel.textContent = directory === '.' ? 'root' : directory;
        dirLabel.className = 'wf-tree__label';
        fileTree.appendChild(dirLabel);
        Object.values(files).forEach((path) => {
            const fileItem = document.createElement('li');
            fileItem.className = 'wf-tree__item';
            fileItem.dataset.path = path;
            fileItem.textContent = path;
            fileTree.appendChild(fileItem);
        });
    });
}

function bindChat() {
    const form = qs('#chat-form');
    const input = qs('#chat-input');
    if (!form || !input) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const message = input.value.trim();
        if (!message) return;
        input.value = '';
        appendChatMessage('user', message);
        const submitButton = qs('.wf-button', form);
        try {
            if (submitButton) submitButton.disabled = true;
            const payload = await requestJSON('/api/chat', { data: { message } });
            appendChatMessage('ai', payload.response?.message || 'No response received.');
            if (payload.response?.generated) {
                appendChatMessage('ai', `Generated project: ${payload.response.generated.name}`);
            }
            if (Array.isArray(payload.projects)) {
                renderProjectList(payload.projects);
            }
        } catch (error) {
            appendChatMessage('ai', `Error: ${error.message}`);
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
}

async function initialise() {
    bindChat();
    bindProjectDeletion(document);
    bindModelUpload();
    bindModelActions();
    bindEditor();

    const context = window.WEBFORGE_CONTEXT || {};
    if (context.page === 'models') {
        await refreshModels();
    } else {
        await refreshProjects();
        await refreshModels();
    }
}

document.addEventListener('DOMContentLoaded', initialise);
