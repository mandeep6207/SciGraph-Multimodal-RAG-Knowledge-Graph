/**
 * SciGraph Universal AI Assistant Manager
 * ChatGPT-inspired interface supporting:
 *   Mode A: Global Assistant (Grok / Local open-ended conversations)
 *   Mode B: SciGraph Research Assistant (Evidence-grounded RAG with multi-document source selection)
 * Features real-time SSE streaming, stop generation, attachment upload, copy/regenerate, and conversation persistence.
 */

const AssistantManager = {
  conversations: [],
  activeConvId: null,
  activeMode: 'global', // 'global' | 'research'
  selectedModel: 'openai/gpt-oss-20b',
  selectedSources: [], // array of filenames, e.g. ['GA-Unit-1.pdf']
  allSources: [],
  isGenerating: false,
  activeAbortController: null,
  isSidebarCollapsed: false,
  userScrolledUp: false,

  async init() {
    this.bindDOM();
    await this.loadModels();
    await this.loadSources();
    await this.loadConversations();
    this.renderSourceChips();
  },

  bindDOM() {
    // Mode switcher buttons
    const btnModeGlobal = document.getElementById('chat-mode-global');
    const btnModeResearch = document.getElementById('chat-mode-research');
    if (btnModeGlobal && btnModeResearch) {
      btnModeGlobal.addEventListener('click', () => this.switchMode('global'));
      btnModeResearch.addEventListener('click', () => this.switchMode('research'));
    }

    // Model selector
    const modelSelect = document.getElementById('chat-model-select');
    if (modelSelect) {
      modelSelect.addEventListener('change', () => {
        this.selectedModel = modelSelect.value;
      });
    }

    // Sidebar collapse / expand
    const btnCollapse = document.getElementById('btn-chat-sidebar-toggle');
    if (btnCollapse) {
      btnCollapse.addEventListener('click', () => this.toggleSidebar());
    }

    // New Chat
    const btnNew = document.getElementById('btn-new-chat');
    if (btnNew) {
      btnNew.addEventListener('click', () => this.createNewConversation());
    }

    // Source picker modal toggle
    const btnOpenSources = document.getElementById('btn-open-sources-modal');
    const modalSources = document.getElementById('modal-sources-picker');
    const btnCloseSources = document.getElementById('close-sources-modal');
    const btnApplySources = document.getElementById('apply-sources-btn');

    if (btnOpenSources && modalSources) {
      btnOpenSources.addEventListener('click', () => {
        this.renderSourcesModalList();
        modalSources.classList.add('open');
      });
    }
    if (btnCloseSources && modalSources) {
      btnCloseSources.addEventListener('click', () => modalSources.classList.remove('open'));
    }
    if (btnApplySources && modalSources) {
      btnApplySources.addEventListener('click', () => {
        modalSources.classList.remove('open');
        this.renderSourceChips();
      });
    }

    // Attachment upload (+) button
    const btnAttach = document.getElementById('chat-attach-btn');
    const fileInput = document.getElementById('chat-file-input');
    if (btnAttach && fileInput) {
      btnAttach.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => this.handleAttachmentUpload(e));
    }

    // Input textarea & Send / Stop buttons
    const textarea = document.getElementById('chat-textarea');
    const sendBtn = document.getElementById('chat-send-btn');
    const stopBtn = document.getElementById('chat-stop-btn');

    const updateSendBtnState = () => {
      const hasText = textarea && textarea.value.trim().length > 0;
      if (sendBtn) {
        sendBtn.disabled = !hasText || this.isGenerating;
        if (!hasText || this.isGenerating) {
          sendBtn.classList.add('disabled');
        } else {
          sendBtn.classList.remove('disabled');
        }
      }
    };

    if (sendBtn) {
      sendBtn.addEventListener('click', () => this.handleSend());
    }

    if (stopBtn) {
      stopBtn.addEventListener('click', () => this.stopGenerating());
    }

    if (textarea) {
      textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleSend();
        }
      });
      // Auto expand height & update send button state
      textarea.addEventListener('input', () => {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 180) + 'px';
        updateSendBtnState();
      });
      updateSendBtnState();
    }

    // Scroll listener for smart auto-scrolling
    const msgContainer = document.getElementById('chat-messages-container');
    if (msgContainer) {
      msgContainer.addEventListener('scroll', () => {
        const isNearBottom = msgContainer.scrollHeight - msgContainer.scrollTop - msgContainer.clientHeight < 100;
        this.userScrolledUp = !isNearBottom;
      });
    }

    // Conversation search
    const searchConv = document.getElementById('chat-search-conv');
    if (searchConv) {
      searchConv.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase().trim();
        this.renderConversationsList(q);
      });
    }
  },

  async loadModels() {
    try {
      const resp = await fetch('/api/models');
      if (!resp.ok) return;
      const data = await resp.json();
      const select = document.getElementById('chat-model-select');
      if (select && data.models) {
        select.innerHTML = '';
        data.models.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = m.name;
          if (m.id === data.default) {
            opt.selected = true;
            this.selectedModel = m.id;
          }
          select.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn('Could not load models:', e);
    }
  },

  async loadSources() {
    try {
      const resp = await fetch('/api/sources');
      if (!resp.ok) return;
      this.allSources = await resp.json();
      // Default: If research mode and no selection, default to all documents
      this.renderSourceChips();
    } catch (e) {
      console.warn('Could not load sources:', e);
    }
  },

  switchMode(mode) {
    this.activeMode = mode;
    const btnGlobal = document.getElementById('chat-mode-global');
    const btnResearch = document.getElementById('chat-mode-research');
    const sourceBar = document.getElementById('chat-sources-bar');
    const openSourcesBtn = document.getElementById('btn-open-sources-modal');

    if (mode === 'global') {
      if (btnGlobal) btnGlobal.className = 'mode-toggle-btn active';
      if (btnResearch) btnResearch.className = 'mode-toggle-btn';
      if (sourceBar) sourceBar.style.display = 'none';
      if (openSourcesBtn) openSourcesBtn.style.display = 'none';
      const area = document.getElementById('chat-textarea');
      if (area) area.placeholder = 'Message Global Assistant... (Powered by Grok / Everyday AI & Code)';
    } else {
      if (btnGlobal) btnGlobal.className = 'mode-toggle-btn';
      if (btnResearch) btnResearch.className = 'mode-toggle-btn active';
      if (sourceBar) sourceBar.style.display = 'flex';
      if (openSourcesBtn) openSourcesBtn.style.display = 'inline-flex';
      const area = document.getElementById('chat-textarea');
      if (area) area.placeholder = 'Ask a question grounded in selected research documents...';
    }

    this.renderSourceChips();
  },

  toggleSidebar() {
    const sidebar = document.getElementById('chat-sidebar');
    if (!sidebar) return;
    this.isSidebarCollapsed = !this.isSidebarCollapsed;
    if (this.isSidebarCollapsed) {
      sidebar.classList.add('collapsed');
    } else {
      sidebar.classList.remove('collapsed');
    }
  },

  renderSourceChips() {
    const container = document.getElementById('chat-source-chips-container');
    const btnCount = document.getElementById('sources-count-badge');
    if (!container) return;

    if (this.selectedSources.length === 0) {
      container.innerHTML = `
        <span class="chip-all-sources" title="Querying all indexed papers">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path></svg>
          All Corpus Papers (${this.allSources.length || 15})
        </span>
      `;
      if (btnCount) btnCount.textContent = `All (${this.allSources.length || 15})`;
    } else {
      let html = '';
      this.selectedSources.forEach(src => {
        html += `
          <span class="source-chip">
            <span class="chip-label" title="${this.escapeHtml(src)}">${this.escapeHtml(src)}</span>
            <button class="chip-remove" onclick="AssistantManager.removeSource('${this.escapeJs(src)}')">✕</button>
          </span>
        `;
      });
      container.innerHTML = html;
      if (btnCount) btnCount.textContent = `${this.selectedSources.length} selected`;
    }
  },

  removeSource(src) {
    this.selectedSources = this.selectedSources.filter(s => s !== src);
    this.renderSourceChips();
  },

  renderSourcesModalList() {
    const tbody = document.getElementById('sources-modal-tbody');
    if (!tbody) return;

    if (this.allSources.length === 0) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:16px;">No indexed papers found.</td></tr>`;
      return;
    }

    let html = '';
    this.allSources.forEach(s => {
      const isChecked = this.selectedSources.includes(s.filename);
      html += `
        <tr style="border-bottom: 1px solid var(--border-subtle); cursor: pointer;" onclick="AssistantManager.toggleSourceCheckbox('${this.escapeJs(s.filename)}')">
          <td style="width: 36px; text-align: center;">
            <input type="checkbox" id="chk-src-${this.escapeJs(s.filename)}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation(); AssistantManager.toggleSourceCheckbox('${this.escapeJs(s.filename)}')">
          </td>
          <td style="font-weight: 500; font-family: var(--font-mono); font-size: 12px; color: var(--text-primary);">
            ${this.escapeHtml(s.filename)}
          </td>
          <td style="font-size: 11px; color: var(--accent-primary); font-family: var(--font-mono);">
            ${s.chunks || 1} chunks · ${s.nodes || 0} nodes
          </td>
          <td style="font-size: 11px; color: var(--text-tertiary);">
            ${this.formatBytes(s.size)}
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  },

  toggleSourceCheckbox(filename) {
    const idx = this.selectedSources.indexOf(filename);
    if (idx >= 0) {
      this.selectedSources.splice(idx, 1);
    } else {
      this.selectedSources.push(filename);
    }
    const chk = document.getElementById(`chk-src-${filename}`);
    if (chk) chk.checked = this.selectedSources.includes(filename);
    this.renderSourceChips();
  },

  selectAllSources() {
    this.selectedSources = this.allSources.map(s => s.filename);
    this.renderSourcesModalList();
    this.renderSourceChips();
  },

  clearSelectedSources() {
    this.selectedSources = [];
    this.renderSourcesModalList();
    this.renderSourceChips();
  },

  async handleAttachmentUpload(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const formData = new FormData();
    formData.append('file', file);

    Toast.show(`Uploading and indexing ${file.name}...`, 'info');

    try {
      const resp = await fetch('/upload', { method: 'POST', body: formData });
      if (!resp.ok) throw new Error('Upload failed');
      const data = await resp.json();
      Toast.show(`Attached and queued: ${file.name}`, 'success');

      // Refresh sources and auto-select this new file
      await this.loadSources();
      if (!this.selectedSources.includes(data.filename)) {
        this.selectedSources.push(data.filename);
      }
      this.renderSourceChips();
    } catch (err) {
      Toast.show(`Failed to upload attachment: ${err.message}`, 'error');
    } finally {
      e.target.value = '';
    }
  },

  async loadConversations() {
    try {
      this.conversations = await API.getConversations();
      if (!Array.isArray(this.conversations) || this.conversations.length === 0) {
        this.createNewConversation(false);
      } else {
        this.activeConvId = this.conversations[0].id;
      }
      this.renderConversationsList();
      this.renderMessages();
    } catch (e) {
      console.warn('Failed to load conversations, starting fresh:', e);
      this.createNewConversation(false);
    }
  },

  createNewConversation(save = true) {
    const newId = 'conv-' + Date.now();
    const newConv = {
      id: newId,
      title: 'New Conversation',
      created_at: Date.now(),
      messages: [],
    };
    this.conversations.unshift(newConv);
    this.activeConvId = newId;
    this.renderConversationsList();
    this.renderMessages();
    if (save) this.persistConversations();
  },

  selectConversation(convId) {
    this.activeConvId = convId;
    this.renderConversationsList();
    this.renderMessages();
  },

  deleteConversation(convId) {
    if (!confirm('Are you sure you want to delete this conversation?')) return;
    this.conversations = this.conversations.filter(c => c.id !== convId);
    if (this.conversations.length === 0) {
      this.createNewConversation(false);
    } else if (this.activeConvId === convId) {
      this.activeConvId = this.conversations[0].id;
    }
    this.renderConversationsList();
    this.renderMessages();
    this.persistConversations();
  },

  renderConversationsList(filterQuery = '') {
    const list = document.getElementById('conversations-list-container');
    if (!list) return;

    let items = this.conversations;
    if (filterQuery) {
      items = items.filter(c => (c.title || '').toLowerCase().includes(filterQuery));
    }

    if (items.length === 0) {
      list.innerHTML = `<div style="padding:16px 8px; font-size:12px; color:var(--text-tertiary); text-align:center;">No conversations found</div>`;
      return;
    }

    list.innerHTML = items.map(c => {
      const isActive = c.id === this.activeConvId;
      const dateStr = c.created_at ? new Date(c.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '';
      return `
        <div class="conv-item ${isActive ? 'active' : ''}" onclick="AssistantManager.selectConversation('${c.id}')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="min-width: 14px; opacity: 0.7;">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          <div class="conv-info">
            <div class="conv-title">${this.escapeHtml(c.title || 'Conversation')}</div>
            <div class="conv-date">${dateStr}</div>
          </div>
          <button class="conv-delete-btn" title="Delete conversation" onclick="event.stopPropagation(); AssistantManager.deleteConversation('${c.id}')">
            ✕
          </button>
        </div>
      `;
    }).join('');
  },

  renderMessages() {
    const container = document.getElementById('chat-messages-container');
    const chatMain = document.querySelector('.chat-main');
    if (!container) return;

    const currentConv = this.conversations.find(c => c.id === this.activeConvId);
    if (!currentConv || currentConv.messages.length === 0) {
      if (chatMain) chatMain.classList.add('is-empty');
      // Empty-State Welcome Screen
      container.innerHTML = `
        <div class="chat-welcome-container">
          <div class="welcome-logo">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <circle cx="6" cy="6" r="3"></circle>
              <circle cx="18" cy="18" r="3"></circle>
              <circle cx="6" cy="18" r="3"></circle>
              <circle cx="18" cy="6" r="3"></circle>
              <line x1="8.5" y1="7.5" x2="15.5" y2="16.5"></line>
              <line x1="8.5" y1="16.5" x2="15.5" y2="7.5"></line>
            </svg>
          </div>
          <h2 class="welcome-title">What would you like to explore today?</h2>
          <p class="welcome-subtitle">
            Ask questions, explore scientific concepts, or discover insights across your research.
          </p>

          <div class="suggested-prompts-grid">
            <div class="prompt-card" onclick="AssistantManager.sendPrompt('Explain a scientific concept: How do Variational Autoencoders and Diffusion Models model data distributions?')">
              <div class="prompt-text">Explain a scientific concept</div>
              <div class="prompt-subtext">Deep generative models & mathematical formulations</div>
            </div>
            <div class="prompt-card" onclick="AssistantManager.sendPrompt('Summarize my research papers across the indexed corpus with key findings and methods.')">
              <div class="prompt-text">Summarize my research papers</div>
              <div class="prompt-subtext">Evidence synthesis across active corpus</div>
            </div>
            <div class="prompt-card" onclick="AssistantManager.sendPrompt('Compare two research documents: How do Unit 1 and Unit 2 approach latent space representations?')">
              <div class="prompt-text">Compare two research documents</div>
              <div class="prompt-subtext">Comparative analysis of concepts & architectures</div>
            </div>
            <div class="prompt-card" onclick="AssistantManager.sendPrompt('Identify research gaps and future directions highlighted in the uploaded literature.')">
              <div class="prompt-text">Identify research gaps</div>
              <div class="prompt-subtext">Frontier questions and open challenges</div>
            </div>
          </div>
        </div>
      `;
      return;
    }

    if (chatMain) chatMain.classList.remove('is-empty');

    container.innerHTML = currentConv.messages.map((m, idx) => {
      const isUser = m.role === 'user';
      let contentHtml = '';
      if (isUser) {
        contentHtml = this.escapeHtml(m.text || m.content || '');
      } else {
        contentHtml = this.formatMarkdown(m.text || m.content || '');
      }

      const latencyTag = m.latency_ms 
        ? `<span class="badge badge-emerald" style="font-size:10px; font-family:var(--font-mono);">⚡ ${(m.latency_ms / 1000).toFixed(2)}s</span>` 
        : '';
      const modeTag = m.mode ? `<span class="badge badge-neutral" style="font-size:10px;">${m.mode.toUpperCase()}</span>` : '';
      const modelTag = m.model ? `<span class="badge badge-info" style="font-size:10px;">${m.model.split('/').pop()}</span>` : '';

      // Citations drawer
      let citationsHtml = '';
      if (m.citations && m.citations.length > 0) {
        citationsHtml = `
          <div class="citations-drawer">
            <div class="citations-header" onclick="this.nextElementSibling.classList.toggle('open')">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
              <span>Verified Document Sources (${m.citations.length})</span>
              <span style="font-size:10px; opacity:0.6; margin-left:auto;">Click to toggle</span>
            </div>
            <div class="citations-body">
              ${m.citations.map(c => `
                <div class="citation-entry">
                  <div class="citation-doc">📄 ${this.escapeHtml(c.document || 'Corpus Document')} — ${this.escapeHtml(c.section || 'Excerpt')}</div>
                  <div class="citation-snippet">${this.escapeHtml(c.snippet || '')}</div>
                </div>
              `).join('')}
            </div>
          </div>
        `;
      }

      return `
        <div class="msg-row ${m.role}" id="msg-row-${idx}">
          <div class="msg-avatar ${isUser ? 'user' : 'assistant'}">${isUser ? 'MK' : 'SG'}</div>
          <div class="msg-body">
            <div class="msg-bubble">${contentHtml}</div>
            <div class="msg-meta-bar">
              <span class="msg-time">${new Date(m.ts || Date.now()).toLocaleTimeString()}</span>
              ${latencyTag}
              ${modeTag}
              ${modelTag}
              ${!isUser ? `
                <div class="msg-actions">
                  <button class="msg-action-btn" title="Copy response" onclick="AssistantManager.copyMessageText(${idx})">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    <span>Copy</span>
                  </button>
                  <button class="msg-action-btn" title="Regenerate" onclick="AssistantManager.regenerateFrom(${idx})">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"></path></svg>
                    <span>Regenerate</span>
                  </button>
                </div>
              ` : ''}
            </div>
            ${citationsHtml}
          </div>
        </div>
      `;
    }).join('');

    container.scrollTop = container.scrollHeight;
  },

  sendPrompt(promptText) {
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.value = promptText;
      this.handleSend();
    }
  },

  async handleSend() {
    if (this.isGenerating) return;

    const textarea = document.getElementById('chat-textarea');
    if (!textarea) return;

    const text = textarea.value.trim();
    if (!text) return;

    textarea.value = '';
    textarea.style.height = 'auto';
    textarea.dispatchEvent(new Event('input'));

    const currentConv = this.conversations.find(c => c.id === this.activeConvId);
    if (!currentConv) return;

    // Add user message
    currentConv.messages.push({
      role: 'user',
      text: text,
      content: text,
      ts: Date.now(),
    });

    if (currentConv.messages.length === 1) {
      currentConv.title = text.slice(0, 36) + (text.length > 36 ? '...' : '');
      this.renderConversationsList();
    }

    this.renderMessages();
    this.userScrolledUp = false;
    this.scrollToBottom(true);

    // Toggle Send / Stop button
    this.isGenerating = true;
    this.setStreamingUI(true);

    // Create pending assistant message
    const pendingMsgIdx = currentConv.messages.length;
    currentConv.messages.push({
      role: 'assistant',
      text: '',
      content: '',
      model: this.selectedModel,
      mode: this.activeMode,
      ts: Date.now(),
      citations: [],
    });
    this.renderMessages();

    const container = document.getElementById('chat-messages-container');
    const lastRow = container.querySelector(`#msg-row-${pendingMsgIdx}`);
    const bubbleEl = lastRow ? lastRow.querySelector('.msg-bubble') : null;

    if (bubbleEl) {
      bubbleEl.innerHTML = `<span class="cursor-blink">▍</span>`;
    }

    this.activeAbortController = new AbortController();
    const t0 = performance.now();
    let accumulatedText = '';
    let citationsCaptured = [];

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: this.activeAbortController.signal,
        body: JSON.stringify({
          message: text,
          model: this.selectedModel,
          mode: this.activeMode,
          sources: this.selectedSources.length > 0 ? this.selectedSources : null,
          temperature: 0.7,
          messages: currentConv.messages.slice(0, -1).map(m => ({
            role: m.role,
            content: m.text || m.content || '',
          })),
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep last incomplete line

        for (const line of lines) {
          if (line.startsWith('data: ') && line.trim() !== 'data: [DONE]') {
            try {
              const data = json_parse_safe(line.slice(6));
              if (!data) continue;

              if (data.type === 'meta') {
                if (data.citations) citationsCaptured = data.citations;
              } else if (data.type === 'token') {
                accumulatedText += data.token;
                if (bubbleEl) {
                  bubbleEl.innerHTML = this.formatMarkdown(accumulatedText) + `<span class="cursor-blink">▍</span>`;
                  this.scrollToBottom(false);
                }
              } else if (data.type === 'error') {
                accumulatedText += `\n\n**Error:** ${data.error}`;
              }
            } catch (e) {
              console.warn('Error reading stream chunk:', e);
            }
          }
        }
      }

      const totalLatency = Math.round(performance.now() - t0);
      currentConv.messages[pendingMsgIdx].text = accumulatedText;
      currentConv.messages[pendingMsgIdx].content = accumulatedText;
      currentConv.messages[pendingMsgIdx].latency_ms = totalLatency;
      currentConv.messages[pendingMsgIdx].citations = citationsCaptured;

      this.renderMessages();
      this.persistConversations();

    } catch (err) {
      if (err.name === 'AbortError') {
        accumulatedText += ' *(Generation stopped by user)*';
      } else {
        accumulatedText += `\n\n⚠️ **Request Failed:** ${err.message}`;
      }
      currentConv.messages[pendingMsgIdx].text = accumulatedText;
      this.renderMessages();
    } finally {
      this.isGenerating = false;
      this.activeAbortController = null;
      this.setStreamingUI(false);
      this.scrollToBottom();
    }
  },

  scrollToBottom(force = false) {
    const container = document.getElementById('chat-messages-container');
    if (!container) return;
    if (force || !this.userScrolledUp) {
      container.scrollTop = container.scrollHeight;
    }
  },

  startNewChat() {
    NavManager.switchTab('assistant');
    this.createNewConversation(true);
    const textarea = document.getElementById('chat-textarea');
    if (textarea) {
      textarea.value = '';
      textarea.focus();
      textarea.dispatchEvent(new Event('input'));
    }
  },

  continueRecentChat() {
    NavManager.switchTab('assistant');
    if (this.conversations && this.conversations.length > 0) {
      this.selectConversation(this.conversations[0].id);
    } else {
      this.startNewChat();
    }
  },

  stopGenerating() {
    if (this.activeAbortController) {
      this.activeAbortController.abort();
    }
  },

  setStreamingUI(isStreaming) {
    const sendBtn = document.getElementById('chat-send-btn');
    const stopBtn = document.getElementById('chat-stop-btn');
    if (sendBtn && stopBtn) {
      if (isStreaming) {
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'flex';
      } else {
        sendBtn.style.display = 'flex';
        stopBtn.style.display = 'none';
      }
    }
  },

  copyMessageText(idx) {
    const currentConv = this.conversations.find(c => c.id === this.activeConvId);
    if (!currentConv || !currentConv.messages[idx]) return;
    const txt = currentConv.messages[idx].text || currentConv.messages[idx].content || '';
    navigator.clipboard.writeText(txt).then(() => {
      Toast.show('Copied to clipboard!', 'info');
    });
  },

  copyCodeBlock(btn) {
    const wrapper = btn.closest('.code-block-wrapper');
    if (!wrapper) return;
    const pre = wrapper.querySelector('pre');
    if (!pre) return;
    navigator.clipboard.writeText(pre.innerText).then(() => {
      const originalText = btn.innerHTML;
      btn.innerHTML = '<span style="color:var(--accent-primary);">✓ Copied</span>';
      setTimeout(() => { btn.innerHTML = originalText; }, 2000);
      Toast.show('Code copied to clipboard', 'info');
    });
  },

  regenerateFrom(idx) {
    const currentConv = this.conversations.find(c => c.id === this.activeConvId);
    if (!currentConv || idx <= 0) return;
    const priorUserMsg = currentConv.messages[idx - 1];
    if (priorUserMsg && priorUserMsg.role === 'user') {
      currentConv.messages = currentConv.messages.slice(0, idx);
      const textarea = document.getElementById('chat-textarea');
      if (textarea) textarea.value = priorUserMsg.text || priorUserMsg.content || '';
      this.handleSend();
    }
  },

  async persistConversations() {
    try {
      await API.saveConversations(this.conversations);
    } catch (e) {
      console.error('Failed to save conversations:', e);
    }
  },

  formatMarkdown(str) {
    if (!str) return '';
    let html = '';
    if (window.marked) {
      try {
        html = marked.parse(str);
      } catch (e) {
        html = this.escapeHtml(str);
      }
    } else {
      // Fallback basic markdown
      let out = this.escapeHtml(str);
      out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      out = out.replace(/\*(.*?)\*/g, '<em>$1</em>');
      out = out.replace(/`([^`]+)`/g, '<code>$1</code>');
      out = out.replace(/\n\n/g, '<br><br>');
      out = out.replace(/\n/g, '<br>');
      html = out;
    }

    // Enhance code blocks with header and copy button
    html = html.replace(/<pre><code(?:\s+class="language-(\w+)")?>([\s\S]*?)<\/code><\/pre>/gi, (match, lang, code) => {
      const language = (lang || 'code').toUpperCase();
      return `
        <div class="code-block-wrapper">
          <div class="code-block-header">
            <span>${language}</span>
            <button class="code-copy-btn" onclick="AssistantManager.copyCodeBlock(this)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
              <span>Copy code</span>
            </button>
          </div>
          <pre><code>${code}</code></pre>
        </div>
      `;
    });

    return html;
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
    return String(str).replace(/[&<>'"]/g, tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag] || tag));
  },

  escapeJs(str) {
    if (!str) return '';
    return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
  }
};

function json_parse_safe(str) {
  try {
    return JSON.parse(str);
  } catch (e) {
    return null;
  }
}

window.AssistantManager = AssistantManager;
