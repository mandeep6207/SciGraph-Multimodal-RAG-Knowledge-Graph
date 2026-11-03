/**
 * SciGraph Live Activity Manager
 * Real-time event streaming via SSE (/logs/live) with severity filters and scroll controls.
 */
const LiveActivityManager = {
  eventSource: null,
  autoScroll: true,
  filterLevel: 'all',

  init() {
    this.bindControls();
  },

  connect() {
    if (this.eventSource) return;

    this.eventSource = new EventSource('/logs/live');

    this.eventSource.onmessage = (event) => {
      if (!event.data || event.data.startsWith(':')) return;
      try {
        const item = JSON.parse(event.data);
        this.addLogItem(item.level || 'info', item.message || '');
      } catch (e) {
        this.addLogItem('info', event.data);
      }
    };

    this.eventSource.onerror = (e) => {
      console.warn('Live log stream disconnected:', e);
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
    };
  },

  bindControls() {
    const clearBtn = document.getElementById('live-log-clear-btn');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        const container = document.getElementById('live-log-container');
        if (container) container.innerHTML = '';
      });
    }

    const scrollBtn = document.getElementById('live-log-autoscroll-btn');
    if (scrollBtn) {
      scrollBtn.addEventListener('click', () => {
        this.autoScroll = !this.autoScroll;
        scrollBtn.textContent = this.autoScroll ? 'Pause Scroll' : 'Resume Scroll';
        scrollBtn.classList.toggle('btn-secondary');
        scrollBtn.classList.toggle('btn-outline');
      });
    }

    document.querySelectorAll('[data-log-filter]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('[data-log-filter]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.filterLevel = btn.getAttribute('data-log-filter');
        this.applyFilter();
      });
    });
  },

  addLogItem(level, message) {
    const container = document.getElementById('live-log-container');
    if (!container) return;

    const row = document.createElement('div');
    row.className = `log-row log-${level}`;
    row.setAttribute('data-level', level);

    let badgeCls = 'badge-neutral';
    if (level === 'info') badgeCls = 'badge-info';
    else if (level === 'warning' || level === 'warn') badgeCls = 'badge-warning';
    else if (level === 'error') badgeCls = 'badge-danger';

    row.innerHTML = `
      <span class="badge ${badgeCls}" style="font-size: 10px; text-transform: uppercase;">${level}</span>
      <span style="color: var(--text-muted); font-family: var(--font-mono); font-size: 11px;">${new Date().toLocaleTimeString()}</span>
      <span style="font-family: var(--font-mono); font-size: 12px; color: var(--text-primary); word-break: break-all;">${escapeHtml(message)}</span>
    `;

    if (this.filterLevel !== 'all' && this.filterLevel !== level) {
      row.style.display = 'none';
    }

    container.appendChild(row);

    if (this.autoScroll) {
      container.scrollTop = container.scrollHeight;
    }
  },

  applyFilter() {
    const rows = document.querySelectorAll('.log-row');
    rows.forEach(r => {
      const lvl = r.getAttribute('data-level');
      if (this.filterLevel === 'all' || this.filterLevel === lvl) {
        r.style.display = 'flex';
      } else {
        r.style.display = 'none';
      }
    });
  }
};
