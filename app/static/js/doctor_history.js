(() => {
  const copyButton = document.getElementById("copy-access-code");
  if (copyButton) {
    const status = document.getElementById("copy-access-code-status");
    const link = document.getElementById("link-patient-after-copy");

    copyButton.addEventListener("click", async () => {
      if (!navigator.clipboard || !navigator.clipboard.writeText) {
        status.textContent = copyButton.dataset.copyError;
        return;
      }

      try {
        await navigator.clipboard.writeText(copyButton.dataset.accessCode);
        status.textContent = copyButton.dataset.copiedLabel;
        link.hidden = true;
      } catch (error) {
        console.error("Unable to copy the patient access code.", error);
        status.textContent = copyButton.dataset.copyError;
      }
    });
  }

  const element = document.getElementById("history-data");
  if (!element || typeof Chart === "undefined") {
    return;
  }

  const history = JSON.parse(element.textContent);
  const labels = history.labels;
  const readings = history.measurements;
  const dateAxis = {
    ticks: { callback: () => "" },
  };
  const lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: "index" },
    plugins: {
      tooltip: {
        callbacks: {
          title: (items) => items.length
            ? window.formatMeasurementTimestamp(items[0].label)
            : "",
        },
      },
    },
    scales: { x: dateAxis, y: { beginAtZero: true } },
  };

  const bloodPressure = document.getElementById("blood-pressure-chart");
  new Chart(bloodPressure, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: history.labels_text.systolic,
          data: readings.map((row) => row.systolic),
          borderColor: "#2854dd",
          pointBackgroundColor: readings.map((row) =>
            row.abnormal_systolic ? "#c00000" : "#2854dd",
          ),
          pointBorderColor: readings.map((row) =>
            row.abnormal_systolic ? "#c00000" : "#2854dd",
          ),
          pointStyle: readings.map((row) =>
            row.abnormal_systolic ? "triangle" : "circle",
          ),
          pointRadius: readings.map((row) =>
            row.abnormal_systolic ? 8 : 3,
          ),
          tension: 0.2,
        },
        {
          label: history.labels_text.diastolic,
          data: readings.map((row) => row.diastolic),
          borderColor: "#2e8b57",
          pointBackgroundColor: readings.map((row) =>
            row.abnormal_diastolic ? "#c00000" : "#2e8b57",
          ),
          pointBorderColor: readings.map((row) =>
            row.abnormal_diastolic ? "#c00000" : "#2e8b57",
          ),
          pointStyle: readings.map((row) =>
            row.abnormal_diastolic ? "triangle" : "circle",
          ),
          pointRadius: readings.map((row) =>
            row.abnormal_diastolic ? 8 : 3,
          ),
          tension: 0.2,
        },
        {
          label: history.labels_text.pulse_pressure,
          data: readings.map((row) => row.pulse_pressure),
          borderColor: "#657084",
          yAxisID: "y1",
          tension: 0.2,
        },
        {
          label: `${history.labels_text.threshold} (${history.labels_text.systolic})`,
          data: labels.map(() => history.threshold.systolic),
          borderColor: "#c00000",
          borderDash: [6, 4],
          pointRadius: 0,
        },
        {
          label: `${history.labels_text.threshold} (${history.labels_text.diastolic})`,
          data: labels.map(() => history.threshold.diastolic),
          borderColor: "#c00000",
          borderDash: [2, 4],
          pointRadius: 0,
        },
      ],
    },
    options: {
      ...lineOptions,
      scales: {
        x: dateAxis,
        y: { beginAtZero: false },
        y1: {
          position: "right",
          beginAtZero: true,
          grid: { drawOnChartArea: false },
        },
      },
    },
  });

  const symptomChart = new Chart(document.getElementById("symptom-chart"), {
    type: "line",
    data: {
      labels,
      datasets: history.symptoms.map((symptom, index) => ({
        label: symptom.label,
        data: symptom.data,
        borderColor: `hsl(${(index * 43) % 360} 55% 40%)`,
        spanGaps: false,
        tension: 0.2,
      })),
    },
    options: lineOptions,
  });

  document.querySelectorAll(".symptom-toggle").forEach((toggle) => {
    toggle.addEventListener("change", () => {
      const datasetIndex = history.symptoms.findIndex(
        (symptom) => symptom.key === toggle.value,
      );
      if (datasetIndex >= 0) {
        symptomChart.setDatasetVisibility(datasetIndex, toggle.checked);
        symptomChart.update();
      }
    });
  });

  new Chart(document.getElementById("pulse-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: history.labels_text.pulse,
          data: readings.map((row) => row.pulse),
          borderColor: "#2854dd",
          tension: 0.2,
        },
      ],
    },
    options: lineOptions,
  });

  const comparisonElement = document.getElementById("comparison-data");
  if (comparisonElement) {
    const comparison = JSON.parse(comparisonElement.textContent);
    new Chart(document.getElementById("measurement-comparison-chart"), {
      type: "line",
      data: {
        labels: comparison.map((reading) => reading.measured_at),
        datasets: [
          {
            label: history.labels_text.systolic,
            data: comparison.map((reading) => reading.systolic),
            borderColor: "#2854dd",
            tension: 0.2,
          },
          {
            label: history.labels_text.diastolic,
            data: comparison.map((reading) => reading.diastolic),
            borderColor: "#2e8b57",
            tension: 0.2,
          },
          {
            label: history.labels_text.pulse,
            data: comparison.map((reading) => reading.pulse),
            borderColor: "#946116",
            yAxisID: "y1",
            tension: 0.2,
          },
        ],
      },
      options: {
        ...lineOptions,
        scales: {
          x: dateAxis,
          y: { beginAtZero: false, title: { display: true, text: "mmHg" } },
          y1: {
            position: "right",
            beginAtZero: false,
            grid: { drawOnChartArea: false },
            title: { display: true, text: history.labels_text.pulse },
          },
        },
      },
    });
  }
})();
