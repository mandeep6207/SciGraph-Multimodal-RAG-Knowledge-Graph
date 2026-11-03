/**
 * SciGraph 3D Knowledge Graph Engine
 * Emerald Signature Art Direction with UnrealBloom, Directional Luminous Particles,
 * Planetary Targeting Rings, Scientific Ambient Dust, and Physics Sliders.
 */

const TYPE_COLORS = {
  concept: '#B5F36B',       // SciGraph signature emerald-lime
  entity: '#6EAA85',        // Neural sage green
  method: '#98D977',        // Botanical green
  task: '#D9A65A',          // Amber
  metric: '#52B788',        // Mint green
  dataset: '#E9E8DF',       // Warm ivory
  finding: '#74C69D',       // Soft sage
  document: '#D8F3DC',      // Pale ivory green
  author: '#81B29A',        // Slate sage
  person: '#95D5B2',        // Seafoam
  organization: '#B7E4C7',  // Soft jade
  location: '#A3B18A',      // Olive sage
  category: '#E07A5F',      // Muted coral
  chunk: '#588157',         // Forest sage
  relation: '#738276',      // Slate wire
  unknown: '#929B91',       // Muted text
  discarded: '#2D372E'      // Deep muted
};

const GraphManager = {
  graph: null,
  fullGraphData: { nodes: [], links: [] },
  graphData: { nodes: [], links: [] },
  selectedNode: null,
  selectedNodeTypes: new Set(),
  persistentHiddenTypes: new Set(['discarded']),
  
  // Physics & Limits
  graphNodeLimit: 300,
  graphLinkDistance: 60,
  graphNodeRepulsion: 120,

  init() {
    this.bindControls();
  },

  initOrResize() {
    if (!this.graph) {
      this.initGraph();
    } else {
      this.onResize();
    }
  },

  async initGraph() {
    const el = document.getElementById('3d-graph');
    if (!el) return;

    this.setLoading(true, 'Querying Scientific Knowledge Graph...');

    try {
      const data = await API.getGraph(this.graphNodeLimit);
      this.fullGraphData = (data && Array.isArray(data.nodes)) ? data : { nodes: [], links: [] };
      if (!this.fullGraphData.nodes || this.fullGraphData.nodes.length === 0) {
        this.setLoading(false);
        this.updateHudStats();
        el.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-secondary);font-family:var(--font-mono);text-align:center;padding:24px;">
            <div style="max-width:420px;background:rgba(21,29,24,0.9);border:1px solid rgba(181,243,107,0.2);border-radius:10px;padding:28px;">
              <div style="font-size:28px;margin-bottom:12px;color:var(--accent-primary);">◈</div>
              <div style="font-size:16px;font-weight:600;color:var(--text-primary);margin-bottom:8px;">No Graph Entities Found</div>
              <div style="font-size:12px;color:var(--text-muted);line-height:1.6;margin-bottom:16px;">
                Upload research documents in the Research Library to extract scientific entities and relationships.
              </div>
              <button class="btn btn-primary btn-sm" onclick="NavManager.switchTab('library')">
                Go to Research Library →
              </button>
            </div>
          </div>`;
        return;
      }
      this.applyFiltersAndRender();
    } catch (err) {
      console.error('Failed to load graph data:', err);
      this.setLoading(false);
      el.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#E05D52;font-family:var(--font-mono);text-align:center;padding:20px;">
          <div>
            <div style="font-size:22px;margin-bottom:8px;">⚠️ Graph Data Offline</div>
            <div style="color:var(--text-muted);font-size:13px;">${escapeHtml(err.message)}</div>
          </div>
        </div>`;
    }
  },

  setLoading(show, message = 'Loading Graph...') {
    const overlay = document.getElementById('graph-loading-overlay');
    const msgEl = document.getElementById('graph-loading-msg');
    if (overlay) overlay.style.display = show ? 'flex' : 'none';
    if (msgEl) msgEl.textContent = message;
  },

  hexToRgba(hex, alpha = 0.6) {
    if (!hex) return `rgba(181, 243, 107, ${alpha})`;
    if (hex.startsWith('rgba')) return hex;
    let c = hex.replace('#', '');
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    if (c.length === 6) {
      const num = parseInt(c, 16);
      return `rgba(${(num >> 16) & 255}, ${(num >> 8) & 255}, ${num & 255}, ${alpha})`;
    }
    return `rgba(181, 243, 107, ${alpha})`;
  },

  defaultLinkColor(l) {
    const srcId = l.source?.id || l.source;
    const srcNode = (this.graphData?.nodes || []).find(n => n.id === srcId);
    const col = srcNode ? (TYPE_COLORS[srcNode.type] || '#B5F36B') : '#B5F36B';
    return this.hexToRgba(col, 0.40);
  },

  defaultLinkArrowColor(l) {
    const srcId = l.source?.id || l.source;
    const srcNode = (this.graphData?.nodes || []).find(n => n.id === srcId);
    return srcNode ? (TYPE_COLORS[srcNode.type] || '#B5F36B') : '#B5F36B';
  },

  applyFiltersAndRender() {
    const hiddenTypes = new Set(this.persistentHiddenTypes);
    const hasTypeFilter = this.selectedNodeTypes.size > 0;

    const filteredNodes = (this.fullGraphData.nodes || []).filter(n => {
      const type = (n.type || 'concept').toLowerCase();
      if (hiddenTypes.has(type)) return false;
      if (hasTypeFilter && !this.selectedNodeTypes.has(type)) return false;
      return true;
    });

    const validNodeIds = new Set(filteredNodes.map(n => n.id));
    const filteredLinks = (this.fullGraphData.links || []).filter(l => {
      const s = l.source?.id || l.source;
      const t = l.target?.id || l.target;
      return validNodeIds.has(s) && validNodeIds.has(t);
    });

    this.graphData = { nodes: filteredNodes, links: filteredLinks };
    this.renderGraph(this.graphData);
    this.updateLegend();
    this.updateHudStats();
    this.setLoading(false);
  },

  renderGraph(data) {
    const el = document.getElementById('3d-graph');
    if (!el) return;
    el.innerHTML = '';

    const FG3D = window.ForceGraph3D || (typeof ForceGraph3D !== 'undefined' ? ForceGraph3D : null);
    if (!FG3D) {
      el.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:center;height:100%;color:#E05D52;font-family:var(--font-mono);text-align:center;">
          ForceGraph3D library not found.
        </div>`;
      return;
    }

    const degreeMap = {};
    data.links.forEach(l => {
      const s = l.source?.id || l.source;
      const t = l.target?.id || l.target;
      degreeMap[s] = (degreeMap[s] || 0) + 1;
      degreeMap[t] = (degreeMap[t] || 0) + 1;
    });
    data.nodes.forEach(n => { n.degree = degreeMap[n.id] || 1; });
    const maxDeg = Math.max(...data.nodes.map(n => n.degree), 1);

    window.hoverLinks = null;
    let hoverNode = null;

    this.graph = FG3D({ antialias: true, alpha: false })(el)
      .backgroundColor('#090C0A')
      .showNavInfo(false)

      // Nodes
      .nodeColor(n => TYPE_COLORS[n.type] || '#929B91')
      .nodeVal(n => 0.5 + (n.degree / maxDeg) * 3)
      .nodeOpacity(0.95)
      .nodeResolution(20)

      // Hover Tooltip
      .nodeLabel(n => `
        <div style="background: rgba(16, 22, 18, 0.96); border: 1px solid ${TYPE_COLORS[n.type] || '#B5F36B'}88; border-radius: 6px; padding: 8px 12px; font-family: var(--font-mono); font-size: 11px; color: #E9E8DF; max-width: 250px; box-shadow: 0 4px 20px rgba(0,0,0,0.8);">
          <strong style="color:${TYPE_COLORS[n.type] || '#B5F36B'}; font-size:12px;">${escapeHtml(n.id)}</strong><br>
          <span style="color:var(--text-muted); font-size: 10px;">${n.type || 'concept'} · ${n.degree || 1} links</span>
          ${n.desc ? `<br><span style="color:#C3C9C1; font-size:10px;">${escapeHtml(n.desc.slice(0, 90))}…</span>` : ''}
        </div>
      `)

      // Glowing Links & Arcs
      .linkCurvature(0.16)
      .linkCurveRotation(0.25)
      .linkColor(l => {
        if (window.hoverLinks && window.hoverLinks.has(l)) return '#B5F36B';
        return this.defaultLinkColor(l);
      })
      .linkWidth(l => (window.hoverLinks && window.hoverLinks.has(l) ? 3.0 : 1.4))
      .linkOpacity(0.85)
      .linkDirectionalArrowLength(4.0)
      .linkDirectionalArrowRelPos(0.95)
      .linkDirectionalArrowColor(l => this.defaultLinkArrowColor(l))

      // Custom 3D Glossy Node Meshes with Floating SpriteText
      .nodeThreeObjectExtend(false)
      .nodeThreeObject(node => {
        const group = new THREE.Group();
        const color = TYPE_COLORS[node.type] || '#929B91';
        const size = 1.3 + (node.degree * 0.16);

        // Glossy sphere with emissive neon glow
        const geo = new THREE.SphereGeometry(size, 24, 24);
        const mat = new THREE.MeshPhongMaterial({
          color: color,
          emissive: color,
          emissiveIntensity: 0.22,
          shininess: 90
        });
        const mesh = new THREE.Mesh(geo, mat);
        group.add(mesh);

        // Floating labels for prominent nodes
        if (node.degree >= 3 && typeof SpriteText === 'function') {
          const sprite = new SpriteText(node.id);
          sprite.color = 'rgba(233, 232, 223, 0.90)';
          sprite.textHeight = 3.2 + (node.degree * 0.04);
          sprite.position.y = size + 4.5;
          group.add(sprite);
        }

        return group;
      })

      // Flowing directional particles
      .linkDirectionalParticles(l => (window.hoverLinks && window.hoverLinks.has(l) ? 4 : 2))
      .linkDirectionalParticleWidth(2.2)
      .linkDirectionalParticleSpeed(0.006)
      .linkDirectionalParticleColor(l => {
        const srcId = l.source?.id || l.source;
        const srcNode = (this.graphData?.nodes || []).find(n => n.id === srcId);
        return srcNode ? (TYPE_COLORS[srcNode.type] || '#B5F36B') : '#B5F36B';
      })

      // Node Click Shockwave & Targeting Ring
      .onNodeClick(node => this.handleNodeClick(node))

      // Node Hover Neighborhood
      .onNodeHover(node => this.handleNodeHover(node, el))

      .onBackgroundClick(() => this.restoreColors())
      .graphData(data);

    // Forces
    this.graph.d3Force('charge').strength(-this.graphNodeRepulsion);
    this.graph.d3Force('link').distance(this.graphLinkDistance).strength(0.18);

    // UnrealBloom Glow Post-Processing
    if (typeof THREE.UnrealBloomPass === 'function' && this.graph.postProcessingComposer) {
      try {
        const bloomPass = new THREE.UnrealBloomPass(
          new THREE.Vector2(window.innerWidth, window.innerHeight),
          1.1, 1.0, 0.12
        );
        this.graph.postProcessingComposer().addPass(bloomPass);
      } catch (e) {
        console.warn('Bloom effect skipped:', e);
      }
    }

    // Ambient 3D Data Dust Particles
    const dustGeometry = new THREE.BufferGeometry();
    const dustCount = 600;
    const positions = new Float32Array(dustCount * 3);
    for (let i = 0; i < dustCount * 3; i++) {
      positions[i] = (Math.random() - 0.5) * 1600;
    }
    dustGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const dustMaterial = new THREE.PointsMaterial({
      color: '#6EAA85',
      size: 1.5,
      transparent: true,
      opacity: 0.28
    });
    const dustMesh = new THREE.Points(dustGeometry, dustMaterial);
    this.graph.scene().add(dustMesh);

    this.onResize();
  },

  handleNodeClick(node) {
    this.selectedNode = node;
    this.showNodeDetails(node);

    // Smooth camera zoom
    const dist = 75;
    this.graph.cameraPosition(
      { x: node.x + dist, y: node.y + dist * 0.4, z: node.z + dist },
      node,
      900
    );

    // Shockwave expansion animation
    const shockGeo = new THREE.SphereGeometry(1, 24, 24);
    const shockMat = new THREE.MeshBasicMaterial({
      color: TYPE_COLORS[node.type] || '#B5F36B',
      transparent: true,
      opacity: 0.6,
      wireframe: true
    });
    const shockMesh = new THREE.Mesh(shockGeo, shockMat);
    shockMesh.position.set(node.x, node.y, node.z);
    this.graph.scene().add(shockMesh);

    let progress = 0;
    const shockAnim = () => {
      progress += 0.05;
      const s = 1 + progress * 24;
      shockMesh.scale.set(s, s, s);
      shockMat.opacity = Math.max(0, 0.6 * (1 - progress));
      if (progress < 1) {
        requestAnimationFrame(shockAnim);
      } else {
        this.graph.scene().remove(shockMesh);
      }
    };
    shockAnim();

    // Planetary Targeting Ring
    if (window.activeTargetRing) {
      this.graph.scene().remove(window.activeTargetRing);
    }
    const ringGeo = new THREE.RingGeometry(3.5, 3.9, 32);
    const ringMat = new THREE.MeshBasicMaterial({
      color: '#B5F36B',
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.8
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.position.set(node.x, node.y, node.z);
    ringMesh.lookAt(this.graph.camera().position);
    this.graph.scene().add(ringMesh);
    window.activeTargetRing = ringMesh;
  },

  handleNodeHover(node, el) {
    el.style.cursor = node ? 'pointer' : 'default';
    if (!node) {
      if (!this.selectedNode) {
        this.restoreColors();
      }
      return;
    }

    const neighborIds = new Set([node.id]);
    const connected = new Set();
    this.graphData.links.forEach(l => {
      const s = l.source?.id || l.source;
      const t = l.target?.id || l.target;
      if (s === node.id || t === node.id) {
        neighborIds.add(s);
        neighborIds.add(t);
        connected.add(l);
      }
    });
    window.hoverLinks = connected;

    this.graph.nodeColor(n =>
      neighborIds.has(n.id)
        ? (TYPE_COLORS[n.type] || '#929B91')
        : this.hexToRgba(TYPE_COLORS[n.type] || '#929B91', 0.2)
    );
    this.graph.linkColor(l => (connected.has(l) ? '#B5F36B' : 'rgba(190, 220, 190, 0.06)'));
    this.graph.linkWidth(l => (connected.has(l) ? 3.0 : 0.8));
  },

  restoreColors() {
    this.selectedNode = null;
    window.hoverLinks = null;
    if (window.activeTargetRing && this.graph) {
      this.graph.scene().remove(window.activeTargetRing);
      window.activeTargetRing = null;
    }
    if (this.graph) {
      this.graph.nodeColor(n => TYPE_COLORS[n.type] || '#929B91');
      this.graph.linkColor(l => this.defaultLinkColor(l));
      this.graph.linkWidth(1.4);
    }
    const drawer = document.getElementById('graph-node-drawer');
    if (drawer) drawer.classList.remove('open');
  },

  showNodeDetails(node) {
    const drawer = document.getElementById('graph-node-drawer');
    if (!drawer) return;

    drawer.classList.add('open');
    document.getElementById('node-drawer-id').textContent = node.id;
    document.getElementById('node-drawer-type').textContent = node.type || 'concept';
    document.getElementById('node-drawer-type').style.background = this.hexToRgba(TYPE_COLORS[node.type] || '#B5F36B', 0.16);
    document.getElementById('node-drawer-type').style.color = TYPE_COLORS[node.type] || '#B5F36B';
    document.getElementById('node-drawer-degree').textContent = `${node.degree || 1} connections`;
    document.getElementById('node-drawer-desc').textContent = node.desc || 'No summary extracted for this entity.';
  },

  updateHudStats() {
    const elNodes = document.getElementById('graph-hud-nodes');
    const elLinks = document.getElementById('graph-hud-links');
    if (elNodes) elNodes.textContent = this.graphData.nodes.length;
    if (elLinks) elLinks.textContent = this.graphData.links.length;
  },

  updateLegend() {
    const container = document.getElementById('graph-legend-container');
    if (!container) return;

    const typeCounts = {};
    (this.fullGraphData.nodes || []).forEach(n => {
      if (!this.persistentHiddenTypes.has(n.type)) {
        typeCounts[n.type] = (typeCounts[n.type] || 0) + 1;
      }
    });

    container.innerHTML = Object.entries(typeCounts).map(([type, count]) => {
      const color = TYPE_COLORS[type] || '#B5F36B';
      const isSelected = this.selectedNodeTypes.has(type);
      return `
        <div class="legend-chip ${isSelected ? 'active' : ''}" onclick="GraphManager.toggleTypeFilter('${type}')" style="cursor:pointer; display:inline-flex; align-items:center; gap:6px; padding:3px 9px; border-radius:4px; font-size:11px; font-family:var(--font-mono); background:${isSelected ? color : 'rgba(255,255,255,0.05)'}; color:${isSelected ? '#090C0A' : '#E9E8DF'}; border:1px solid ${isSelected ? color : 'rgba(190,220,190,0.12)'}; margin:2px;">
          <span style="width:7px; height:7px; border-radius:50%; background:${color}; box-shadow:0 0 6px ${color};"></span>
          <span>${type} (${count})</span>
        </div>
      `;
    }).join('');
  },

  toggleTypeFilter(type) {
    if (this.selectedNodeTypes.has(type)) {
      this.selectedNodeTypes.delete(type);
    } else {
      this.selectedNodeTypes.add(type);
    }
    this.applyFiltersAndRender();
  },

  onResize() {
    const container = document.getElementById('3d-graph');
    if (this.graph && container) {
      this.graph.width(container.clientWidth);
      this.graph.height(container.clientHeight);
    }
  },

  bindControls() {
    const closeBtn = document.getElementById('close-node-drawer');
    if (closeBtn) closeBtn.addEventListener('click', () => this.restoreColors());

    const resetBtn = document.getElementById('graph-btn-reset');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (this.graph) {
          this.graph.zoomToFit(800, 40);
        }
      });
    }

    // Sliders
    const limitSlider = document.getElementById('graph-slider-limit');
    if (limitSlider) {
      limitSlider.addEventListener('change', async (e) => {
        this.graphNodeLimit = parseInt(e.target.value);
        document.getElementById('graph-val-limit').textContent = this.graphNodeLimit;
        this.setLoading(true);
        const data = await API.getGraph(this.graphNodeLimit);
        this.fullGraphData = data;
        this.applyFiltersAndRender();
      });
    }

    const distSlider = document.getElementById('graph-slider-distance');
    if (distSlider) {
      distSlider.addEventListener('input', (e) => {
        this.graphLinkDistance = parseInt(e.target.value);
        document.getElementById('graph-val-distance').textContent = this.graphLinkDistance;
        if (this.graph) {
          this.graph.d3Force('link').distance(this.graphLinkDistance);
          this.graph.d3ReheatSimulation();
        }
      });
    }

    const repSlider = document.getElementById('graph-slider-repulsion');
    if (repSlider) {
      repSlider.addEventListener('input', (e) => {
        this.graphNodeRepulsion = parseInt(e.target.value);
        document.getElementById('graph-val-repulsion').textContent = this.graphNodeRepulsion;
        if (this.graph) {
          this.graph.d3Force('charge').strength(-this.graphNodeRepulsion);
          this.graph.d3ReheatSimulation();
        }
      });
    }

    // Search Node
    const searchInput = document.getElementById('graph-search-input');
    if (searchInput) {
      let timeout;
      searchInput.addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(async () => {
          const term = e.target.value.trim();
          this.setLoading(true);
          const data = await API.getGraph(this.graphNodeLimit, term);
          this.fullGraphData = data;
          this.applyFiltersAndRender();
        }, 300);
      });
    }
  }
};
