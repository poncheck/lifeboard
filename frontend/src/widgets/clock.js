// LifeBoard — custom renderer for the built-in `clock` module. Needs a
// live local tick every second rather than polling the backend every
// second (see docs/ARCHITECTURE.md: "the clock module... needs a live
// local tick rather than polling every second"). The backend's
// get_data() is only used once to confirm the module is enabled; the
// actual displayed time comes from the browser's own clock.

const ClockWidget = {
  render(container, _data) {
    container.dataset.status = "neutral";
    container.innerHTML = `
      <div class="card-title">Clock</div>
      <div class="card-primary" id="clock-time" style="font-size:1.8rem;">--:--:--</div>
      <div class="card-lines"><div class="line" id="clock-date"></div></div>
    `;

    const timeEl = container.querySelector("#clock-time");
    const dateEl = container.querySelector("#clock-date");

    function tick() {
      const now = new Date();
      timeEl.textContent = now.toLocaleTimeString([], { hour12: false });
      dateEl.textContent = now.toLocaleDateString([], {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    }

    tick();
    // Store the interval id on the element so dashboard.js can clear it
    // if this card is ever removed/re-rendered without a page reload.
    container._clockIntervalId = setInterval(tick, 1000);
  },

  cleanup(container) {
    if (container._clockIntervalId) {
      clearInterval(container._clockIntervalId);
    }
  },
};
