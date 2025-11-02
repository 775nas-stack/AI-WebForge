const qs = (selector, scope = document) => scope.querySelector(selector);
const qsa = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

function appendChatMessage(role, text) {
    const log = qs('#chat-log');
    if (!log) return;
    const bubble = document.createElement('div');
    bubble.className = `wf-chat__message wf-chat__message--${role}`;
    bubble.textContent = String(text || '').trim();
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
}

async function postJSON(url, data) {
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!response.ok) {
        throw new Error((await response.json()).detail || 'Request failed');
    }
    return response.json();
}

async function deleteProject(name) {
    const response = await fetch(`/api/projects/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!response.ok) {
        throw new Error('Failed to delete project');
    }
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
                <a class="wf-link" href="/editor/${project.name}">Open</a>
                <a class="wf-link" href="/api/projects/download/${project.name}">Download</a>
                <button class="wf-link wf-link--danger" data-action="delete" data-project="${project.name}">Delete</button>
            </div>
        `;
        container.appendChild(li);
    }
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
            const { response, projects } = await postJSON('/api/chat', { message });
            appendChatMessage('ai', response.message || 'No response received.');
            if (response.generated) {
                appendChatMessage('ai', `Generated project: ${response.generated.name}`);
            }
            if (Array.isArray(projects)) {
                renderProjectList(projects);
            }
        } catch (error) {
            appendChatMessage('ai', `Error: ${error.message}`);
        } finally {
            if (submitButton) submitButton.disabled = false;
        }
    });
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
            const parentItem = target.closest('[data-project]');
            if (parentItem) parentItem.remove();
            const list = target.closest('#project-list');
            if (list && !list.querySelector('.wf-list__item')) {
                renderProjectList([]);
            }
        } catch (error) {
            alert(error.message);
        }
    });
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
                body: formData
            });
            if (!response.ok) {
                const payload = await response.json();
                throw new Error(payload.detail || 'Upload failed');
            }
            const { model } = await response.json();
            addModelCard(model);
            form.reset();
        } catch (error) {
            alert(error.message);
        }
    });
}

function addModelCard(model) {
    const grid = qs('#model-grid');
    const list = qs('#model-list');
    if (grid) {
        const card = document.createElement('article');
        card.className = 'wf-card';
        card.innerHTML = `
            <h2>${model.name}</h2>
            <p class="wf-muted">${model.type?.toUpperCase?.() || model.type} · ${model.size}</p>
            <p class="wf-hash">SHA256: ${model.hash}</p>
        `;
        const emptyState = grid.querySelector('.wf-empty');
        if (emptyState) emptyState.remove();
        grid.prepend(card);
    }
    if (list) {
        const item = document.createElement('li');
        item.className = 'wf-list__item';
        item.innerHTML = `
            <div>
                <strong>${model.name}</strong>
                <p class="wf-muted">${model.type?.toUpperCase?.() || model.type} · ${model.size}</p>
            </div>
        `;
        const emptyState = list.querySelector('.wf-empty');
        if (emptyState) emptyState.remove();
        list.prepend(item);
    }
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
            await postJSON('/api/projects/save', {
                project: context.project,
                path: activePath,
                content: editor.value
            });
            dirty = false;
            currentFile.textContent = activePath;
        } catch (error) {
            alert(error.message);
        }
    });
}

function init() {
    bindChat();
    bindProjectDeletion(document);
    bindModelUpload();
    bindEditor();
}

document.addEventListener('DOMContentLoaded', init);
