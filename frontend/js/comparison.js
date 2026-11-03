/**
 * SciGraph Paper Comparison Matrix Manager
 * Side-by-side scientific inquiry, methodology comparison, and cross-paper synthesis.
 */
const ComparisonManager = {
  documents: [],
  selectedDocs: [],

  async init() {
    await this.refresh();
  },

  async refresh() {
    try {
      this.documents = await API.getUploads();
      this.render();
    } catch (e) {
      console.error('Failed to load comparison data:', e);
    }
  },

  render() {
    const selectorContainer = document.getElementById('comparison-paper-selector');
    const matrixContainer = document.getElementById('comparison-matrix-grid');
    if (!selectorContainer || !matrixContainer) return;

    if (!this.documents || this.documents.length === 0) {
      matrixContainer.innerHTML = `
        <div style="text-align: center; padding: 48px 16px; color: var(--text-muted); font-family: var(--font-mono);">
          [ 0x00 // EMPTY ] Ingest at least two research papers in the Library to run comparative matrix analysis.
        </div>
      `;
      return;
    }

    // Default select first two papers if not already selected
    if (this.selectedDocs.length === 0 && this.documents.length >= 1) {
      this.selectedDocs = this.documents.slice(0, Math.min(2, this.documents.length)).map(d => d.filename);
    }

    // Render selector chips
    selectorContainer.innerHTML = this.documents.map(doc => {
      const isSelected = this.selectedDocs.includes(doc.filename);
      return `
        <button class="btn btn-sm ${isSelected ? 'btn-primary' : 'btn-outline'}" 
          onclick="ComparisonManager.toggleDoc('${escapeJs(doc.filename)}')">
          ${isSelected ? '✓ ' : '+ '}${escapeHtml(doc.filename)}
        </button>
      `;
    }).join('');

    // Render comparison columns
    const activePapers = this.documents.filter(d => this.selectedDocs.includes(d.filename));
    if (activePapers.length === 0) {
      matrixContainer.innerHTML = `
        <div style="text-align: center; padding: 32px; color: var(--text-muted);">
          Select one or more papers above to display the comparison matrix.
        </div>
      `;
      return;
    }

    matrixContainer.innerHTML = `
      <div style="display: grid; grid-template-columns: repeat(${activePapers.length}, minmax(300px, 1fr)); gap: var(--space-4);">
        ${activePapers.map((paper, idx) => `
          <div class="card" style="display: flex; flex-direction: column; gap: 14px; border-top: 3px solid ${idx === 0 ? 'var(--accent-primary)' : 'var(--accent-secondary)'};">
            <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px;">
              <div>
                <span class="label-technical">// PAPER ${String(idx + 1).padStart(2, '0')}</span>
                <h4 style="font-size: 15px; font-weight: 600; color: var(--text-primary); margin-top: 4px; word-break: break-word;">
                  ${escapeHtml(paper.filename)}
                </h4>
              </div>
              <button class="btn btn-sm btn-ghost" onclick="ComparisonManager.toggleDoc('${escapeJs(paper.filename)}')" title="Remove from comparison">✕</button>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-family: var(--font-mono); font-size: 11px; background: var(--bg-surface); padding: 8px 12px; border-radius: var(--radius-sm);">
              <div>
                <span style="color: var(--text-muted);">SIZE:</span>
                <span style="color: var(--text-primary);">${(paper.size / (1024 * 1024)).toFixed(2)} MB</span>
              </div>
              <div>
                <span style="color: var(--text-muted);">CHUNKS:</span>
                <span style="color: var(--accent-primary);">${paper.chunks || 0}</span>
              </div>
              <div>
                <span style="color: var(--text-muted);">STATUS:</span>
                <span style="color: ${paper.status === 'completed' ? 'var(--status-success)' : 'var(--text-muted)'};">${paper.status || 'uploaded'}</span>
              </div>
              <div>
                <span style="color: var(--text-muted);">DATE:</span>
                <span style="color: var(--text-secondary);">${new Date(paper.modified * 1000).toLocaleDateString()}</span>
              </div>
            </div>

            <div>
              <div class="label-technical" style="margin-bottom: 6px;">Extraction Modality</div>
              <p style="font-size: 12px; color: var(--text-secondary); line-height: 1.5;">
                Multimodal PDF parsed via MinerU OCR layout model. Tokenized into vector embedding space and synthesized into dual-level LightRAG entity-relation graph.
              </p>
            </div>

            <div style="margin-top: auto; padding-top: 10px; border-top: 1px solid var(--border-subtle); display: flex; gap: 8px;">
              <button class="btn btn-sm btn-outline" style="flex: 1;" onclick="LibraryManager.queryDoc('${escapeJs(paper.filename)}')">
                Analyze in Copilot →
              </button>
            </div>
          </div>
        `).join('')}
      </div>

      <div class="card" style="margin-top: var(--space-4); background: var(--bg-surface); border-left: 3px solid var(--accent-primary);">
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
          <div>
            <div class="label-technical" style="color: var(--accent-primary);">Comparative Research Synthesis</div>
            <div style="font-size: 13px; color: var(--text-primary); margin-top: 2px;">
              Run automated cross-paper synthesis across all ${activePapers.length} selected documents.
            </div>
          </div>
          <button class="btn btn-primary btn-sm" onclick="ComparisonManager.runCrossSynthesis()">
            Synthesize Methodology Differences →
          </button>
        </div>
      </div>
    `;
  },

  toggleDoc(filename) {
    const idx = this.selectedDocs.indexOf(filename);
    if (idx !== -1) {
      this.selectedDocs.splice(idx, 1);
    } else {
      if (this.selectedDocs.length >= 4) {
        Toast.show('Maximum 4 papers can be compared simultaneously', 'info');
        return;
      }
      this.selectedDocs.push(filename);
    }
    this.render();
  },

  runCrossSynthesis() {
    if (this.selectedDocs.length < 2) {
      Toast.show('Please select at least 2 papers to compare', 'info');
      return;
    }
    NavManager.switchTab('assistant');
    if (window.AssistantManager) {
      AssistantManager.setInputPrompt(`Compare and contrast the research methodology, key assumptions, and experimental findings between: ${this.selectedDocs.join(' and ')}.`);
    }
  }
};
