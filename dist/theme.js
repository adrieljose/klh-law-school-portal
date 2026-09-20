'use strict';
(function () {
  const key = 'klh-theme-v1';
  const root = document.documentElement;
  const media = window.matchMedia('(prefers-color-scheme: dark)');

  function storedTheme() {
    try {
      const value = localStorage.getItem(key);
      return value === 'light' || value === 'dark' ? value : null;
    } catch {
      return null;
    }
  }

  function apply(theme, persist = false) {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    if (persist) {
      try { localStorage.setItem(key, theme); } catch {}
    }
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      const next = theme === 'dark' ? 'light' : 'dark';
      button.setAttribute('aria-label', `Switch to ${next} mode`);
      button.setAttribute('title', `Switch to ${next} mode`);
      button.setAttribute('aria-pressed', String(theme === 'dark'));
      const label = button.querySelector('.theme-label');
      if (label) label.textContent = theme === 'dark' ? 'Light' : 'Dark';
    });
  }

  apply(storedTheme() || (media.matches ? 'dark' : 'light'));

  document.addEventListener('DOMContentLoaded', () => {
    apply(root.dataset.theme || 'light');
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.addEventListener('click', () => {
        apply(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
      });
    });
  });

  media.addEventListener?.('change', event => {
    if (!storedTheme()) apply(event.matches ? 'dark' : 'light');
  });
})();
