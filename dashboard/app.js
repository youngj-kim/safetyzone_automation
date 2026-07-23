const map = L.map("map", {
  preferCanvas: true,
}).setView([36.4, 127.8], 7);
window.dashboardMap = map;

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

const layerGroups = {
  currentChild: L.layerGroup().addTo(map),
  currentSenior: L.layerGroup().addTo(map),
  currentDisabled: L.layerGroup().addTo(map),
  currentOther: L.layerGroup().addTo(map),
  new: L.layerGroup().addTo(map),
  changed: L.layerGroup().addTo(map),
  review: L.layerGroup().addTo(map),
};

const state = {
  events: [],
  eventLayers: new Map(),
  eventFeatures: new Map(),
  timelines: new Map(),
  polygonDeletedManageNos: new Set(),
  currentGroups: new Map(),
};
document.body.dataset.dashboardVersion = "20260723-11";

function numberText(value) {
  return Number(value || 0).toLocaleString("ko-KR");
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatApiDate(value) {
  if (!value) return "-";
  return value;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function runFailureReason(errorMessage) {
  if (!errorMessage) return "";
  const message = String(errorMessage);
  if (message.includes("too many 429")) {
    return "공공 API 요청 제한(429)으로 수집 실패";
  }
  if (message.includes("ERR_03") || message.includes("조회된 데이터가 없습니다")) {
    return "공공 API 응답 데이터 없음";
  }
  if (message.includes("timeout") || message.includes("Timeout")) {
    return "공공 API 응답 시간 초과";
  }
  return message
    .replace(/([?&](?:serviceKey|service_key|key|token)=)[^&\s]+/gi, "$1[REDACTED]")
    .slice(0, 160);
}

function changeColor(type) {
  if (type === "NEW") return "#2f8f5b";
  if (type === "DELETED") return "#cf3f35";
  if (type === "MISSING") return "#707985";
  return "#c77900";
}

function changeCategory(type) {
  if (type === "NEW") return "new";
  if (type === "DELETED" || type === "MISSING") return "review";
  return "changed";
}

function zoneTypeInfo(code) {
  const normalized = String(code || "").trim();
  const types = {
    1: { label: "어린이보호구역", color: "#2563eb", fillOpacity: 0.1 },
    2: { label: "노인보호구역", color: "#be185d", fillOpacity: 0.12 },
    3: { label: "장애인보호구역", color: "#0891b2", fillOpacity: 0.12 },
  };
  return types[normalized] || {
    label: "보호구역 유형 미분류",
    color: "#707985",
    fillOpacity: 0.08,
  };
}

function currentLayerKey(code) {
  const normalized = String(code || "").trim();
  if (normalized === "1") return "currentChild";
  if (normalized === "2") return "currentSenior";
  if (normalized === "3") return "currentDisabled";
  return "currentOther";
}

function summarizeNames(names) {
  const uniqueNames = [...new Set(names.filter(Boolean))];
  if (!uniqueNames.length) return "현재 그룹명 없음";
  if (uniqueNames.length <= 2) return uniqueNames.join(", ");
  return `${uniqueNames.slice(0, 2).join(", ")} 외 ${uniqueNames.length - 2}건`;
}

function buildCurrentGroupIndex(zones, points) {
  const groups = new Map();
  [...(zones.features || []), ...(points.features || [])].forEach((feature) => {
    const props = feature.properties || {};
    const groupId = props.zone_group_id;
    if (!groupId) return;
    if (!groups.has(groupId)) {
      groups.set(groupId, {
        zoneNames: [],
        pointNames: [],
        sourceManageNos: new Set(),
      });
    }
    const group = groups.get(groupId);
    if (props.source_manage_no) group.sourceManageNos.add(props.source_manage_no);
    if (feature.geometry?.type === "Point") {
      group.pointNames.push(props.facility_name);
    } else {
      group.zoneNames.push(props.facility_name);
    }
  });
  return groups;
}

function reviewReason(props) {
  if (!["DELETED", "MISSING"].includes(props.change_type)) return "";
  if (props.layer_type === "Polygon") return "Polygon 삭제 이벤트";
  if (state.polygonDeletedManageNos.has(props.source_manage_no)) {
    return "Polygon도 함께 삭제됨";
  }

  const group = state.currentGroups.get(props.zone_group_id);
  if (!group) return "현재 그룹 없음, 원천 삭제 또는 응답 누락 확인";

  const currentNames = summarizeNames([...group.zoneNames, ...group.pointNames]);
  if (group.sourceManageNos.has(props.source_manage_no)) {
    return `같은 관리번호가 현재 그룹에 남아 있음: ${currentNames}`;
  }
  return `같은 그룹 Polygon 유지: ${currentNames}`;
}

function enrichReviewProperties(props) {
  return {
    ...props,
    review_reason: props.review_reason || reviewReason(props),
  };
}

function featureProperties(feature) {
  return {
    ...(feature.properties || {}),
    event_id: feature.properties?.event_id ?? feature.id,
  };
}

function eventKey(props) {
  return `${props.layer_type}-${props.event_id}`;
}

function timelineKey(props) {
  const layerType = props.layer_type || (props.facility_id ? "Point" : "Polygon");
  const entityId = props.source_manage_no || props.zone_group_id || props.event_id;
  return entityId ? `${layerType}:${entityId}` : "";
}

function timelineForProps(props) {
  return state.timelines.get(timelineKey(props));
}

function statusHintLabel(status) {
  const labels = {
    CURRENT: "현재 유지",
    NEW: "신규",
    UPDATED: "변경 추적",
    MISSING_REVIEW: "삭제 검토 1회",
    DELETE_CANDIDATE: "반복 누락, 삭제 의심",
    DELETED_CONFIRMED: "삭제 확인",
    RETURNED: "누락 후 재등장",
  };
  return labels[status] || status || "";
}

function timelineSummary(timeline) {
  if (!timeline) return "";
  const parts = [statusHintLabel(timeline.status_hint)];
  if (timeline.missing_streak > 0) {
    parts.push(`연속 누락 ${timeline.missing_streak}회`);
  }
  if (timeline.events?.length > 1) {
    parts.push(`누적 감지 ${timeline.events.length}회`);
  }
  return parts.filter(Boolean).join(" · ");
}

function popupTimelineContent(props) {
  const timeline = timelineForProps(props);
  if (!timeline) return "";
  const recentEvents = (timeline.events || [])
    .slice(0, 3)
    .map(
      (event) =>
        `<li>${formatDate(event.detected_at)} · ${event.layer_type} · ${event.change_type}</li>`,
    )
    .join("");
  return `
    <div class="popup-timeline">
      <strong>${timelineSummary(timeline)}</strong>
      ${recentEvents ? `<ol>${recentEvents}</ol>` : ""}
    </div>
  `;
}

function boundsFromFeature(feature) {
  if (!feature?.geometry) return null;
  if (feature.geometry.type === "Point") {
    const [lng, lat] = feature.geometry.coordinates;
    return L.latLngBounds([L.latLng(lat, lng)]);
  }
  const points = [];
  const collectCoordinates = (coordinates) => {
    if (!Array.isArray(coordinates)) return;
    if (typeof coordinates[0] === "number" && typeof coordinates[1] === "number") {
      points.push(L.latLng(coordinates[1], coordinates[0]));
      return;
    }
    coordinates.forEach(collectCoordinates);
  };
  collectCoordinates(feature.geometry.coordinates);
  return points.length ? L.latLngBounds(points) : null;
}

function ensureLayerVisible(category) {
  const group = layerGroups[category];
  if (!group) return;
  if (!map.hasLayer(group)) {
    group.addTo(map);
    const input = document.querySelector(`input[data-layer="${category}"]`);
    if (input) input.checked = true;
  }
}

function focusEvent(event) {
  const category = changeCategory(event.change_type);
  ensureLayerVisible(category);

  const key = eventKey(event);
  const layer = state.eventLayers.get(key);
  const feature = state.eventFeatures.get(key);
  const bounds =
    boundsFromFeature(feature) ||
    (layer?.getBounds ? layer.getBounds() : null) ||
    (layer?.getLatLng ? L.latLngBounds([layer.getLatLng()]) : null);

  window.dashboardLastFocus = {
    key,
    hasLayer: Boolean(layer),
    hasFeature: Boolean(feature),
    hasBounds: Boolean(bounds),
    isValid: Boolean(bounds?.isValid()),
  };
  document.body.dataset.lastFocus = JSON.stringify(window.dashboardLastFocus);
  if (!bounds?.isValid()) return;
  const center = bounds.getCenter();
  if (feature?.geometry?.type === "Point" || bounds.getNorthEast().equals(bounds.getSouthWest())) {
    map.setView(center, Math.max(map.getZoom(), 17), { animate: true });
  } else {
    map.fitBounds(bounds.pad(0.35), { maxZoom: 17, animate: true });
  }
  L.popup({ maxWidth: 320 })
    .setLatLng(center)
    .setContent(popupContent(event))
    .openOn(map);
  document.body.dataset.lastPopup = key;
}

function popupContent(props) {
  const enriched = enrichReviewProperties(props);
  const title = props.facility_name || "이름 없음";
  const type = props.change_type ? `<b>${props.change_type}</b><br>` : "";
  const review = enriched.review_reason ? `검토: ${enriched.review_reason}<br>` : "";
  const zoneType = zoneTypeInfo(props.facility_type_code);
  const apiDates =
    props.api_first_registered_on || props.api_last_modified_on
      ? `API 최초등록: ${formatApiDate(props.api_first_registered_on)}<br>
    API 최종수정: ${formatApiDate(props.api_last_modified_on)}<br>`
      : "";
  return `
    <strong>${title}</strong><br>
    ${type}
    종류: ${zoneType.label}<br>
    관리번호: ${props.source_manage_no || "-"}<br>
    시군구: ${props.sgg_code || "-"}<br>
    그룹: ${props.zone_group_id || "-"}<br>
    ${apiDates}
    ${review}
    ${popupTimelineContent(props)}
    ${props.detected_at ? `감지: ${formatDate(props.detected_at)}<br>` : ""}
    ${props.updated_at ? `시스템 갱신: ${formatDate(props.updated_at)}<br>` : ""}
  `;
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

function renderOverview(overview) {
  document.getElementById("polygon-count").textContent = numberText(
    overview.current_counts?.polygons,
  );
  document.getElementById("point-count").textContent = numberText(
    overview.current_counts?.facility_points,
  );
  document.getElementById("sgg-count").textContent = numberText(
    overview.current_counts?.sgg_codes,
  );

  const recentRuns = overview.recent_runs || [];
  const latest = recentRuns[0];
  document.getElementById("last-updated").textContent = latest
    ? `최근 실행 ${formatDate(latest.finished_at || latest.started_at)}`
    : "실행 이력이 없습니다";
  document.getElementById("run-total").textContent = `${numberText(recentRuns.length)}건`;

  const runList = document.getElementById("run-list");
  runList.replaceChildren(
    ...recentRuns.map((run) => {
      const item = document.createElement("li");
      item.className = "run-item";
      const polygonChanges = Object.values(run.polygon_changes || {}).reduce(
        (sum, value) => sum + Number(value || 0),
        0,
      );
      const pointChanges = Object.values(run.point_changes || {}).reduce(
        (sum, value) => sum + Number(value || 0),
        0,
      );
      item.innerHTML = `
        <div class="run-topline">
          <span class="run-title">${run.status}</span>
          <span class="badge ${run.status === "SUCCESS" ? "NEW" : "DELETED"}">${formatDate(
            run.finished_at || run.started_at,
          )}</span>
        </div>
        <div class="run-meta">
          수집 ${numberText(run.fetched_count)}건 · Polygon 변경 ${numberText(
            polygonChanges,
          )}건 · Point 변경 ${numberText(pointChanges)}건<br>
          ${
            run.status !== "SUCCESS" && run.error_message
              ? `<span class="run-error">실패 사유: ${escapeHtml(
                  runFailureReason(run.error_message),
                )}</span><br>`
              : ""
          }
          ${run.run_id}
        </div>
      `;
      return item;
    }),
  );
}

function renderEvents() {
  const query = document.getElementById("event-search").value.trim().toLowerCase();
  const type = document.getElementById("event-type").value;
  const filtered = state.events.filter((event) => {
    const matchesType = !type || event.change_type === type;
    const haystack = [
      event.facility_name,
      event.source_manage_no,
      event.sgg_code,
      event.run_id,
      event.layer_type,
      event.facility_type_code,
      zoneTypeInfo(event.facility_type_code).label,
    ]
      .join(" ")
      .toLowerCase();
    return matchesType && (!query || haystack.includes(query));
  });

  document.getElementById("event-total").textContent = `${numberText(filtered.length)}건`;
  const eventList = document.getElementById("event-list");
  eventList.replaceChildren(
    ...filtered.slice(0, 120).map((event) => {
      const enriched = enrichReviewProperties(event);
      const timelineText = timelineSummary(timelineForProps(event));
      const zoneType = zoneTypeInfo(event.facility_type_code);
      const item = document.createElement("li");
      item.className = "event-item";
      item.tabIndex = 0;
      item.setAttribute("role", "button");
      item.setAttribute("aria-label", `${event.facility_name || "이름 없음"} 위치로 이동`);
      item.innerHTML = `
        <div class="event-topline">
          <span class="event-title">${event.facility_name || "이름 없음"}</span>
          <span class="badge ${event.change_type}">${event.change_type}</span>
        </div>
        <div class="event-meta">
          <span class="zone-type" style="--zone-type-color: ${zoneType.color}">${zoneType.label}</span><br>
          ${event.layer_type} · ${event.source_manage_no || "-"} · ${event.sgg_code || "-"}<br>
          ${
            enriched.review_reason
              ? `<span class="review-reason">${enriched.review_reason}</span><br>`
              : ""
          }
          ${
            event.api_last_modified_on
              ? `<span>API 최종수정 ${formatApiDate(event.api_last_modified_on)}</span><br>`
              : ""
          }
          ${timelineText ? `<span class="timeline-summary">${timelineText}</span><br>` : ""}
          ${formatDate(event.detected_at)}
        </div>
      `;
      item.addEventListener("click", () => {
        document.querySelectorAll(".event-item.selected").forEach((selectedItem) => {
          selectedItem.classList.remove("selected");
        });
        item.classList.add("selected");
        focusEvent(event);
      });
      item.addEventListener("keydown", (keyboardEvent) => {
        if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
          keyboardEvent.preventDefault();
          focusEvent(event);
        }
      });
      return item;
    }),
  );
}

function addCurrentZones(geojson) {
  return Object.keys(layerGroups)
    .filter((key) => key.startsWith("current"))
    .map((key) =>
      L.geoJSON(geojson, {
        filter: (feature) => currentLayerKey(feature.properties?.facility_type_code) === key,
        style: (feature) => {
          const zoneType = zoneTypeInfo(feature.properties?.facility_type_code);
          return {
            color: zoneType.color,
            weight: 1.6,
            opacity: 0.8,
            fillColor: zoneType.color,
            fillOpacity: zoneType.fillOpacity,
          };
        },
        onEachFeature: (feature, itemLayer) => {
          const props = enrichReviewProperties({
            layer_type: "Polygon",
            ...(feature.properties || {}),
          });
          feature.properties = props;
          itemLayer.bindPopup(popupContent(props));
        },
      }).addTo(layerGroups[key]),
    );
}

function addCurrentPoints(geojson) {
  return Object.keys(layerGroups)
    .filter((key) => key.startsWith("current"))
    .map((key) =>
      L.geoJSON(geojson, {
        filter: (feature) => currentLayerKey(feature.properties?.facility_type_code) === key,
        pointToLayer: (feature, latlng) => {
          const zoneType = zoneTypeInfo(feature.properties?.facility_type_code);
          return L.circleMarker(latlng, {
            radius: 4,
            color: "#ffffff",
            weight: 1,
            fillColor: zoneType.color,
            fillOpacity: 0.9,
          });
        },
        onEachFeature: (feature, itemLayer) => {
          const props = enrichReviewProperties({
            layer_type: "Point",
            ...(feature.properties || {}),
          });
          feature.properties = props;
          itemLayer.bindPopup(popupContent(props));
        },
      }).addTo(layerGroups[key]),
    );
}

function addChangeLayer(geojson) {
  const layers = [];
  (geojson.features || []).forEach((feature) => {
    feature.properties = featureProperties(feature);
    const category = changeCategory(feature.properties?.change_type);
    const layer = L.geoJSON(feature, {
      style: (item) => ({
        color: changeColor(item.properties?.change_type),
        weight: 3,
        opacity: 0.9,
        fillColor: changeColor(item.properties?.change_type),
        fillOpacity: 0.16,
      }),
      pointToLayer: (item, latlng) =>
        L.circleMarker(latlng, {
          radius: 7,
          color: "#ffffff",
          weight: 2,
          fillColor: changeColor(item.properties?.change_type),
          fillOpacity: 0.95,
        }),
      onEachFeature: (item, itemLayer) => {
        const props = enrichReviewProperties(item.properties || {});
        item.properties = props;
        itemLayer.bindPopup(popupContent(props));
        state.eventLayers.set(eventKey(props), itemLayer);
      },
    }).addTo(layerGroups[category]);
    layers.push(layer);
  });
  return layers;
}

function bindLayerToggles() {
  document.querySelectorAll("[data-layer]").forEach((input) => {
    input.addEventListener("change", () => {
      const group = layerGroups[input.dataset.layer];
      if (input.checked) {
        group.addTo(map);
      } else {
        group.removeFrom(map);
      }
    });
  });
}

function bindActivityTabs() {
  document.querySelectorAll(".activity-tab").forEach((button) => {
    button.addEventListener("click", () => {
      const selectedPanel = button.dataset.panel;
      document.querySelectorAll(".activity-tab").forEach((tabButton) => {
        const isActive = tabButton === button;
        tabButton.classList.toggle("active", isActive);
        tabButton.setAttribute("aria-selected", String(isActive));
      });
      document.querySelectorAll(".activity-panel").forEach((panel) => {
        const isActive = panel.id === `${selectedPanel}-panel`;
        panel.classList.toggle("active", isActive);
        panel.hidden = !isActive;
      });
    });
  });
}

async function main() {
  bindLayerToggles();
  bindActivityTabs();
  document.getElementById("event-search").addEventListener("input", renderEvents);
  document.getElementById("event-type").addEventListener("change", renderEvents);

  const [overview, events, zones, points, changeZones, changePoints, timelines] = await Promise.all([
    loadJson("data/overview.json"),
    loadJson("data/change_events.json"),
    loadJson("data/current_zones.geojson"),
    loadJson("data/current_points.geojson"),
    loadJson("data/change_zones.geojson"),
    loadJson("data/change_points.geojson"),
    loadJson("data/timelines.json"),
  ]);

  renderOverview(overview);
  state.events = events.events || [];
  state.timelines = new Map(
    (timelines.timelines || []).map((timeline) => [timeline.entity_key, timeline]),
  );
  state.eventFeatures = new Map(
    [...(changeZones.features || []), ...(changePoints.features || [])].map((feature) => {
      feature.properties = featureProperties(feature);
      return [eventKey(feature.properties), feature];
    }),
  );
  state.polygonDeletedManageNos = new Set(
    (changeZones.features || [])
      .filter((feature) => feature.properties?.change_type === "DELETED")
      .map((feature) => feature.properties?.source_manage_no)
      .filter(Boolean),
  );
  state.currentGroups = buildCurrentGroupIndex(zones, points);
  addCurrentZones(zones);
  addCurrentPoints(points);
  addChangeLayer(changeZones);
  addChangeLayer(changePoints);
  renderEvents();

  const allMapLayers = Object.values(layerGroups)
    .flatMap((group) => Object.values(group._layers))
    .filter((layer) => !layer.getLayers || layer.getLayers().length > 0);
  const allLayers = L.featureGroup(allMapLayers);
  if (allLayers.getLayers().length) {
    map.fitBounds(allLayers.getBounds().pad(0.1));
  }
  requestAnimationFrame(() => map.invalidateSize());
}

window.addEventListener("resize", () => map.invalidateSize());

new ResizeObserver(() => {
  requestAnimationFrame(() => map.invalidateSize());
}).observe(document.getElementById("map"));

main().catch((error) => {
  document.getElementById("last-updated").textContent =
    "대시보드 데이터를 불러오지 못했습니다";
  console.error(error);
});
