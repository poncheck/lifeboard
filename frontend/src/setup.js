// LifeBoard — onboarding wizard submit. Posts to /api/setup, then
// redirects to /login.html on success. If setup has already run
// (account already exists), redirects straight to login too.

(async function init() {
  try {
    const status = await Api.get("/api/account/status");
    if (status.has_account) {
      window.location.href = "/login.html";
      return;
    }
  } catch {
    // If the status check itself fails, let the user try the form —
    // the backend will reject appropriately.
  }
})();

document.getElementById("setup-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorEl = document.getElementById("error-message");
  errorEl.textContent = "";

  const form = event.target;
  const payload = {
    full_name: form.full_name.value,
    date_of_birth: form.date_of_birth.value,
    email: form.email.value,
    password: form.password.value,
  };

  try {
    await Api.post("/api/setup", payload);
    window.location.href = "/login.html";
  } catch (err) {
    errorEl.textContent = err.message;
  }
});
