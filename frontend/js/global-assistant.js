/**
 * SciGraph Global AI Assistant
 * Interacts with /api/chat/global using Grok Cloud or Local Ollama models.
 */
const GlobalAssistant = {
  isGenerating: false,

  init() {
    this.streamEl = document.getElementById('global-assistant-stream');
    this.inputEl = document.getElementById('global-assistant-input');
    this.selectEl = document.getElementById('global-assistant-model-select');
    this.badgeEl = document.getElementById('global-assistant-status-badge');
    this.submitBtn = document.getElementById('global-assistant-submit-btn');

    this.loadModels();

    if (this.selectEl) {
      this.selectEl.addEventListener('change', () => {
        const selected = this.selectEl.options[this.selectEl.selectedIndex].text;
        if (this.badgeEl) {
          this.badgeEl.textContent = selected.split('(')[0].trim().toUpperCase() + ' ACTIVE';
        }
      });
    }
  },

  async loadModels() {
    try {
      const res = await fetch('/api/models');
      if (!res.ok) return;
      const data = await res.json();
      if (data && data.models && data.models.length > 0 && this.selectEl) {
        this.selectEl.innerHTML = '';
        data.models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.name;
          if (m.id === data.default) opt.selected = true;
          this.selectEl.appendChild(opt);
        });
        if (this.badgeEl) {
          const activeName = (data.models.find(m => m.id === data.default) || data.models[0]).name;
          this.badgeEl.textContent = activeName.split('(')[0].trim().toUpperCase() + ' READY';
        }
      }
    } catch (e) {
      console.warn('Could not load /api/models:', e);
    }
  },

  async send() {
    if (this.isGenerating || !this.inputEl) return;
    const text = this.inputEl.value.trim();
    if (!text) return;

    const model = this.selectEl ? this.selectEl.value : 'openai/gpt-oss-120b';

    // 1. Append User Message
    this.appendMessage('user', text);
    this.inputEl.value = '';
    this.isGenerating = true;

    if (this.submitBtn) {
      this.submitBtn.disabled = true;
      this.submitBtn.innerHTML = `<span>Thinking...</span>`;
    }

    // 2. Append Pending Assistant Bubble
    const pendingId = 'ga-msg-' + Date.now();
    this.appendMessage('assistant', 'Synthesizing response...', pendingId, true);

    try {
      const resp = await fetch('/api/chat/global', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          model: model,
          temperature: 0.7
        })
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(err.detail || `Server returned ${resp.status}`);
      }

      const result = await resp.json();
      const reply = result.reply || 'No response generated.';
      const latency = (result.latency_ms / 1000).toFixed(2);
      const provider = (result.provider || 'AI').toUpperCase();

      this.updatePendingMessage(pendingId, reply, `${latency}s · ${provider}`);
      
      // Save to query history
      this.saveHistory(text, reply, model, `${latency}s`);
    } catch (err) {
      this.updatePendingMessage(pendingId, `**Error:** ${err.message}`, 'Failed', true);
    } finally {
      this.isGenerating = false;
      if (this.submitBtn) {
        this.submitBtn.disabled = false;
        this.submitBtn.innerHTML = `<span>Send</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>`;
      }
    }
  },

  appendMessage(role, text, id = null, isPending = false) {
    if (!this.streamEl) return;
    const row = document.createElement('div');
    if (id) row.id = id;
    row.style.display = 'flex';
    row.style.gap = '12px';
    row.style.alignItems = 'flex-start';
    row.style.padding = '10px 12px';
    row.style.borderRadius = 'var(--radius-md)';
    row.style.animation = 'fadeIn 0.2s ease-out';

    if (role === 'user') {
      row.style.background = 'rgba(255, 255, 255, 0.03)';
      row.style.border = '1px solid var(--border-subtle)';
      row.innerHTML = `
        <div style="width: 26px; height: 26px; border-radius: var(--radius-sm); background: var(--bg-surface-elevated); border: 1px solid var(--border-default); color: var(--text-primary); display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 11px; flex-shrink: 0;">YOU</div>
        <div style="flex: 1; font-size: 13px; color: var(--text-primary); line-height: 1.5; white-space: pre-wrap;">${this.escapeHtml(text)}</div>
      `;
    } else {
      row.style.background = 'rgba(181, 243, 107, 0.03)';
      row.style.border = '1px solid rgba(181, 243, 107, 0.12)';
      row.innerHTML = `
        <div style="width: 26px; height: 26px; border-radius: var(--radius-sm); background: var(--accent-primary); color: #000; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 11px; flex-shrink: 0;">SG</div>
        <div style="flex: 1; min-width: 0;">
          <div class="msg-content" style="font-size: 13px; color: var(--text-primary); line-height: 1.6;">${isPending ? '<em style="color: var(--text-tertiary);">' + text + '</em>' : this.formatMarkdown(text)}</div>
          <div class="msg-meta" style="font-size: 10px; font-family: var(--font-mono); color: var(--text-tertiary); margin-top: 4px;"></div>
        </div>
      `;
    }

    this.streamEl.appendChild(row);
    this.streamEl.scrollTop = this.streamEl.scrollHeight;
  },

  updatePendingMessage(id, text, metaText, isError = false) {
    const el = document.getElementById(id);
    if (!el) return;
    const content = el.querySelector('.msg-content');
    const meta = el.querySelector('.msg-meta');
    if (content) {
      content.innerHTML = this.formatMarkdown(text);
      if (isError) content.style.color = 'var(--accent-red, #ff5555)';
    }
    if (meta && metaText) {
      meta.textContent = metaText;
    }
    if (this.streamEl) {
      this.streamEl.scrollTop = this.streamEl.scrollHeight;
    }
  },

  saveHistory(query, answer, model, latency) {
    try {
      const hist = JSON.parse(localStorage.getItem('scigraph_query_history') || '[]');
      hist.unshift({
        id: 'q_' + Date.now(),
        query,
        answer,
        mode: model,
        latency,
        timestamp: new Date().toISOString()
      });
      localStorage.setItem('scigraph_query_history', JSON.stringify(hist.slice(0, 50)));
      if (window.HistoryManager) {
        window.HistoryManager.renderQueries();
      }
    } catch (e) {
      console.warn('Failed to save query to history:', e);
    }
  },

  formatMarkdown(str) {
    if (!str) return '';
    // Basic Markdown format
    let out = this.escapeHtml(str);
    out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    out = out.replace(/\*(.*?)\*/g, '<em>$1</em>');
    out = out.replace(/`(.*?)`/g, '<code style="background: rgba(255,255,255,0.06); padding: 2px 4px; border-radius: 3px; font-family: var(--font-mono); font-size: 11px;">$1</code>');
    out = out.replace(/\n\n/g, '<br><br>');
    out = out.replace(/\n/g, '<br>');
    return out;
  },

  escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
};

window.GlobalAssistant = GlobalAssistant;
