// LifeBoard — dark/light theme toggle (Phase 4). Applies a
// data-theme attribute on <html> as early as possible (this script is
// loaded in <head>, before body paint, to avoid a flash of the wrong
// theme) and persists the user's explicit choice in localStorage —
// deliberately not following prefers-color-scheme, so a toggle click
// always wins over the OS setting.

(function () {
  const STORAGE_KEY = "lifeboard-theme";

  function applyTheme(theme) {
    if (theme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  }

  const saved = localStorage.getItem(STORAGE_KEY) || "dark";
  applyTheme(saved);

  window.Theme = {
    get() {
      return localStorage.getItem(STORAGE_KEY) || "dark";
    },
    toggle() {
      const next = this.get() === "light" ? "dark" : "light";
      localStorage.setItem(STORAGE_KEY, next);
      applyTheme(next);
      return next;
    },
  };

  // Wires up a #theme-toggle-btn if the page has one — self-contained
  // so every page that includes this script gets a working toggle
  // without needing its own page-specific JS to call Theme.toggle().
  document.addEventListener("DOMContentLoaded", () => {
    const button = document.getElementById("theme-toggle-btn");
    if (!button) return;

    function syncIcon() {
      button.textContent = window.Theme.get() === "light" ? "☀️" : "🌙";
    }
    syncIcon();
    button.addEventListener("click", () => {
      window.Theme.toggle();
      syncIcon();
    });
  });
})();
