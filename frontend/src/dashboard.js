// LifeBoard — responsive dashboard grid + independent per-widget poll
// loops. Per docs/ARCHITECTURE.md: "Dashboard polls /api/modules/{id}/data
// every refresh_seconds... using independent setIntervals per widget —
// one slow module never blocks others."

const Dashboard = {
  _pollTimers: {},
  _cardElements: {},
  _manifests: {},

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
    this._manifests = manifests;

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
      card.draggable = true;
      grid.appendChild(card);
      this._cardElements[entry.module_id] = card;

      // Per Phase 4: per-module refresh override from the saved layout
      // takes priority over the manifest default (config_panel.js lets
      // the user set this per module, not just accept the manifest's
      // default_refresh_seconds).
      const refreshSeconds = entry.refresh_seconds || manifest.default_refresh_seconds || 30;
      this._startPolling(entry.module_id, Math.max(1, refreshSeconds));
    }

    this._wireDragReorder(grid);
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

    const manifest = this._manifests[moduleId];
    if (manifest && manifest.requires_integration && data && !data.error) {
      data._integrationStatus = {
        last_synced_at: manifest.integration_last_synced_at,
        last_error: manifest.integration_last_error,
      };
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

  // Per Phase 4: persisted drag-to-reposition grid layout. HTML5 drag
  // events on each card; on drop, re-derive each enabled module's
  // position from DOM order and persist via POST /api/dashboard.
  _wireDragReorder(grid) {
    let draggedId = null;

    grid.querySelectorAll(".card").forEach((card) => {
      card.addEventListener("dragstart", () => {
        draggedId = card.dataset.moduleId;
        card.style.opacity = "0.4";
      });
      card.addEventListener("dragend", () => {
        card.style.opacity = "";
      });
      card.addEventListener("dragover", (event) => {
        event.preventDefault();
      });
      card.addEventListener("drop", async (event) => {
        event.preventDefault();
        if (!draggedId || draggedId === card.dataset.moduleId) return;

        const cards = Array.from(grid.querySelectorAll(".card"));
        const draggedEl = this._cardElements[draggedId];
        const targetIndex = cards.indexOf(card);
        const draggedIndex = cards.indexOf(draggedEl);

        if (draggedIndex < targetIndex) {
          card.after(draggedEl);
        } else {
          card.before(draggedEl);
        }

        await this._persistCurrentOrder(grid);
      });
    });
  },

  async _persistCurrentOrder(grid) {
    const layoutResponse = await Api.get("/api/dashboard");
    const layout = layoutResponse.modules || [];
    const layoutById = {};
    for (const entry of layout) {
      layoutById[entry.module_id] = entry;
    }

    const orderedIds = Array.from(grid.querySelectorAll(".card")).map((card) => card.dataset.moduleId);
    orderedIds.forEach((moduleId, index) => {
      if (layoutById[moduleId]) {
        layoutById[moduleId].position = index;
      }
    });

    await Api.post("/api/dashboard", { modules: layout });
  },
};
