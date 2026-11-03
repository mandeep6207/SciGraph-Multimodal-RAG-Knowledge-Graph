/**
 * SciGraph Dashboard Manager (Overview)
 * Editorial Scientific Instrumentation, Interactive Hero Network Simulation,
 * Smooth Numeric Counter Transitions, and Real Telemetries.
 */
const DashboardManager = {
  stats: null,
  heroCanvasInitialized: false,

  async init() {
    this.initHeroNetwork();
    await this.refresh();
  },

  async refresh() {
    try {
      const [stats, health, uploads] = await Promise.all([
        API.getStats().catch(() => null),
        API.getHealth().catch(() => null),
        API.getUploads().catch(() => []),
      ]);

      if (stats) {
        this.stats = stats;
        this.renderStats(stats);
      }

      if (health) {
        this.renderHealth(health);
      }

      this.renderRecentDocs(uploads);
      this.renderActivityTimeline(uploads, stats);
    } catch (e) {
      console.error('Error refreshing dashboard:', e);
    }
  },

  animateNumber(el, target, duration = 800) {
    if (!el) return;
    const end = parseInt(target, 10) || 0;
    const start = parseInt(el.textContent, 10) || 0;
    if (start === end) {
      el.textContent = end;
      return;
    }

    const startTime = performance.now();
    const step = (currentTime) => {
      const progress = Math.min((currentTime - startTime) / duration, 1);
      // Ease out cubic
      const ease = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(start + (end - start) * ease);
      el.textContent = current;
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = end;
      }
    };
    requestAnimationFrame(step);
  },

  renderStats(stats) {
    const elDocs = document.getElementById('dash-stat-docs');
    const elNodes = document.getElementById('dash-stat-nodes');
    const elRels = document.getElementById('dash-stat-relations');
    const elQueries = document.getElementById('dash-stat-queries');
    const elQueued = document.getElementById('dash-stat-queued');

    this.animateNumber(elDocs, stats.total_docs ?? 0);
    this.animateNumber(elNodes, stats.total_nodes ?? 0);
    this.animateNumber(elRels, stats.total_relations ?? 0);
    this.animateNumber(elQueries, stats.total_queries ?? 0);
    if (elQueued) elQueued.textContent = stats.queued ?? 0;
  },

  renderHealth(health) {
    const elModel = document.getElementById('header-model-tag');
    const elDot = document.getElementById('header-status-dot');

    if (elModel) {
      elModel.textContent = `${health.llm_engine}: ${health.llm_model}`;
    }
    if (elDot) {
      if (health.status === 'ok') {
        elDot.classList.remove('offline');
        elDot.style.background = '#B5F36B';
        elDot.style.boxShadow = '0 0 10px #B5F36B';
      } else {
        elDot.classList.add('offline');
        elDot.style.background = '#E05D52';
        elDot.style.boxShadow = 'none';
      }
    }
  },

  renderRecentDocs(uploads) {
    const container = document.getElementById('dash-recent-docs-tbody');
    if (!container) return;

    if (!uploads || uploads.length === 0) {
      container.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center; padding: 32px 16px; color: var(--text-muted); font-size: 13px;">
            <div style="font-family: var(--font-mono); margin-bottom: 6px; color: var(--accent-secondary);">// CORPUS STATUS: EMPTY</div>
            No documents ingested in current workspace. Click <strong>"Add Research Papers"</strong> to begin multimodal graph synthesis.
          </td>
        </tr>
      `;
      return;
    }

    const recent = uploads.slice(0, 6);
    container.innerHTML = recent.map(doc => {
      const sizeStr = (doc.size / (1024 * 1024)).toFixed(2) + ' MB';
      const dateStr = new Date(doc.modified * 1000).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric'
      });
      const isCompleted = doc.status === 'completed';
      const statusBadge = isCompleted
        ? `<span class="badge badge-success">✓ Indexed (${doc.chunks || 0} chunks)</span>`
        : `<span class="badge badge-neutral">Uploaded</span>`;

      return `
        <tr class="editorial-row">
          <td>
            <div style="display: flex; align-items: center; gap: 10px;">
              <div class="doc-type-icon">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
              </div>
              <div style="display: flex; flex-direction: column;">
                <span class="doc-title-link" title="${escapeHtml(doc.filename)}" onclick="NavManager.switchTab('library')">${escapeHtml(doc.filename)}</span>
                <span style="font-size: 11px; font-family: var(--font-mono); color: var(--text-dim); margin-top: 1px;">
                  PDF · OCR Layout Verified
                </span>
              </div>
            </div>
          </td>
          <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary);">${sizeStr}</td>
          <td style="font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);">${dateStr}</td>
          <td>${statusBadge}</td>
          <td style="text-align: right;">
            <button class="btn btn-sm btn-outline" onclick="LibraryManager.queryDoc('${escapeJs(doc.filename)}')">Copilot Inquiry →</button>
          </td>
        </tr>
      `;
    }).join('');
  },

  renderActivityTimeline(uploads, stats) {
    const container = document.getElementById('dash-activity-timeline');
    if (!container) return;

    if (!uploads || uploads.length === 0) {
      container.innerHTML = `
        <div style="padding: 24px 0; text-align: center; color: var(--text-muted); font-size: 12px; font-family: var(--font-mono);">
          [ 0x00 // IDLE ] No recent pipeline telemetries recorded.
        </div>
      `;
      return;
    }

    const events = [];
    uploads.slice(0, 4).forEach(doc => {
      events.push({
        title: `Document Ingestion: ${doc.filename}`,
        meta: `${(doc.size / (1024 * 1024)).toFixed(2)} MB · ${doc.status === 'completed' ? 'Synthesized' : 'Uploaded'}`,
        time: new Date(doc.modified * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        type: doc.status === 'completed' ? 'indexed' : 'uploaded',
      });
    });

    if (stats && stats.total_nodes > 0) {
      events.unshift({
        title: `Knowledge Graph Synchronization`,
        meta: `${stats.total_nodes} entities · ${stats.total_relations} semantic edges active`,
        time: 'Just now',
        type: 'graph',
      });
    }

    container.innerHTML = events.map(ev => {
      const dotColor = ev.type === 'indexed' || ev.type === 'graph' ? 'var(--accent-primary)' : 'var(--accent-secondary)';
      return `
        <div class="timeline-item">
          <div class="timeline-marker" style="background: ${dotColor}; box-shadow: 0 0 8px ${dotColor};"></div>
          <div class="timeline-content">
            <div class="timeline-title">${escapeHtml(ev.title)}</div>
            <div class="timeline-meta">${escapeHtml(ev.meta)}</div>
          </div>
          <div class="timeline-time">${escapeHtml(ev.time)}</div>
        </div>
      `;
    }).join('');
  },

  initHeroNetwork() {
    if (this.heroCanvasInitialized) return;
    const canvas = document.getElementById('hero-network-canvas');
    if (!canvas) return;
    this.heroCanvasInitialized = true;

    const ctx = canvas.getContext('2d');
    let width, height;
    let mouse = { x: -1000, y: -1000, isHovering: false };

    const resize = () => {
      const rect = canvas.parentElement.getBoundingClientRect();
      width = canvas.width = rect.width;
      height = canvas.height = rect.height;
    };
    window.addEventListener('resize', resize);
    resize();

    canvas.parentElement.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.isHovering = true;
    });

    canvas.parentElement.addEventListener('mouseleave', () => {
      mouse.isHovering = false;
    });

    // Particle nodes
    const nodeCount = Math.min(36, Math.floor(width / 22));
    const nodes = [];
    const colors = ['#B5F36B', '#6EAA85', '#98D977', '#D9A65A', '#E9E8DF'];

    for (let i = 0; i < nodeCount; i++) {
      nodes.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.45,
        vy: (Math.random() - 0.5) * 0.45,
        radius: 1.8 + Math.random() * 2.2,
        color: colors[i % colors.length],
        pulse: Math.random() * Math.PI,
      });
    }

    const draw = () => {
      ctx.clearRect(0, 0, width, height);

      // Draw edges
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.hypot(dx, dy);

          if (dist < 110) {
            const alpha = Math.max(0, 0.22 * (1 - dist / 110));
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.strokeStyle = `rgba(181, 243, 107, ${alpha})`;
            ctx.lineWidth = 1;
            ctx.stroke();
          }
        }
      }

      // Draw and update nodes
      nodes.forEach(n => {
        n.x += n.vx;
        n.y += n.vy;

        // Bounce
        if (n.x < 0 || n.x > width) n.vx *= -1;
        if (n.y < 0 || n.y > height) n.vy *= -1;

        // Mouse repulsion
        if (mouse.isHovering) {
          const mdx = n.x - mouse.x;
          const mdy = n.y - mouse.y;
          const mdist = Math.hypot(mdx, mdy);
          if (mdist < 80 && mdist > 0) {
            const force = (80 - mdist) / 80;
            n.x += (mdx / mdist) * force * 1.5;
            n.y += (mdy / mdist) * force * 1.5;
          }
        }

        n.pulse += 0.03;
        const currentRadius = n.radius + Math.sin(n.pulse) * 0.4;

        ctx.beginPath();
        ctx.arc(n.x, n.y, Math.max(1, currentRadius), 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.shadowColor = n.color;
        ctx.shadowBlur = 6;
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      requestAnimationFrame(draw);
    };
    draw();
  }
};
