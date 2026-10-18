// LifeBoard — registers sw.js (see that file for the caching
// strategy). Loaded on every page; registration is a no-op on
// browsers without service worker support (older iOS Safari in
// non-standalone mode, etc.) — just skip silently.

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("LifeBoard: service worker registration failed", err);
    });
  });
}
