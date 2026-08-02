const MONTHLY_DATA_URL = "data/monthly_archives.json?v=20260802-1";

const metricLabels = {
  fetched_count: "원본 수집",
  polygon_count: "Polygon",
  facility_point_count: "Point",
};

const elements = {
  updated: document.getElementById("monthly-updated"),
  archiveMonthCount: document.getElementById("archive-month-count"),
  latestPolygonCount: document.getElementById("latest-polygon-count"),
  latestPointCount: document.getElementById("latest-point-count"),
  latestFetchedCount: document.getElementById("latest-fetched-count"),
  metric: document.getElementById("monthly-metric"),
  chart: document.getElementById("monthly-chart"),
  rowCount: document.getElementById("monthly-row-count"),
  tableBody: document.getElementById("monthly-table-body"),
  empty: document.getElementById("monthly-empty"),
};

const formatNumber = (value) => Number(value || 0).toLocaleString("ko-KR");

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function normalizeArchives(data) {
  return [...(data.archives || [])].sort((a, b) => String(b.month).localeCompare(String(a.month)));
}

function renderMetrics(archives) {
  const latest = archives[0] || {};
  elements.archiveMonthCount.textContent = formatNumber(archives.length);
  elements.latestPolygonCount.textContent = formatNumber(latest.polygon_count);
  elements.latestPointCount.textContent = formatNumber(latest.facility_point_count);
  elements.latestFetchedCount.textContent = formatNumber(latest.fetched_count);
}

function renderChart(archives) {
  const metric = elements.metric.value;
  const ordered = [...archives].reverse();
  const maxValue = Math.max(...ordered.map((item) => Number(item[metric] || 0)), 1);
  elements.chart.innerHTML = "";

  if (!ordered.length) {
    return;
  }

  for (const item of ordered) {
    const value = Number(item[metric] || 0);
    const percent = Math.max(4, Math.round((value / maxValue) * 100));
    const row = document.createElement("div");
    row.className = "monthly-chart-row";
    row.innerHTML = `
      <span class="monthly-chart-month">${item.month || "-"}</span>
      <span class="monthly-chart-track">
        <span class="monthly-chart-bar" style="width: ${percent}%"></span>
      </span>
      <strong>${formatNumber(value)}</strong>
    `;
    elements.chart.appendChild(row);
  }

  elements.metric.setAttribute("aria-label", `${metricLabels[metric]} 월별 추이`);
}

function renderTable(archives) {
  elements.tableBody.innerHTML = "";
  elements.rowCount.textContent = `${formatNumber(archives.length)}건`;
  elements.empty.hidden = archives.length > 0;

  for (const item of archives) {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.month || "-"}</td>
      <td>${formatDateTime(item.generated_at)}</td>
      <td>${formatNumber(item.fetched_count)}</td>
      <td>${formatNumber(item.polygon_count)}</td>
      <td>${formatNumber(item.facility_point_count)}</td>
      <td><code>${item.run_id || "-"}</code></td>
      <td>${item.status || "ARCHIVED"}</td>
    `;
    elements.tableBody.appendChild(row);
  }
}

function render(data) {
  const archives = normalizeArchives(data);
  elements.updated.textContent = data.generated_at
    ? `최근 갱신 ${formatDateTime(data.generated_at)}`
    : "월별 아카이브 통계 대기 중";
  renderMetrics(archives);
  renderChart(archives);
  renderTable(archives);
}

async function loadMonthlyStats() {
  try {
    const response = await fetch(MONTHLY_DATA_URL, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    render(await response.json());
  } catch (error) {
    elements.updated.textContent = `월별 통계를 불러오지 못했습니다: ${error.message}`;
    elements.empty.hidden = false;
  }
}

elements.metric.addEventListener("change", () => {
  fetch(MONTHLY_DATA_URL, { cache: "no-store" })
    .then((response) => response.json())
    .then((data) => renderChart(normalizeArchives(data)));
});

loadMonthlyStats();
