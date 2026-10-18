// LifeBoard — service worker for "Add to Home Screen" offline shell
// caching. Per the Phase 6 plan item: "Real offline/installable PWA
// behavior (service worker caching real data, not just shell)."
//
// Strategy:
// - App shell (HTML/CSS/JS/icons/manifest): cache-first, so the UI
//   itself loads instantly even with zero connectivity — a stale shell
//   is still useful, and these files only change on a deploy.
// - API calls (/api/*): network-first with a cache fallback. Live data
//   is always preferred when reachable; if the network is down, the
//   last successfully fetched response for that exact URL is served
//   instead of a hard failure, so a card can show "the last reading we
//   had" rather than going blank. This is real cached data, not just
//   the app shell — per the plan's explicit "not just shell" ask.
// - Auth endpoints (setup/login/logout/account) are never cached —
//   serving a stale 200 for a login POST would be actively wrong.

const SHELL_CACHE = "lifeboard-shell-v1";
const API_CACHE = "lifeboard-api-v1";

const SHELL_URLS = [
  "/",
  "/login.html",
  "/setup.html",
  "/account.html",
  "/admin/integrations.html",
  "/manifest.json",
  "/icons/icon.svg",
  "/src/style.css",
  "/src/theme.js",
  "/src/api.js",
  "/src/main.js",
  "/src/dashboard.js",
  "/src/config_panel.js",
  "/src/login.js",
  "/src/setup.js",
  "/src/account.js",
  "/src/widgets/registry.js",
  "/src/widgets/generic.js",
  "/src/widgets/clock.js",
  "/src/widgets/nutrition.js",
  "/src/admin/integrations.js",
];

const NEVER_CACHE_API_PREFIXES = [
  "/api/setup",
  "/api/login",
  "/api/logout",
  "/api/account/",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== SHELL_CACHE && key !== API_CACHE)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

function isNeverCachedApiPath(pathname) {
  return NEVER_CACHE_API_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (event.request.method !== "GET") {
    return; // never intercept POST/DELETE — always hit the network
  }

  if (url.pathname.startsWith("/api/")) {
    if (isNeverCachedApiPath(url.pathname)) {
      return; // let auth endpoints pass straight through, uncached
    }
    event.respondWith(networkFirstWithCacheFallback(event.request));
    return;
  }

  event.respondWith(cacheFirstWithNetworkFallback(event.request));
});

async function cacheFirstWithNetworkFallback(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(SHELL_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    // Shell asset not cached and network unreachable — nothing we can
    // do, let the browser surface its own offline error for this one.
    throw err;
  }
}

async function networkFirstWithCacheFallback(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}
