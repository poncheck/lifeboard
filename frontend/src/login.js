// LifeBoard — login form submit. Posts to /api/login (session cookie
// set by the server), then redirects to the dashboard. If no account
// exists yet, redirects to the setup wizard instead of showing a
// confusing "invalid credentials" error on an empty login.

(async function init() {
  try {
    const status = await Api.get("/api/account/status");
    if (!status.has_account) {
      window.location.href = "/setup.html";
    }
  } catch {
    // Non-fatal — let the user try the login form anyway.
  }
})();

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorEl = document.getElementById("error-message");
  errorEl.textContent = "";

  const form = event.target;
  const payload = {
    email: form.email.value,
    password: form.password.value,
    remember_me: form.remember_me.checked,
  };

  try {
    await Api.post("/api/login", payload);
    window.location.href = "/";
  } catch (err) {
    errorEl.textContent = "Invalid email or password.";
  }
});
