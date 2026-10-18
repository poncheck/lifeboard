// LifeBoard — account settings page: change password, log out all
// sessions. Per Phase 5.

document.getElementById("logout-btn").addEventListener("click", async () => {
  try {
    await Api.post("/api/logout");
  } finally {
    window.location.href = "/login.html";
  }
});

document.getElementById("change-password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const errorEl = document.getElementById("change-password-error");
  const successEl = document.getElementById("change-password-success");
  errorEl.textContent = "";
  successEl.hidden = true;

  const form = event.target;
  try {
    await Api.post("/api/account/change-password", {
      current_password: form.current_password.value,
      new_password: form.new_password.value,
    });
    successEl.hidden = false;
    // change-password invalidates this session's own token too —
    // redirect to login rather than leaving a dead session hanging.
    setTimeout(() => {
      window.location.href = "/login.html";
    }, 1200);
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("logout-all-btn").addEventListener("click", async () => {
  const errorEl = document.getElementById("logout-all-error");
  errorEl.textContent = "";
  try {
    await Api.post("/api/account/logout-all-sessions");
    window.location.href = "/login.html";
  } catch (err) {
    errorEl.textContent = err.message;
  }
});
