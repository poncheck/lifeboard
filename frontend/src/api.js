// LifeBoard — tiny fetch wrapper shared by every page's JS. No framework,
// no build step (see docs/ARCHITECTURE.md). Cookies (the session) are
// sent automatically via `credentials: "same-origin"`.

const Api = {
  async _request(method, path, body) {
    const response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 401 && !path.startsWith("/api/login") && !path.startsWith("/api/setup")) {
      // Mid-session expiry/invalidation: bounce back to login, per the
      // frontend widget contract in docs/ARCHITECTURE.md.
      window.location.href = "/login.html";
      throw new Error("Not authenticated");
    }

    let data = null;
    const text = await response.text();
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = null;
      }
    }

    if (!response.ok) {
      const detail = (data && data.detail) || `Request failed (${response.status})`;
      throw new Error(detail);
    }
    return data;
  },

  get(path) {
    return this._request("GET", path);
  },
  post(path, body) {
    return this._request("POST", path, body || {});
  },
  del(path) {
    return this._request("DELETE", path);
  },
};
