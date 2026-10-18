// LifeBoard — config panel: checkbox list of discovered modules
// (greyed out if requires_integration isn't satisfied), toggle on/off,
// POST /api/dashboard to persist. Per docs/ARCHITECTURE.md.

const ConfigPanel = {
  async render() {
    const list = document.getElementById("config-panel-list");
    list.innerHTML = "";

    const [layoutResponse, modulesResponse] = await Promise.all([
      Api.get("/api/dashboard"),
      Api.get("/api/modules"),
    ]);

    const layout = layoutResponse.modules || [];
    const manifests = modulesResponse || {};
    const layoutById = {};
    for (const entry of layout) {
      layoutById[entry.module_id] = entry;
    }

    const moduleIds = Object.keys(manifests).sort();
    for (const moduleId of moduleIds) {
      const manifest = manifests[moduleId];
      const existing = layoutById[moduleId];
      const enabled = existing ? !!existing.enabled : false;
      const satisfied = manifest.requirement_satisfied !== false;
      const refreshSeconds = existing && existing.refresh_seconds
        ? existing.refresh_seconds
        : manifest.default_refresh_seconds || 30;

      const item = document.createElement("div");
      item.className = `panel-item${satisfied ? "" : " disabled"}`;
      item.innerHTML = `
        <div class="panel-item-header">
          <span class="name">${escapeHtml(manifest.name || moduleId)}</span>
          <label class="toggle">
            <input type="checkbox" ${enabled ? "checked" : ""} ${satisfied ? "" : "disabled"} data-module-id="${moduleId}">
            Enabled
          </label>
        </div>
        <p class="description">${escapeHtml(manifest.description || "")}</p>
        ${
          satisfied
            ? ""
            : `<p class="requirement-note">Needs the <strong>${escapeHtml(
                manifest.requires_integration
              )}</strong> integration configured first — see <a href="/admin/integrations.html">Integrations</a>.</p>`
        }
        <label class="refresh-override" style="margin-top:0.4rem;display:flex;align-items:center;gap:0.4rem;font-size:0.8rem;color:var(--text-dim);">
          Refresh every
          <input
            type="number"
            min="1"
            value="${refreshSeconds}"
            data-refresh-module-id="${moduleId}"
            style="width:70px;padding:0.25rem 0.4rem;"
          >
          seconds
        </label>
      `;
      list.appendChild(item);
    }

    list.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.addEventListener("change", (event) => this._onToggle(event, layout, manifests));
    });
    list.querySelectorAll('input[data-refresh-module-id]').forEach((input) => {
      input.addEventListener("change", (event) => this._onRefreshChange(event, layout, manifests));
    });
  },

  async _onRefreshChange(event, layout, manifests) {
    const moduleId = event.target.dataset.refreshModuleId;
    const refreshSeconds = Math.max(1, parseInt(event.target.value, 10) || 30);

    let entry = layout.find((item) => item.module_id === moduleId);
    if (!entry) {
      entry = {
        module_id: moduleId,
        enabled: false,
        position: layout.length,
        refresh_seconds: refreshSeconds,
      };
      layout.push(entry);
    } else {
      entry.refresh_seconds = refreshSeconds;
    }

    await Api.post("/api/dashboard", { modules: layout });
    await Dashboard.render();
  },

  async _onToggle(event, layout, manifests) {
    const moduleId = event.target.dataset.moduleId;
    const enabled = event.target.checked;

    let entry = layout.find((item) => item.module_id === moduleId);
    if (!entry) {
      const manifest = manifests[moduleId];
      entry = {
        module_id: moduleId,
        enabled,
        position: layout.length,
        refresh_seconds: manifest.default_refresh_seconds || 30,
      };
      layout.push(entry);
    } else {
      entry.enabled = enabled;
    }

    await Api.post("/api/dashboard", { modules: layout });
    await Dashboard.render();
  },
};

document.getElementById("toggle-config").addEventListener("click", (event) => {
  event.preventDefault();
  const panel = document.getElementById("config-panel");
  panel.hidden = !panel.hidden;
  if (!panel.hidden) {
    ConfigPanel.render();
  }
});
