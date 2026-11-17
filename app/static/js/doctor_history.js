(() => {
  const element = document.getElementById("history-data");
  if (!element || typeof Chart === "undefined") {
    return;
  }

  const history = JSON.parse(element.textContent);
  const labels = history.labels;
  const readings = history.measurements;
  const lineOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { intersect: false, mode: "index" },
    scales: { y: { beginAtZero: true } },
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
          borderColor: "#176b70",
          pointBackgroundColor: readings.map((row) =>
            row.abnormal_systolic ? "#c00000" : "#176b70",
          ),
          pointBorderColor: readings.map((row) =>
            row.abnormal_systolic ? "#c00000" : "#176b70",
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
          borderColor: "#d27630",
          pointBackgroundColor: readings.map((row) =>
            row.abnormal_diastolic ? "#c00000" : "#d27630",
          ),
          pointBorderColor: readings.map((row) =>
            row.abnormal_diastolic ? "#c00000" : "#d27630",
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
          borderColor: "#7554a4",
          yAxisID: "y1",
          tension: 0.2,
        },
        {
          label: `${history.labels_text.threshold} (${history.labels_text.systolic})`,
          data: labels.map(() => history.threshold.systolic),
          borderColor: "#a33b3b",
          borderDash: [6, 4],
          pointRadius: 0,
        },
        {
          label: `${history.labels_text.threshold} (${history.labels_text.diastolic})`,
          data: labels.map(() => history.threshold.diastolic),
          borderColor: "#d18a8a",
          borderDash: [2, 4],
          pointRadius: 0,
        },
      ],
    },
    options: {
      ...lineOptions,
      scales: {
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
          borderColor: "#176b70",
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
            borderColor: "#b4232e",
            tension: 0.2,
          },
          {
            label: history.labels_text.diastolic,
            data: comparison.map((reading) => reading.diastolic),
            borderColor: "#2854dd",
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
