/**
 * SciGraph Main Application Bootstrapper
 * Coordinates themes, navigation, modules, and global notifications.
 */

// Global HTML sanitizers
function escapeHtml(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  }[tag] || tag));
}

function escapeJs(str) {
  if (typeof str !== 'string') return '';
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

// Global Toast System
const Toast = {
  show(message, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✓';
    else if (type === 'error') icon = '✕';

    const accentColor = type === 'success' 
      ? 'var(--accent-primary)' 
      : (type === 'error' ? 'var(--status-danger)' : 'var(--accent-secondary)');

    toast.innerHTML = `
      <span style="font-weight: 700; font-family: var(--font-mono); color: ${accentColor};">${icon}</span>
      <span style="flex: 1; font-size: 13px;">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(20px)';
      toast.style.transition = 'all 0.2s ease';
      setTimeout(() => toast.remove(), 200);
    }, duration);
  }
};

// Application Startup
document.addEventListener('DOMContentLoaded', async () => {
  console.log('Initializing SciGraph — Scientific Intelligence Workspace...');

  // 1. Theme Manager
  ThemeManager.init();

  // 2. Profile Manager
  await ProfileManager.init();

  // 3. Feature Managers (initialized before Navigation so route hooks resolve cleanly)
  DashboardManager.init();
  LibraryManager.init();
  AssistantManager.init();
  WorkspaceManager.init();
  GraphManager.init();
  if (window.LiveActivityManager) LiveActivityManager.init();
  SettingsManager.init();
  if (window.ComparisonManager) ComparisonManager.init();
  if (window.InsightsManager) InsightsManager.init();
  if (window.HistoryManager) HistoryManager.init();

  // 4. Navigation Manager (activates active tab from hash or defaults to overview)
  NavManager.init();

  // 5. Global Search & Command Hotkeys (Ctrl+K or "/")
  const globalSearch = document.getElementById('global-search-input');
  if (globalSearch) {
    globalSearch.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const query = globalSearch.value.trim();
        if (query) {
          NavManager.switchTab('library');
          const libInput = document.getElementById('library-search-input');
          if (libInput) {
            libInput.value = query;
            LibraryManager.searchQuery = query.toLowerCase();
            LibraryManager.render();
          }
        }
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    if ((e.key === '/' || (e.ctrlKey && e.key.toLowerCase() === 'k') || (e.metaKey && e.key.toLowerCase() === 'k')) &&
        document.activeElement.tagName !== 'INPUT' && 
        document.activeElement.tagName !== 'TEXTAREA') {
      e.preventDefault();
      if (globalSearch) globalSearch.focus();
    }
  });

  console.log('SciGraph Ready.');
});
