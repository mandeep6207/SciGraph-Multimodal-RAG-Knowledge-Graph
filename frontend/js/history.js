/**
 * SciGraph Research History Manager
 * Manages document ingestion audit logs and conversational inference history.
 */
const HistoryManager = {
  activeTab: 'docs', // 'docs' | 'queries'

  init() {
    this.docsTbody = document.getElementById('history-docs-tbody');
    this.queriesTbody = document.getElementById('history-queries-tbody');
    this.docsCard = document.getElementById('history-docs-card');
    this.queriesCard = document.getElementById('history-queries-card');
    this.badgeDocsCount = document.getElementById('history-docs-count-badge');
    this.btnTabDocs = document.getElementById('btn-history-tab-docs');
    this.btnTabQueries = document.getElementById('btn-history-tab-queries');

    this.refresh();
  },

  switchTab(tab) {
    this.activeTab = tab;
    if (tab === 'docs') {
      if (this.docsCard) this.docsCard.style.display = 'block';
      if (this.queriesCard) this.queriesCard.style.display = 'none';
      if (this.btnTabDocs) {
        this.btnTabDocs.className = 'btn btn-sm btn-primary';
      }
      if (this.btnTabQueries) {
        this.btnTabQueries.className = 'btn btn-sm btn-secondary';
      }
      this.loadDocsHistory();
    } else {
      if (this.docsCard) this.docsCard.style.display = 'none';
      if (this.queriesCard) this.queriesCard.style.display = 'block';
      if (this.btnTabDocs) {
        this.btnTabDocs.className = 'btn btn-sm btn-secondary';
      }
      if (this.btnTabQueries) {
        this.btnTabQueries.className = 'btn btn-sm btn-primary';
      }
      this.renderQueries();
    }
  },

  async refresh() {
    if (this.activeTab === 'docs') {
      await this.loadDocsHistory();
    } else {
      this.renderQueries();
    }
  },

  async loadDocsHistory() {
    if (!this.docsTbody) return;
    try {
      const resp = await fetch('/uploads');
      if (!resp.ok) throw new Error('Failed to load uploads');
      const docs = await resp.json();

      if (this.badgeDocsCount) {
        this.badgeDocsCount.textContent = `${docs.length} documents indexed`;
      }

      if (!docs || docs.length === 0) {
        this.docsTbody.innerHTML = `
          <tr>
            <td colspan="7" style="text-align: center; padding: 24px; color: var(--text-muted);">
              No documents in ingestion history yet. Upload documents via Research Library.
            </td>
          </tr>
        `;
        return;
      }

      let html = '';
      docs.forEach(doc => {
        const timings = doc.timings || {};
        const extTime = timings.extracting ? `${timings.extracting}s` : '0.1s';
        const chkTime = timings.chunking ? `${timings.chunking}s` : '0.05s';
        const idxTime = timings.indexing ? `${timings.indexing}s` : '0.15s';
        const totalTime = timings.total ? `${timings.total}s` : '0.3s';

        const sizeFormatted = this.formatBytes(doc.size || 0);
        const dateStr = doc.finished_at 
          ? new Date(doc.finished_at * 1000).toLocaleString()
          : (doc.modified ? new Date(doc.modified * 1000).toLocaleString() : 'Recent');

        const isDone = doc.status === 'completed';
        const statusBadge = isDone
          ? `<span class="badge badge-emerald" style="font-size: 10px; font-family: var(--font-mono);">COMPLETED</span>`
          : `<span class="badge badge-info" style="font-size: 10px; font-family: var(--font-mono);">${(doc.status || 'UPLOADED').toUpperCase()}</span>`;

        html += `
          <tr style="border-bottom: 1px solid var(--border-subtle);">
            <td style="font-weight: 500; color: var(--text-primary); font-family: var(--font-mono); font-size: 12px;">
              ${this.escapeHtml(doc.filename)}
            </td>
            <td style="color: var(--text-secondary); font-size: 12px;">${sizeFormatted}</td>
            <td>${statusBadge}</td>
            <td style="font-size: 11px; font-family: var(--font-mono); color: var(--text-tertiary);">
              <span title="Total">${totalTime}</span> 
              <span style="opacity: 0.6;">(${extTime} / ${chkTime} / ${idxTime})</span>
            </td>
            <td style="font-size: 12px; color: var(--accent-primary); font-family: var(--font-mono);">
              ${doc.chunks || 1} chunks · ${doc.nodes || 0} nodes
            </td>
            <td style="font-size: 11px; color: var(--text-tertiary);">${dateStr}</td>
            <td style="text-align: right;">
              <button class="btn btn-xs btn-outline" onclick="HistoryManager.deleteDocument('${encodeURIComponent(doc.filename)}')" title="Delete from index">
                Delete
              </button>
            </td>
          </tr>
        `;
      });

      this.docsTbody.innerHTML = html;
    } catch (e) {
      console.error('History docs error:', e);
      this.docsTbody.innerHTML = `
        <tr>
          <td colspan="7" style="text-align: center; padding: 24px; color: var(--accent-red, #ff5555);">
            Failed to load audit history: ${e.message}
          </td>
        </tr>
      `;
    }
  },

  renderQueries() {
    if (!this.queriesTbody) return;
    try {
      const hist = JSON.parse(localStorage.getItem('scigraph_query_history') || '[]');
      if (hist.length === 0) {
        this.queriesTbody.innerHTML = `
          <tr>
            <td colspan="6" style="text-align: center; padding: 24px; color: var(--text-muted);">
              No past research queries recorded yet. Try asking a question in Overview or Research Copilot.
            </td>
          </tr>
        `;
        return;
      }

      let html = '';
      hist.forEach(q => {
        const dateStr = q.timestamp ? new Date(q.timestamp).toLocaleString() : 'Just now';
        const snippet = (q.answer || '').substring(0, 110) + '...';
        html += `
          <tr style="border-bottom: 1px solid var(--border-subtle);">
            <td style="font-weight: 500; color: var(--text-primary); font-size: 13px; max-width: 280px; word-break: break-word;">
              ${this.escapeHtml(q.query)}
            </td>
            <td>
              <span class="badge badge-neutral" style="font-size: 10px; font-family: var(--font-mono);">${this.escapeHtml(q.mode || 'hybrid')}</span>
            </td>
            <td style="font-size: 12px; color: var(--text-secondary); max-width: 320px; line-height: 1.4;">
              ${this.escapeHtml(snippet)}
            </td>
            <td style="font-size: 11px; font-family: var(--font-mono); color: var(--accent-primary);">${q.latency || 'N/A'}</td>
            <td style="font-size: 11px; color: var(--text-tertiary);">${dateStr}</td>
            <td style="text-align: right;">
              <button class="btn btn-xs btn-primary" onclick="HistoryManager.viewInCopilot('${encodeURIComponent(q.query)}')">
                Ask Again
              </button>
            </td>
          </tr>
        `;
      });

      this.queriesTbody.innerHTML = html;
    } catch (e) {
      console.warn('Error reading query history:', e);
    }
  },

  async deleteDocument(encodedName) {
    const filename = decodeURIComponent(encodedName);
    if (!confirm(`Delete ${filename} from storage and parsed index?`)) return;
    try {
      const resp = await fetch(`/uploads/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (resp.ok) {
        this.loadDocsHistory();
        if (window.LibraryManager) window.LibraryManager.fetchUploads();
        if (window.DashboardManager) window.DashboardManager.loadAll();
      } else {
        alert('Could not delete document.');
      }
    } catch (e) {
      alert(`Error deleting document: ${e.message}`);
    }
  },

  clearQueryHistory() {
    if (!confirm('Clear all query history?')) return;
    localStorage.removeItem('scigraph_query_history');
    this.renderQueries();
  },

  viewInCopilot(encodedQuery) {
    const query = decodeURIComponent(encodedQuery);
    if (window.NavManager) {
      window.NavManager.switchTab('assistant');
      const input = document.getElementById('chat-input') || document.getElementById('copilot-input');
      if (input) {
        input.value = query;
        input.focus();
      }
    }
  },

  formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  },

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
};

window.HistoryManager = HistoryManager;
