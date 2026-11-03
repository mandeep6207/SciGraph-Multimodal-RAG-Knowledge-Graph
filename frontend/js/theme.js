/**
 * SciGraph Theme Switcher
 * Supports dark and light themes with instant zero-flash switching.
 */
const ThemeManager = {
  STORAGE_KEY: 'scigraph_theme',

  init() {
    const saved = localStorage.getItem(this.STORAGE_KEY);
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initial = saved || (systemDark ? 'dark' : 'light');
    this.setTheme(initial);

    // Bind theme toggles
    document.querySelectorAll('.theme-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => this.toggle());
    });

    // Listen to OS changes if no manual override
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      if (!localStorage.getItem(this.STORAGE_KEY)) {
        this.setTheme(e.matches ? 'dark' : 'light');
      }
    });
  },

  getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  },

  setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(this.STORAGE_KEY, theme);
    this.updateIcons(theme);
  },

  toggle() {
    const next = this.getTheme() === 'dark' ? 'light' : 'dark';
    this.setTheme(next);
  },

  updateIcons(theme) {
    document.querySelectorAll('.theme-icon-sun').forEach(el => {
      el.style.display = theme === 'dark' ? 'block' : 'none';
    });
    document.querySelectorAll('.theme-icon-moon').forEach(el => {
      el.style.display = theme === 'light' ? 'block' : 'none';
    });
  }
};
