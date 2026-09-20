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
        const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        const rect = button.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
        root.style.setProperty('--theme-x', `${x}px`);
        root.style.setProperty('--theme-y', `${y}px`);
        root.style.setProperty('--theme-radius', `${radius}px`);

        if (!reducedMotion && document.startViewTransition) {
          document.startViewTransition(() => apply(next, true));
        } else {
          root.classList.add('theme-changing');
          apply(next, true);
          window.setTimeout(() => root.classList.remove('theme-changing'), 360);
        }
      });
    });
  });

  media.addEventListener?.('change', event => {
    if (!storedTheme()) apply(event.matches ? 'dark' : 'light');
  });
})();
