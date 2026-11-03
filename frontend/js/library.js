/**
 * SciGraph Universal Research Library & Ingestion Manager
 * Supports 18+ formats (PDF, Office, Data, LaTeX, Images), true concurrent processing,
 * individual stage progress, pause/resume, retry, cancel, and deduplication.
 */
const LibraryManager = {
  documents: [],
  searchQuery: '',
  queue: [], // Array of { id, file, filename, size, status, stage, progress, error, jobId, cached, eventSource, timings, chunks, nodes }
  queuePaused: false,

  SUPPORTED_EXTENSIONS: [
    '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.tiff', '.bmp',
    '.docx', '.doc', '.xlsx', '.xls', '.csv', '.pptx', '.ppt',
    '.tex', '.bib', '.txt', '.md', '.rtf', '.html', '.htm', '.json', '.xml'
  ],

  async init() {
    this.bindDropzone();
    this.bindSearch();
    await this.refresh();
  },

  async refresh() {
    try {
      this.documents = await API.getUploads();
      this.render();
      if (window.DashboardManager) {
        DashboardManager.refresh();
      }
    } catch (e) {
      console.error('Failed to load documents:', e);
    }
  },

  bindDropzone() {
    const dropzone = document.getElementById('library-dropzone');
    const fileInput = document.getElementById('library-file-input');
    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', (e) => {
      if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'A') {
        fileInput.click();
      }
    });

    ['dragenter', 'dragover'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach(name => {
      dropzone.addEventListener(name, (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (e) => {
      const files = Array.from(e.dataTransfer.files || []);
      if (files.length > 0) {
        this.addFilesToQueue(files);
      }
    });

    fileInput.addEventListener('change', (e) => {
      const files = Array.from(e.target.files || []);
      if (files.length > 0) {
        this.addFilesToQueue(files);
      }
      fileInput.value = '';
    });
  },

  bindSearch() {
    const input = document.getElementById('library-search-input');
    if (input) {
      input.addEventListener('input', (e) => {
        this.searchQuery = e.target.value.toLowerCase().trim();
        this.render();
      });
    }
  },

  addFilesToQueue(files) {
    let addedCount = 0;

    files.forEach(file => {
      const ext = '.' + file.name.split('.').pop().toLowerCase();
      if (!this.SUPPORTED_EXTENSIONS.includes(ext)) {
        Toast.show(`Unsupported format: ${file.name}. Supported: PDF, Office, Data, LaTeX, Images.`, 'warning');
        return;
      }

      // Check if file already queued and active
      const existing = this.queue.find(item => item.filename === file.name && !['done', 'failed', 'cancelled'].includes(item.status));
      if (existing) {
        return;
      }

      const id = 'q_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
      this.queue.push({
        id,
        file,
        filename: file.name,
        size: file.size,
        status: 'staged',
        stage: 'queued',
        progress: 0,
        error: null,
        jobId: null,
        cached: false,
        eventSource: null,
        timings: {},
        chunks: 0,
        nodes: 0,
        relations: 0,
      });
      addedCount++;
    });

    if (addedCount > 0) {
      Toast.show(`Added ${addedCount} document${addedCount > 1 ? 's' : ''} to universal ingestion queue`, 'info');
      this.renderQueue();
    }
  },

  renderQueue() {
    const queueCard = document.getElementById('upload-queue-card');
    const queueTbody = document.getElementById('upload-queue-tbody');
    const countBadge = document.getElementById('queue-count-badge');
    const statusIndicator = document.getElementById('queue-status-indicator');
    const pauseBtn = document.getElementById('queue-pause-btn');

    if (!queueCard || !queueTbody) return;

    if (this.queue.length === 0) {
      queueCard.style.display = 'none';
      return;
    }

    queueCard.style.display = 'block';
    if (countBadge) {
      countBadge.textContent = `${this.queue.length} file${this.queue.length > 1 ? 's' : ''}`;
    }
    if (statusIndicator) {
      statusIndicator.textContent = this.queuePaused ? 'PAUSED' : 'CONCURRENT ACTIVE';
      statusIndicator.className = this.queuePaused ? 'badge badge-warning' : 'badge badge-info';
    }
    if (pauseBtn) {
      pauseBtn.textContent = this.queuePaused ? 'Resume Queue' : 'Pause Queue';
    }

    queueTbody.innerHTML = this.queue.map(item => {
      const sizeMb = (item.size / (1024 * 1024)).toFixed(2) + ' MB';
      
      let statusBadge = '';
      if (item.status === 'staged') {
        statusBadge = '<span class="badge badge-neutral">Staged</span>';
      } else if (item.status === 'uploading') {
        statusBadge = '<span class="badge badge-info"><span class="pulse-indicator"></span>Uploading...</span>';
      } else if (item.status === 'processing' || item.status === 'parsing') {
        const stageLabel = (item.stage || 'PROCESSING').toUpperCase();
        statusBadge = `<span class="badge badge-warning" style="color: var(--accent-primary); border-color: rgba(181,243,107,0.3);"><span class="pulse-indicator"></span>${stageLabel}</span>`;
      } else if (item.status === 'done') {
        const timingStr = item.timings?.total ? ` · ${item.timings.total}s` : '';
        statusBadge = `<span class="badge badge-success">✓ Completed (${item.chunks || 0} chunks${timingStr})</span>`;
      } else if (item.status === 'failed') {
        statusBadge = `<span class="badge badge-danger" title="${escapeHtml(item.error || 'Failed')}">✕ Failed</span>`;
      } else if (item.status === 'cancelled') {
        statusBadge = '<span class="badge badge-neutral">Cancelled</span>';
      }

      let actions = '';
      if (item.status === 'staged') {
        actions = `<button class="btn btn-sm btn-ghost" onclick="LibraryManager.removeFromQueue('${item.id}')">Dismiss</button>`;
      } else if (item.status === 'failed') {
        actions = `
          <button class="btn btn-sm btn-outline" onclick="LibraryManager.retryItem('${item.id}')" title="Retry Ingestion">↻ Retry</button>
          <button class="btn btn-sm btn-ghost" onclick="LibraryManager.removeFromQueue('${item.id}')">✕</button>
        `;
      } else if (item.status === 'uploading' || item.status === 'processing' || item.status === 'parsing') {
        actions = `<button class="btn btn-sm btn-outline" style="border-color: rgba(224,93,82,0.4); color: #E05D52;" onclick="LibraryManager.cancelItem('${item.id}')" title="Cancel this job">Cancel</button>`;
      } else if (item.status === 'done' || item.status === 'cancelled') {
        actions = `<button class="btn btn-sm btn-ghost" onclick="LibraryManager.removeFromQueue('${item.id}')">Dismiss</button>`;
      }

      const barColor = item.status === 'failed'
        ? 'var(--status-danger)'
        : item.status === 'done'
        ? 'var(--accent-primary)'
        : 'var(--accent-secondary)';

      return `
        <tr>
          <td>
            <div style="font-weight: 500; display: flex; align-items: center; gap: 8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--accent-primary);">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              <span title="${escapeHtml(item.filename)}">${escapeHtml(item.filename)}</span>
            </div>
            ${item.error ? `<div style="font-size: 11px; color: var(--status-danger); margin-top: 2px;">${escapeHtml(item.error)}</div>` : ''}
          </td>
          <td style="font-size: 12px; color: var(--text-secondary); font-family: var(--font-mono);">${sizeMb}</td>
          <td>${statusBadge}</td>
          <td>
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="flex: 1; height: 6px; background: rgba(255,255,255,0.08); border-radius: 3px; overflow: hidden;">
                <div style="width: ${item.progress}%; height: 100%; background: ${barColor}; border-radius: 3px; transition: width 0.25s ease;"></div>
              </div>
              <span style="font-size: 11px; font-family: var(--font-mono); color: var(--text-muted); width: 36px; text-align: right;">${Math.round(item.progress)}%</span>
            </div>
          </td>
          <td style="text-align: right;">
            ${actions}
          </td>
        </tr>
      `;
    }).join('');
  },

  async togglePauseQueue() {
    try {
      if (this.queuePaused) {
        await API.resumeQueue();
        this.queuePaused = false;
        Toast.show('Queue resumed — processing resumed', 'info');
      } else {
        await API.pauseQueue();
        this.queuePaused = true;
        Toast.show('Queue paused', 'warning');
      }
      this.renderQueue();
    } catch (e) {
      Toast.show('Failed to toggle queue pause: ' + e.message, 'error');
    }
  },

  removeFromQueue(id) {
    const idx = this.queue.findIndex(i => i.id === id);
    if (idx !== -1) {
      const item = this.queue[idx];
      if (item.eventSource) {
        item.eventSource.close();
      }
      if (item.jobId) {
        API.removeJob(item.jobId).catch(() => {});
      }
      this.queue.splice(idx, 1);
      this.renderQueue();
    }
  },

  clearCompleted() {
    this.queue = this.queue.filter(i => i.status !== 'done');
    API.clearCompletedJobs().catch(() => {});
    this.renderQueue();
    Toast.show('Cleared completed items from queue', 'info');
  },

  clearQueue() {
    this.queue.forEach(item => {
      if (item.eventSource) {
        item.eventSource.close();
      }
      if (['processing', 'uploading'].includes(item.status) && item.jobId) {
        API.cancelJob(item.jobId).catch(() => {});
      }
    });
    this.queue = [];
    this.renderQueue();
    Toast.show('Queue cleared', 'info');
  },

  async cancelItem(id) {
    const item = this.queue.find(i => i.id === id);
    if (item) {
      if (item.eventSource) {
        item.eventSource.close();
        item.eventSource = null;
      }
      if (item.jobId) {
        await API.cancelJob(item.jobId).catch(() => {});
      }
      item.status = 'cancelled';
      item.stage = 'cancelled';
      item.progress = 0;
      this.renderQueue();
      Toast.show(`Cancelled ingestion for ${item.filename}`, 'info');
    }
  },

  async retryItem(id) {
    const item = this.queue.find(i => i.id === id);
    if (!item) return;

    item.status = 'uploading';
    item.stage = 'queued';
    item.progress = 5;
    item.error = null;
    this.renderQueue();

    try {
      const batchRes = await API.uploadBatch([item.file], true);
      const res = (batchRes.results || [])[0];
      if (res && res.status === 'error') {
        item.status = 'failed';
        item.error = res.error || 'Retry failed';
        item.progress = 0;
      } else if (res) {
        this.handleUploadResult(item, res);
      }
    } catch (err) {
      item.status = 'failed';
      item.error = err.message;
      item.progress = 0;
    }
    this.renderQueue();
  },

  async uploadAllQueue() {
    const pendingItems = this.queue.filter(i => ['staged', 'failed', 'cancelled'].includes(i.status));
    if (pendingItems.length === 0) {
      Toast.show('No pending documents in queue to upload', 'info');
      return;
    }

    pendingItems.forEach(i => {
      i.status = 'uploading';
      i.stage = 'uploading';
      i.progress = 10;
      i.error = null;
    });
    this.renderQueue();

    Toast.show(`Dispatching batch of ${pendingItems.length} documents to concurrent engine...`, 'info');

    try {
      const filesToUpload = pendingItems.map(i => i.file);
      const batchRes = await API.uploadBatch(filesToUpload);

      const results = batchRes.results || [];
      pendingItems.forEach((item, index) => {
        const res = results.find(r => r.original_name === item.filename || r.filename === item.filename) || results[index];
        if (!res) {
          item.status = 'failed';
          item.error = 'No server response';
          item.progress = 0;
        } else if (res.status === 'error') {
          item.status = 'failed';
          item.error = res.error || 'Upload error';
          item.progress = 0;
        } else {
          this.handleUploadResult(item, res);
        }
      });

      Toast.show(`Batch queued: ${batchRes.successful} successful, ${batchRes.failed} failed`, batchRes.failed > 0 ? 'warning' : 'success');
      this.renderQueue();
      await this.refresh();
    } catch (err) {
      pendingItems.forEach(i => {
        i.status = 'failed';
        i.error = err.message;
        i.progress = 0;
      });
      this.renderQueue();
      Toast.show('Batch upload failed: ' + err.message, 'error');
    }
  },

  handleUploadResult(item, res) {
    item.jobId = res.job_id || res.id;
    item.cached = !!res.cached;

    if (res.status === 'done' || res.cached) {
      item.status = 'done';
      item.stage = 'completed';
      item.progress = 100;
      item.chunks = res.chunks || 0;
      item.nodes = res.nodes || 0;
      item.timings = res.timings || {};
      this.renderQueue();
      return;
    }

    // Mark as queued in concurrent background pipeline
    item.status = 'processing';
    item.stage = 'queued';
    item.progress = 10;
    this.renderQueue();

    // Attach SSE progress stream
    if (item.jobId) {
      this.trackJobProgress(item);
    }
  },

  trackJobProgress(item) {
    if (item.eventSource) {
      item.eventSource.close();
    }

    try {
      const sse = new EventSource(`/progress/${item.jobId}`);
      item.eventSource = sse;

      sse.onmessage = (event) => {
        if (!event.data || event.data.startsWith(':')) return;
        try {
          const data = JSON.parse(event.data);
          
          if (data.stage) {
            item.stage = data.stage;
          }
          if (typeof data.progress === 'number') {
            item.progress = data.progress;
          }
          if (data.timings) {
            item.timings = data.timings;
          }
          if (data.chunks) item.chunks = data.chunks;
          if (data.nodes) item.nodes = data.nodes;
          if (data.relations) item.relations = data.relations;

          if (data.status === 'done' || data.stage === 'completed') {
            item.status = 'done';
            item.stage = 'completed';
            item.progress = 100;
            if (item.eventSource) {
              item.eventSource.close();
              item.eventSource = null;
            }
            this.refresh();
          } else if (data.status === 'error' || data.stage === 'error') {
            item.status = 'failed';
            item.stage = 'error';
            item.error = data.message || 'Processing error';
            if (item.eventSource) {
              item.eventSource.close();
              item.eventSource = null;
            }
          } else if (data.status === 'cancelled') {
            item.status = 'cancelled';
            item.stage = 'cancelled';
            if (item.eventSource) {
              item.eventSource.close();
              item.eventSource = null;
            }
          }
          this.renderQueue();
        } catch (e) {
          // Heartbeat or text event
        }
      };

      sse.onerror = () => {
        if (sse) sse.close();
        item.eventSource = null;
        setTimeout(() => this.refresh(), 2000);
      };
    } catch (e) {
      console.warn('Failed to attach SSE tracker:', e);
    }
  },

  render() {
    const tbody = document.getElementById('library-table-tbody');
    const emptyState = document.getElementById('library-empty-state');
    if (!tbody) return;

    let filtered = this.documents;
    if (this.searchQuery) {
      filtered = filtered.filter(d => d.filename.toLowerCase().includes(this.searchQuery));
    }

    if (!filtered || filtered.length === 0) {
      tbody.innerHTML = '';
      if (emptyState) emptyState.style.display = 'flex';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    tbody.innerHTML = filtered.map(doc => {
      const sizeMb = (doc.size / (1024 * 1024)).toFixed(2) + ' MB';
      const dateStr = new Date(doc.modified * 1000).toLocaleDateString();
      const isCompleted = doc.status === 'completed';
      const statusBadge = isCompleted
        ? `<span class="badge badge-success">✓ Indexed (${doc.chunks || 0} chunks)</span>`
        : `<span class="badge badge-neutral">Uploaded</span>`;

      return `
        <tr>
          <td>
            <div style="font-weight: 500; display: flex; align-items: center; gap: 8px;">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--accent-primary);">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
              <span>${escapeHtml(doc.filename)}</span>
            </div>
          </td>
          <td style="font-family: var(--font-mono); font-size: 12px;">${sizeMb}</td>
          <td>${dateStr}</td>
          <td>${statusBadge}</td>
          <td style="text-align: right;">
            <div style="display: inline-flex; gap: 6px;">
              <button class="btn btn-sm btn-outline" onclick="LibraryManager.queryDoc('${escapeJs(doc.filename)}')">Query</button>
              <button class="btn btn-sm btn-danger-outline" onclick="LibraryManager.confirmDelete('${escapeJs(doc.filename)}')">Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  },

  queryDoc(filename) {
    NavManager.switchTab('assistant');
    if (window.AssistantManager) {
      AssistantManager.setInputPrompt(`Analyze the research document "${filename}". Summarize its methodology, findings, and evidence claims.`);
    }
  },

  confirmDelete(filename) {
    if (confirm(`Permanently delete "${filename}" and its vector indices from SciGraph?`)) {
      this.deleteDoc(filename);
    }
  },

  async deleteDoc(filename) {
    try {
      await API.deleteDocument(filename);
      Toast.show(`Deleted "${filename}"`, 'info');
      await this.refresh();
    } catch (e) {
      Toast.show('Failed to delete document: ' + e.message, 'error');
    }
  }
};
