// LifeBoard — custom renderer for the built-in `nutrition` module.
// Needs a small "log a meal" form the generic card schema can't
// express (per docs/ARCHITECTURE.md's frontend widget contract: "A
// module that needs something the generic card can't express... ships
// a custom renderer instead").

const NutritionWidget = {
  render(container, data) {
    if (data && data.error) {
      container.classList.add("card-error");
      container.innerHTML = `<div class="card-title">Nutrition</div><div>${data.error}</div>`;
      return;
    }

    container.dataset.status = data.status || "neutral";
    const linesHtml = (data.lines || [])
      .map((line) => `<div class="line"><span>${line.label}</span><span>${line.value}</span></div>`)
      .join("");

    container.innerHTML = `
      <div class="card-title">${data.title || "Nutrition"}</div>
      <div class="card-primary">${data.primary_value ?? "0"}<span class="unit">${data.primary_unit || ""}</span></div>
      <div class="card-lines">${linesHtml}</div>
      <form class="log-meal-form" style="margin-top:0.5rem;display:flex;gap:0.3rem;flex-wrap:wrap;">
        <input type="text" name="name" placeholder="Meal" required style="flex:1 1 90px;">
        <input type="number" name="kcal" placeholder="kcal" required style="flex:0 1 70px;">
        <button type="submit" class="secondary" style="flex:0 0 auto;">Log</button>
      </form>
      <p class="error-message" style="margin:0;"></p>
    `;

    const form = container.querySelector(".log-meal-form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const errorEl = container.querySelector(".error-message");
      errorEl.textContent = "";
      try {
        await Api.post("/api/nutrition/entries", {
          name: form.name.value,
          kcal: parseFloat(form.kcal.value) || 0,
        });
        form.reset();
        const refreshed = await Api.get("/api/modules/nutrition/data");
        NutritionWidget.render(container, refreshed);
      } catch (err) {
        errorEl.textContent = err.message;
      }
    });
  },
};
