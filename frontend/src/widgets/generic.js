// LifeBoard — default card renderer. Any module's get_data() returning
// this shape renders automatically, zero per-module frontend code
// required (see docs/ARCHITECTURE.md's "generic card schema").
//
// Every renderer in frontend/src/widgets/*.js (including custom ones)
// implements the same tiny contract: render(container, data) -> void.
// `container` is the card's root <div class="card">, already inserted
// into the grid by dashboard.js; this function just fills it in.

const GenericWidget = {
  render(container, data) {
    if (data && data.error) {
      container.classList.add("card-error");
      container.innerHTML = `
        <div class="card-title">${escapeHtml(data.title || "Error")}</div>
        <div class="card-primary" style="font-size:1rem;color:var(--text-dim);">${escapeHtml(data.error)}</div>
      `;
      return;
    }

    const status = data.status || "neutral";
    container.dataset.status = status;

    const linesHtml = (data.lines || [])
      .map(
        (line) =>
          `<div class="line"><span>${escapeHtml(line.label)}</span><span>${escapeHtml(line.value)}</span></div>`
      )
      .join("");

    const updatedHtml = data.updated_at ? `<div class="card-updated">updated ${relativeTime(data.updated_at)}</div>` : "";

    container.innerHTML = `
      <div class="card-title">${escapeHtml(data.title || "")}</div>
      <div class="card-primary">${escapeHtml(data.primary_value ?? "—")}${
        data.primary_unit ? `<span class="unit">${escapeHtml(data.primary_unit)}</span>` : ""
      }</div>
      ${linesHtml ? `<div class="card-lines">${linesHtml}</div>` : ""}
      ${updatedHtml}
    `;
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
