/**
 * SciGraph Research Insights & Graph Analytics Manager
 * High-centrality concept detection, bridge entities, and domain cluster analytics.
 */
const InsightsManager = {
  graphData: null,

  async init() {
    await this.refresh();
  },

  async refresh() {
    try {
      const data = await API.getGraph(300);
      this.graphData = data || { nodes: [], links: [] };
      this.render();
    } catch (e) {
      console.error('Failed to load insights data:', e);
    }
  },

  render() {
    const container = document.getElementById('insights-view-container');
    if (!container) return;

    const nodes = this.graphData.nodes || [];
    const links = this.graphData.links || [];

    // Calculate top bridge entities (highest degree)
    const sortedNodes = [...nodes].sort((a, b) => (b.degree || 0) - (a.degree || 0));
    const topEntities = sortedNodes.slice(0, 8);

    // Group types
    const typeCounts = {};
    nodes.forEach(n => {
      const t = n.type || 'concept';
      typeCounts[t] = (typeCounts[t] || 0) + 1;
    });

    container.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--space-4); margin-bottom: var(--space-6);">
        <div class="card">
          <div class="label-technical">// GRAPH TOPOLOGY</div>
          <div style="display: flex; align-items: baseline; gap: 8px; margin: 8px 0;">
            <span style="font-size: 28px; font-weight: 700; font-family: var(--font-mono); color: var(--accent-primary);">${nodes.length}</span>
            <span style="font-size: 12px; color: var(--text-muted);">indexed entities</span>
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
            Active concept nodes synthesized across ingested papers in current workspace.
          </div>
        </div>

        <div class="card">
          <div class="label-technical">// DENSITY & CONNECTIVITY</div>
          <div style="display: flex; align-items: baseline; gap: 8px; margin: 8px 0;">
            <span style="font-size: 28px; font-weight: 700; font-family: var(--font-mono); color: var(--accent-secondary);">${links.length}</span>
            <span style="font-size: 12px; color: var(--text-muted);">semantic links</span>
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
            Cross-entity semantic assertions extracted by dual-level LightRAG graph engine.
          </div>
        </div>

        <div class="card">
          <div class="label-technical">// GRAPH DENSITY RATIO</div>
          <div style="display: flex; align-items: baseline; gap: 8px; margin: 8px 0;">
            <span style="font-size: 28px; font-weight: 700; font-family: var(--font-mono); color: var(--accent-amber);">
              ${nodes.length > 0 ? (links.length / nodes.length).toFixed(2) : '0.00'}
            </span>
            <span style="font-size: 12px; color: var(--text-muted);">edges / entity</span>
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
            Indicates high interconnectedness and cross-document relational reasoning capability.
          </div>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: 2fr 1fr; gap: var(--space-6);">
        <!-- Top Central Bridge Entities -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">High-Centrality Bridge Entities</div>
              <div class="card-subtitle">Nodes with the highest semantic degree connecting disparate concepts</div>
            </div>
            <button class="btn btn-sm btn-outline" onclick="NavManager.switchTab('graph')">Explore in 3D →</button>
          </div>

          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Concept / Entity</th>
                  <th>Type</th>
                  <th>Degree</th>
                  <th style="text-align: right;">Action</th>
                </tr>
              </thead>
              <tbody>
                ${topEntities.length > 0 ? topEntities.map(node => `
                  <tr>
                    <td>
                      <div style="font-weight: 600; color: var(--text-primary);">
                        ${escapeHtml(node.id)}
                      </div>
                      ${node.desc ? `<div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(node.desc.slice(0, 90))}…</div>` : ''}
                    </td>
                    <td>
                      <span class="badge" style="background: rgba(181, 243, 107, 0.12); color: var(--accent-primary); border: 1px solid rgba(181, 243, 107, 0.3);">
                        ${escapeHtml(node.type || 'concept')}
                      </span>
                    </td>
                    <td style="font-family: var(--font-mono); font-size: 12px; color: var(--accent-secondary); font-weight: 600;">
                      ${node.degree || 1} links
                    </td>
                    <td style="text-align: right;">
                      <button class="btn btn-sm btn-ghost" onclick="
                        NavManager.switchTab('assistant');
                        if (window.AssistantManager) AssistantManager.setInputPrompt('Explain the significance and role of ${escapeJs(node.id)} in the context of indexed research papers.');
                      ">Analyze</button>
                    </td>
                  </tr>
                `).join('') : `
                  <tr>
                    <td colspan="4" style="text-align: center; color: var(--text-muted); padding: 24px;">
                      No graph entities loaded yet. Ingest documents to generate bridge entities.
                    </td>
                  </tr>
                `}
              </tbody>
            </table>
          </div>
        </div>

        <!-- Entity Type Breakdown -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">Ontology Types</div>
              <div class="card-subtitle">Semantic distribution</div>
            </div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px; margin-top: var(--space-2);">
            ${Object.entries(typeCounts).map(([type, count]) => {
              const color = TYPE_COLORS[type] || 'var(--accent-primary)';
              const pct = nodes.length > 0 ? Math.round((count / nodes.length) * 100) : 0;
              return `
                <div>
                  <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                    <span style="font-family: var(--font-mono); color: var(--text-primary); text-transform: uppercase;">${type}</span>
                    <span style="font-family: var(--font-mono); color: var(--text-muted);">${count} (${pct}%)</span>
                  </div>
                  <div style="width: 100%; height: 5px; background: rgba(255,255,255,0.06); border-radius: 3px; overflow: hidden;">
                    <div style="width: ${pct}%; height: 100%; background: ${color}; border-radius: 3px;"></div>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;
  }
};
