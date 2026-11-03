/**
 * SciGraph Processing Pipeline Manager
 * Smooth animated 10-stage pipeline with real SSE event tracking.
 */
const ProcessingManager = {
  currentJobId: null,
  eventSource: null,
  timerInterval: null,
  startTime: null,

  stages: [
    { id: 1, name: 'Upload received', key: 'queued' },
    { id: 2, name: 'PDF validation', key: 'validation' },
    { id: 3, name: 'Layout detection', key: 'layout' },
    { id: 4, name: 'Text/OCR extraction', key: 'ocr' },
    { id: 5, name: 'Multimodal extraction', key: 'multimodal' },
    { id: 6, name: 'Chunk generation', key: 'chunk' },
    { id: 7, name: 'Entity & Relations', key: 'entities' },
    { id: 8, name: 'Vector indexing', key: 'vector' },
    { id: 9, name: 'Knowledge graph update', key: 'graph' },
    { id: 10, name: 'Ready', key: 'done' },
  ],

  startJob(jobId, filename, cached = false, meta = {}) {
    this.currentJobId = jobId;
    this.startTime = Date.now();

    const container = document.getElementById('pipeline-view-container');
    if (container) container.style.display = 'block';

    const fnEl = document.getElementById('pipeline-current-filename');
    if (fnEl) fnEl.textContent = filename;

    this.renderStages(1);
    this.clearLogs();
    this.startTimer();

    if (cached) {
      this.log(`Document already indexed in scientific knowledge base.`);
      this.log(`Loaded ${meta.chunks || 0} chunks, ${meta.nodes || 0} entities, ${meta.relations || 0} relations.`);
      this.renderStages(10);
      this.stopTimer();
      Toast.show('Document ready (using existing index)', 'success');
      return;
    }

    this.connectSSE(jobId);
  },

  renderStages(activeStageId) {
    const grid = document.getElementById('pipeline-steps-grid');
    if (!grid) return;

    grid.innerHTML = this.stages.map(s => {
      let cls = 'pipeline-step';
      let icon = s.id;
      if (s.id < activeStageId) {
        cls += ' completed';
        icon = '✓';
      } else if (s.id === activeStageId) {
        cls += ' active';
      }

      return `
        <div class="${cls}">
          <div class="pipeline-step-num">${icon}</div>
          <div>${s.name}</div>
        </div>
      `;
    }).join('');
  },

  connectSSE(jobId) {
    if (this.eventSource) {
      this.eventSource.close();
    }

    this.eventSource = new EventSource(`/progress/${jobId}`);

    this.eventSource.onmessage = (event) => {
      if (!event.data || event.data.startsWith(':')) return;
      try {
        const data = JSON.parse(event.data);
        this.handleEvent(data);
      } catch (e) {
        // Raw log
        this.log(event.data);
      }
    };

    this.eventSource.onerror = (err) => {
      console.warn('SSE stream closed or error:', err);
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
    };
  },

  handleEvent(data) {
    const msg = data.message || '';
    const kind = data.kind || 'log';
    this.log(`[${kind.toUpperCase()}] ${msg}`);

    const lower = msg.toLowerCase();

    // Map logs to stages
    if (kind === 'queued') {
      this.renderStages(1);
    } else if (kind === 'status' || lower.includes('parsing')) {
      this.renderStages(2);
    } else if (lower.includes('layout') || lower.includes('mineru')) {
      this.renderStages(3);
    } else if (lower.includes('ocr') || lower.includes('text')) {
      this.renderStages(4);
    } else if (kind === 'multimodal_progress' || lower.includes('vision') || lower.includes('equation')) {
      this.renderStages(5);
    } else if (kind === 'chunk' || lower.includes('chunk')) {
      this.renderStages(6);
    } else if (kind === 'node' || kind === 'relation' || lower.includes('entit') || lower.includes('relation')) {
      this.renderStages(7);
    } else if (lower.includes('vector') || lower.includes('embed') || lower.includes('upsert')) {
      this.renderStages(8);
    } else if (lower.includes('merging') || lower.includes('graph')) {
      this.renderStages(9);
    } else if (kind === 'done' || lower.includes('finished')) {
      this.renderStages(10);
      this.stopTimer();
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
      Toast.show('Document processing complete and indexed!', 'success');
      if (window.DashboardManager) DashboardManager.refresh();
      if (window.LibraryManager) LibraryManager.refresh();
    } else if (kind === 'error') {
      this.stopTimer();
      Toast.show('Processing failed: ' + msg, 'error');
    }
  },

  log(text) {
    const term = document.getElementById('pipeline-log-terminal');
    if (!term) return;
    const line = document.createElement('div');
    line.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
  },

  clearLogs() {
    const term = document.getElementById('pipeline-log-terminal');
    if (term) term.innerHTML = '';
  },

  startTimer() {
    this.stopTimer();
    const timerEl = document.getElementById('pipeline-timer-val');
    this.timerInterval = setInterval(() => {
      if (!this.startTime) return;
      const elapsedSec = Math.floor((Date.now() - this.startTime) / 1000);
      const m = Math.floor(elapsedSec / 60).toString().padStart(2, '0');
      const s = (elapsedSec % 60).toString().padStart(2, '0');
      if (timerEl) timerEl.textContent = `${m}:${s}`;
    }, 1000);
  },

  stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }
};
