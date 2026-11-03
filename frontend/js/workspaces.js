/**
 * SciGraph RAG Workspace Manager
 * Multi-workspace interface, collection routing, and honest architecture representation.
 */
const WorkspaceManager = {
  workspaces: [],
  activeWorkspaceId: 'ws-default',

  async init() {
    this.bindModals();
    await this.refresh();
  },

  async refresh() {
    try {
      this.workspaces = await API.getWorkspaces();
      if (!this.workspaces || this.workspaces.length === 0) {
        this.workspaces = [
          {
            id: 'ws-default',
            name: 'General Science Workspace',
            description: 'Primary workspace for multimodal scientific papers, cross-disciplinary graph analysis, and AI intelligence synthesis.',
            created_at: 1704067200,
            is_default: true,
            documents: [],
            tags: ['scientific-research', 'multimodal'],
            storage_mode: 'unified_global_graph',
          }
        ];
      }
      this.render();
    } catch (e) {
      console.error('Failed to load workspaces:', e);
    }
  },

  render() {
    const grid = document.getElementById('workspaces-grid-container');
    if (!grid) return;

    grid.innerHTML = this.workspaces.map(ws => {
      const isDefault = ws.is_default || ws.id === 'ws-default';
      const dateStr = new Date((ws.created_at || Date.now()) * 1000).toLocaleDateString();
      const docCount = (ws.documents || []).length;

      return `
        <div class="card" style="display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px;">
              <span class="badge ${isDefault ? 'badge-info' : 'badge-neutral'}">${isDefault ? 'Active Default' : 'Custom Workspace'}</span>
              <span style="font-size: 11px; color: var(--text-muted); font-family: var(--font-mono);">${dateStr}</span>
            </div>
            <h3 style="font-size: var(--text-md); font-weight: 600; color: var(--text-primary); margin-bottom: 6px;">
              ${escapeHtml(ws.name)}
            </h3>
            <p style="font-size: var(--text-xs); color: var(--text-secondary); line-height: 1.5; margin-bottom: 12px;">
              ${escapeHtml(ws.description || 'No description provided.')}
            </p>
            <div style="display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 12px;">
              ${(ws.tags || []).map(t => `<span class="badge badge-neutral" style="font-size: 10px;">#${escapeHtml(t)}</span>`).join('')}
            </div>
          </div>

          <div style="padding-top: 12px; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; justify-content: space-between;">
            <span style="font-size: 12px; color: var(--text-muted);">
              <strong>${docCount}</strong> papers mapped
            </span>
            <div style="display: flex; gap: 6px;">
              <button class="btn btn-sm btn-primary" onclick="WorkspaceManager.openWorkspace('${ws.id}')">Open</button>
              ${!isDefault ? `<button class="btn btn-sm btn-danger-outline" onclick="WorkspaceManager.deleteWorkspace('${ws.id}')">Delete</button>` : ''}
            </div>
          </div>
        </div>
      `;
    }).join('');
  },

  bindModals() {
    const openBtn = document.getElementById('btn-open-new-rag-modal');
    const modal = document.getElementById('modal-new-rag');
    const closeBtn = document.getElementById('close-new-rag');
    const cancelBtn = document.getElementById('cancel-new-rag');
    const createBtn = document.getElementById('create-new-rag-btn');

    if (!modal) return;

    const open = () => modal.classList.add('open');
    const close = () => modal.classList.remove('open');

    if (openBtn) openBtn.addEventListener('click', open);
    if (closeBtn) closeBtn.addEventListener('click', close);
    if (cancelBtn) cancelBtn.addEventListener('click', close);

    if (createBtn) {
      createBtn.addEventListener('click', async () => {
        const nameInput = document.getElementById('input-new-rag-name');
        const descInput = document.getElementById('input-new-rag-desc');
        const tagsInput = document.getElementById('input-new-rag-tags');

        const name = nameInput.value.trim();
        const desc = descInput.value.trim();
        const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);

        if (!name) {
          Toast.show('Please enter a workspace name', 'error');
          return;
        }

        createBtn.disabled = true;
        createBtn.textContent = 'Creating...';

        try {
          await API.createWorkspace({ name, description: desc, tags });
          Toast.show(`Workspace "${name}" created successfully!`, 'success');
          nameInput.value = '';
          descInput.value = '';
          tagsInput.value = '';
          close();
          await this.refresh();
        } catch (err) {
          Toast.show('Failed to create workspace: ' + err.message, 'error');
        } finally {
          createBtn.disabled = false;
          createBtn.textContent = 'Create Workspace';
        }
      });
    }
  },

  openWorkspace(id) {
    this.activeWorkspaceId = id;
    const ws = this.workspaces.find(w => w.id === id);
    Toast.show(`Switched to workspace "${ws ? ws.name : id}"`, 'info');
    NavManager.switchTab('library');
  },

  async deleteWorkspace(id) {
    if (confirm('Are you sure you want to delete this RAG workspace?')) {
      try {
        await API.deleteWorkspace(id);
        Toast.show('Workspace deleted', 'success');
        await this.refresh();
      } catch (e) {
        Toast.show('Failed to delete workspace: ' + e.message, 'error');
      }
    }
  }
};
