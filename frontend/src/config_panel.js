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
      `;
      list.appendChild(item);
    }

    list.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
      checkbox.addEventListener("change", (event) => this._onToggle(event, layout, manifests));
    });
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
