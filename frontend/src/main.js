// LifeBoard — bootstraps the dashboard page: checks auth, renders the
// grid, wires up the logout button.

(async function init() {
  try {
    const status = await Api.get("/api/account/status");
    if (!status.has_account) {
      window.location.href = "/setup.html";
      return;
    }
  } catch {
    // ignore — proceed and let a protected-route 401 redirect to login
  }

  try {
    await Dashboard.render();
  } catch (err) {
    if (err.message !== "Not authenticated") {
      console.error("Failed to render dashboard:", err);
    }
  }
})();

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await Api.post("/api/logout");
  } finally {
    window.location.href = "/login.html";
  }
});
