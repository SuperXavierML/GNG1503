(() => {
  const timer = document.getElementById("measurement-countdown");
  if (!timer) {
    return;
  }

  const dueAt = Date.parse(timer.dataset.dueAt || "");
  if (Number.isNaN(dueAt)) {
    return;
  }

  const update = () => {
    const remaining = Math.max(0, dueAt - Date.now());
    if (remaining === 0) {
      timer.textContent = timer.dataset.dueLabel;
      return;
    }
    const totalSeconds = Math.floor(remaining / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const clock = [hours, minutes, seconds]
      .map((value) => String(value).padStart(2, "0"))
      .join(":");
    timer.textContent = days > 0
      ? `${days} ${timer.dataset.daysLabel}, ${clock}`
      : clock;
  };

  update();
  window.setInterval(update, 1000);
})();
