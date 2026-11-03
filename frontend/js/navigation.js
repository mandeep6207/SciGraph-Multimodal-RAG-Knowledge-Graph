/**
 * SciGraph Navigation Manager
 * Collapsible sidebar, active tab routing, and responsive mobile handling.
 */
const NavManager = {
  currentTab: 'overview',
  STORAGE_SIDEBAR_KEY: 'scigraph_sidebar_collapsed',

  routes: {
    'overview': { title: 'Research Overview', breadcrumb: 'Intelligence / Overview' },
    'library': { title: 'Research Library', breadcrumb: 'Corpus / Research Library' },
    'graph': { title: 'Knowledge Graph', breadcrumb: 'Exploration / Knowledge Network' },
    'assistant': { title: 'Research Copilot', breadcrumb: 'Intelligence / Research Copilot' },
    'copilot': { title: 'Research Copilot', breadcrumb: 'Intelligence / Research Copilot' },
    'comparison': { title: 'Paper Comparison Matrix', breadcrumb: 'Analysis / Paper Comparison' },
    'insights': { title: 'Research Insights', breadcrumb: 'Synthesis / Research Insights' },
    'live-activity': { title: 'Research History', breadcrumb: 'Tools / Query History' },
    'workspaces': { title: 'My Workspaces', breadcrumb: 'RAG Management / Workspaces' },
    'new-rag': { title: 'New Workspace', breadcrumb: 'RAG Management / New RAG' },
    'collections': { title: 'Document Collections', breadcrumb: 'RAG Management / Collections' },
    'import': { title: 'Import & Pipeline', breadcrumb: 'Tools / Ingestion Pipeline' },
    'history': { title: 'Research History', breadcrumb: 'Tools / Query History' },
    'settings': { title: 'Workspace Settings', breadcrumb: 'Preferences / Settings' },
    'help': { title: 'Help & Documentation', breadcrumb: 'Support / Documentation' },
    'profile': { title: 'User Profile', breadcrumb: 'Account / Mandeep Kumar' },
  },

  init() {
    this.initSidebarCollapse();
    this.bindNavigationClicks();
    
    // Check URL hash or default
    const hash = window.location.hash.replace('#', '');
    if (hash && this.routes[hash]) {
      this.switchTab(hash);
    } else {
      this.switchTab('overview');
    }
  },

  initSidebarCollapse() {
    const sidebar = document.getElementById('sidebar');
    const toggleBtn = document.getElementById('sidebar-collapse-btn');
    if (!sidebar || !toggleBtn) return;

    // Restore saved state
    const isCollapsed = localStorage.getItem(this.STORAGE_SIDEBAR_KEY) === 'true';
    if (isCollapsed) {
      sidebar.classList.add('collapsed');
    }

    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('collapsed');
      const collapsed = sidebar.classList.contains('collapsed');
      localStorage.setItem(this.STORAGE_SIDEBAR_KEY, collapsed);
      // Trigger graph resize if on graph tab
      if (this.currentTab === 'graph' && window.GraphManager) {
        setTimeout(() => GraphManager.onResize(), 220);
      }
    });
  },

  bindNavigationClicks() {
    document.querySelectorAll('[data-nav]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = el.getAttribute('data-nav');
        if (tab) {
          this.switchTab(tab);
        }
      });
    });
  },

  switchTab(tabId) {
    // Alias copilot to assistant if necessary
    const targetPanelId = tabId === 'copilot' ? 'assistant' : tabId;
    if (!this.routes[tabId]) return;
    this.currentTab = tabId;
    window.location.hash = tabId;

    // Update active nav links
    document.querySelectorAll('[data-nav]').forEach(el => {
      const navTarget = el.getAttribute('data-nav');
      if (navTarget === tabId || (tabId === 'assistant' && navTarget === 'copilot') || (tabId === 'copilot' && navTarget === 'assistant')) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });

    // Update Top Header Title & Breadcrumb
    const route = this.routes[tabId];
    const titleEl = document.getElementById('page-header-title');
    const breadcrumbEl = document.getElementById('page-header-breadcrumb');
    if (titleEl) titleEl.textContent = route.title;
    if (breadcrumbEl) breadcrumbEl.textContent = route.breadcrumb;

    // Switch visible panel
    document.querySelectorAll('.panel').forEach(panel => {
      panel.classList.remove('active');
    });

    const activePanel = document.getElementById(`panel-${targetPanelId}`);
    if (activePanel) {
      activePanel.classList.add('active');
    }

    // Trigger tab-specific refresh
    this.onTabActivated(tabId);
  },

  onTabActivated(tabId) {
    if (tabId === 'overview' && window.DashboardManager) {
      DashboardManager.refresh();
    } else if (tabId === 'library' && window.LibraryManager) {
      LibraryManager.refresh();
    } else if (tabId === 'graph' && window.GraphManager) {
      GraphManager.initOrResize();
    } else if (tabId === 'workspaces' && window.WorkspaceManager) {
      WorkspaceManager.refresh();
    } else if ((tabId === 'assistant' || tabId === 'copilot') && window.AssistantManager) {
      AssistantManager.onFocus();
    } else if (tabId === 'live-activity' && window.LiveActivityManager) {
      LiveActivityManager.connect();
    } else if (tabId === 'comparison' && window.ComparisonManager) {
      ComparisonManager.refresh();
    } else if (tabId === 'insights' && window.InsightsManager) {
      InsightsManager.refresh();
    }
  }
};
