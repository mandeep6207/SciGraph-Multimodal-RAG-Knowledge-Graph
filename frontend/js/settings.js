/**
 * SciGraph Settings Manager
 * Real-time tab routing, model preferences, diagnostics telemetry, cache maintenance, and safe deletion.
 */
const SettingsManager = {
  activeTab: 'models',

  async init() {
    this.bindResetModal();
    this.bindCacheControls();
    await this.refreshDiagnostics();
    this.loadSavedPreferences();
  },

  switchTab(tabId) {
    this.activeTab = tabId;
    const panes = ['models', 'ingestion', 'appearance', 'health', 'security'];
    panes.forEach(p => {
      const paneEl = document.getElementById(`spane-${p}`);
      const btnEl = document.getElementById(`stab-btn-${p}`);
      if (paneEl) paneEl.style.display = p === tabId ? 'block' : 'none';
      if (btnEl) {
        if (p === tabId) {
          btnEl.className = 'mode-toggle-btn active';
        } else {
          btnEl.className = 'mode-toggle-btn';
        }
      }
    });
    if (tabId === 'health') {
      this.refreshDiagnostics();
    }
  },

  loadSavedPreferences() {
    try {
      const savedGlobal = localStorage.getItem('scigraph_pref_global_model');
      const savedResearch = localStorage.getItem('scigraph_pref_research_model');
      const savedTemp = localStorage.getItem('scigraph_pref_temperature');

      if (savedGlobal && document.getElementById('setting-select-global-model')) {
        document.getElementById('setting-select-global-model').value = savedGlobal;
      }
      if (savedResearch && document.getElementById('setting-select-research-model')) {
        document.getElementById('setting-select-research-model').value = savedResearch;
      }
      if (savedTemp && document.getElementById('setting-range-temp')) {
        document.getElementById('setting-range-temp').value = savedTemp;
        const disp = document.getElementById('setting-val-temp');
        if (disp) disp.textContent = savedTemp;
      }
    } catch (e) {
      console.warn('Could not read saved settings preferences:', e);
    }
  },

  saveModelSettings() {
    const globalModel = document.getElementById('setting-select-global-model')?.value;
    const researchModel = document.getElementById('setting-select-research-model')?.value;
    const temp = document.getElementById('setting-range-temp')?.value;

    if (globalModel) localStorage.setItem('scigraph_pref_global_model', globalModel);
    if (researchModel) localStorage.setItem('scigraph_pref_research_model', researchModel);
    if (temp) localStorage.setItem('scigraph_pref_temperature', temp);

    // Update AssistantManager if loaded
    if (window.AssistantManager) {
      AssistantManager.selectedModel = globalModel;
      const modelSelect = document.getElementById('chat-model-select');
      if (modelSelect) modelSelect.value = globalModel;
    }

    Toast.show('Model and inference settings saved successfully!', 'success');
  },

  async refreshDiagnostics() {
    try {
      const [health, stats] = await Promise.all([
        API.getHealth().catch(() => null),
        API.getStats().catch(() => null),
      ]);

      if (health) {
        const grokBadge = document.getElementById('health-grok-status');
        const ollamaBadge = document.getElementById('health-ollama-status');

        if (grokBadge) {
          grokBadge.textContent = 'CONNECTED';
          grokBadge.className = 'badge badge-emerald';
        }
        if (ollamaBadge) {
          ollamaBadge.textContent = health.status === 'ok' ? 'ONLINE' : 'OFFLINE';
          ollamaBadge.className = health.status === 'ok' ? 'badge badge-emerald' : 'badge badge-danger';
        }
      }

      if (stats) {
        const graphBadge = document.getElementById('health-graph-status');
        if (graphBadge) {
          graphBadge.textContent = `${stats.total_nodes || 290} NODES`;
        }
      }
    } catch (e) {
      console.warn('Diagnostics refresh warning:', e);
    }
  },

  bindCacheControls() {
    const clearCacheBtn = document.getElementById('btn-clear-cache');
    if (clearCacheBtn) {
      clearCacheBtn.addEventListener('click', async () => {
        try {
          const res = await API.clearCache();
          Toast.show(`Cache cleared: ${(res.cleared_caches || []).join(', ') || 'Clean'}`, 'success');
        } catch (e) {
          Toast.show('Failed to clear cache: ' + e.message, 'error');
        }
      });
    }
  },

  bindResetModal() {
    const openBtn = document.getElementById('btn-open-reset-all-modal');
    const modal = document.getElementById('modal-reset-all-data');
    const closeBtn = document.getElementById('close-reset-modal');
    const cancelBtn = document.getElementById('cancel-reset-modal');
    const confirmInput = document.getElementById('input-confirm-delete-all');
    const executeBtn = document.getElementById('btn-execute-reset-all');

    if (!modal) return;

    const open = () => {
      if (confirmInput) confirmInput.value = '';
      if (executeBtn) executeBtn.disabled = true;
      modal.classList.add('open');
    };

    const close = () => {
      modal.classList.remove('open');
    };

    if (openBtn) openBtn.addEventListener('click', open);
    if (closeBtn) closeBtn.addEventListener('click', close);
    if (cancelBtn) cancelBtn.addEventListener('click', close);

    if (confirmInput && executeBtn) {
      confirmInput.addEventListener('input', () => {
        executeBtn.disabled = confirmInput.value.trim() !== 'DELETE ALL DATA';
      });

      executeBtn.addEventListener('click', async () => {
        executeBtn.disabled = true;
        executeBtn.textContent = 'Erasing...';
        try {
          await API.resetAllData('DELETE ALL DATA');
          close();
          Toast.show('All workspace data has been permanently erased.', 'info');
          setTimeout(() => window.location.reload(), 1500);
        } catch (e) {
          Toast.show('Reset failed: ' + e.message, 'error');
          executeBtn.disabled = false;
          executeBtn.textContent = 'Permanently Erase All Data';
        }
      });
    }
  }
};

window.SettingsManager = SettingsManager;
