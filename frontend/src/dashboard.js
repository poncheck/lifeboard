// LifeBoard — responsive dashboard grid + independent per-widget poll
// loops. Per docs/ARCHITECTURE.md: "Dashboard polls /api/modules/{id}/data
// every refresh_seconds... using independent setIntervals per widget —
// one slow module never blocks others."

const Dashboard = {
  _pollTimers: {},
  _cardElements: {},

  async render() {
    this._stopAllPolling();

    const grid = document.getElementById("dashboard-grid");
    const emptyState = document.getElementById("empty-state");
    grid.innerHTML = "";

    const [layoutResponse, modulesResponse] = await Promise.all([
      Api.get("/api/dashboard"),
      Api.get("/api/modules"),
    ]);

    const layout = layoutResponse.modules || [];
    const manifests = modulesResponse || {};

    const enabled = layout
      .filter((entry) => entry.enabled && manifests[entry.module_id])
      .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

    if (enabled.length === 0) {
      emptyState.hidden = false;
      return;
    }
    emptyState.hidden = true;

    for (const entry of enabled) {
      const manifest = manifests[entry.module_id];
      const card = document.createElement("div");
      card.className = `card grid-${manifest.grid_size || "1x1"}`;
      card.dataset.moduleId = entry.module_id;
      grid.appendChild(card);
      this._cardElements[entry.module_id] = card;

      const refreshSeconds = entry.refresh_seconds || manifest.default_refresh_seconds || 30;
      this._startPolling(entry.module_id, Math.max(1, refreshSeconds));
    }
  },

  async _fetchAndRenderOnce(moduleId) {
    const card = this._cardElements[moduleId];
    if (!card) return;

    let data;
    try {
      data = await Api.get(`/api/modules/${moduleId}/data`);
    } catch (err) {
      data = { error: err.message };
    }

    const renderer = WidgetRegistry.getRenderer(moduleId);
    renderer.render(card, data);
  },

  _startPolling(moduleId, refreshSeconds) {
    // Fire immediately, then on its own independent interval — a slow
    // or down module's poll must never block another widget's.
    this._fetchAndRenderOnce(moduleId);
    this._pollTimers[moduleId] = setInterval(() => {
      this._fetchAndRenderOnce(moduleId);
    }, refreshSeconds * 1000);
  },

  _stopAllPolling() {
    for (const moduleId of Object.keys(this._pollTimers)) {
      clearInterval(this._pollTimers[moduleId]);
      const card = this._cardElements[moduleId];
      const renderer = WidgetRegistry.getRenderer(moduleId);
      if (card && renderer.cleanup) {
        renderer.cleanup(card);
      }
    }
    this._pollTimers = {};
    this._cardElements = {};
  },
};
