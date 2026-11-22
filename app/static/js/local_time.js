(() => {
  const locale = document.documentElement.lang === "fr" ? "fr-CA" : "en-CA";
  const formatter = new Intl.DateTimeFormat(locale, {
    timeZone: "America/Toronto",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  window.formatMeasurementTimestamp = (timestamp) => {
    const utcTimestamp = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(timestamp)
      ? timestamp
      : `${timestamp.replace(" ", "T")}Z`;
    const date = new Date(utcTimestamp);
    return Number.isNaN(date.getTime()) ? timestamp : formatter.format(date);
  };

  document.querySelectorAll("[data-utc-time]").forEach((element) => {
    element.textContent = window.formatMeasurementTimestamp(
      element.dataset.utcTime,
    );
  });
})();
