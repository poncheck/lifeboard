// LifeBoard — admin panel's Integrations screen: one card per
// discovered integration, a form built from credential_fields,
// "Test & Save", a sync status line (last synced / last error), and a
// "Sync now" button. Per docs/ARCHITECTURE.md.

const IntegrationsAdmin = {
  async render() {
    const list = document.getElementById("integrations-list");
    list.innerHTML = "";

    const integrations = await Api.get("/api/integrations");
    const ids = Object.keys(integrations).sort();

    if (ids.length === 0) {
      list.innerHTML = '<p style="color:var(--text-dim);">No integrations discovered.</p>';
      return;
    }

    for (const integrationId of ids) {
      list.appendChild(this._renderItem(integrationId, integrations[integrationId]));
    }
  },

  _renderItem(integrationId, manifest) {
    const item = document.createElement("div");
    item.className = "panel-item";

    const fieldsHtml = (manifest.credential_fields || [])
      .map(
        (field) => `
          <div class="field">
            <label for="field-${integrationId}-${field.key}">${escapeHtml(field.label)}</label>
            <input
              id="field-${integrationId}-${field.key}"
              type="${field.secret ? "password" : "text"}"
              data-key="${field.key}"
            >
          </div>`
      )
      .join("");

    const statusHtml = this._statusLineHtml(manifest);

    item.innerHTML = `
      <div class="panel-item-header">
        <span class="name">${escapeHtml(manifest.name || integrationId)}</span>
        <span style="font-size:0.8rem;color:${manifest.configured ? "var(--ok)" : "var(--text-dim)"};">
          ${manifest.configured ? "Configured" : "Not configured"}
        </span>
      </div>
      <p class="description">${escapeHtml(manifest.description || "")}</p>
      <form class="credential-form" data-integration-id="${integrationId}">
        ${fieldsHtml}
        <div class="actions">
          <button class="secondary" type="submit">Test &amp; Save</button>
          <button class="secondary" type="button" data-action="sync-now">Sync now</button>
          ${manifest.configured ? '<button class="danger" type="button" data-action="remove">Remove</button>' : ""}
        </div>
        <p class="error-message" data-role="form-error"></p>
      </form>
      ${statusHtml}
    `;

    const form = item.querySelector("form");
    form.addEventListener("submit", (event) => this._onSaveCredentials(event, integrationId));
    form.querySelector('[data-action="sync-now"]').addEventListener("click", () =>
      this._onSyncNow(integrationId, item)
    );
    const removeBtn = form.querySelector('[data-action="remove"]');
    if (removeBtn) {
      removeBtn.addEventListener("click", () => this._onRemove(integrationId));
    }

    return item;
  },

  _statusLineHtml(manifest) {
    if (manifest.last_error) {
      return `<p class="status-line status-error">Last error: ${escapeHtml(manifest.last_error)}</p>`;
    }
    if (manifest.last_synced_at) {
      return `<p class="status-line">Last synced ${escapeHtml(relativeTime(manifest.last_synced_at))}</p>`;
    }
    return `<p class="status-line">Never synced</p>`;
  },

  async _onSaveCredentials(event, integrationId) {
    event.preventDefault();
    const form = event.target;
    const errorEl = form.querySelector('[data-role="form-error"]');
    errorEl.textContent = "";

    const credentials = {};
    form.querySelectorAll("input[data-key]").forEach((input) => {
      credentials[input.dataset.key] = input.value;
    });

    try {
      await Api.post(`/api/integrations/${integrationId}/credentials`, credentials);
      await this.render();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  },

  async _onSyncNow(integrationId, item) {
    const errorEl = item.querySelector('[data-role="form-error"]');
    errorEl.textContent = "";
    try {
      await Api.post(`/api/integrations/${integrationId}/sync-now`);
      await this.render();
    } catch (err) {
      errorEl.textContent = err.message;
    }
  },

  async _onRemove(integrationId) {
    await Api.del(`/api/integrations/${integrationId}/credentials`);
    await this.render();
  },
};

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value == null ? "" : String(value);
  return div.innerHTML;
}

function relativeTime(isoString) {
  try {
    const then = new Date(isoString).getTime();
    const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return isoString;
  }
}

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await Api.post("/api/logout");
  } finally {
    window.location.href = "/login.html";
  }
});

IntegrationsAdmin.render();
