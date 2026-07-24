const INITIAL_VIEW = {
  lat: 37.5547,
  lng: 126.9707,
  zoom: 13,
};

const map = L.map("map", {
  preferCanvas: true,
}).setView([INITIAL_VIEW.lat, INITIAL_VIEW.lng], INITIAL_VIEW.zoom);
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
  currentItems: [],
  currentLayers: new Map(),
  currentFeatures: new Map(),
  selectedLocation: null,
  lastOsmView: {
    ...INITIAL_VIEW,
    level: leafletZoomToKakaoLevel(INITIAL_VIEW.zoom),
  },
  lastKakaoView: null,
  kakao: {
    enabled: false,
    loading: null,
    map: null,
    marker: null,
    overlays: new Map(),
    infoWindow: null,
    roadview: null,
    roadviewClient: null,
    roadviewLayerVisible: false,
  },
  timelines: new Map(),
  polygonDeletedManageNos: new Set(),
  currentGroups: new Map(),
};
document.body.dataset.dashboardVersion = "20260724-14";

const dashboardConfig = window.SAFETYZONE_CONFIG || {};
const queryParams = new URLSearchParams(window.location.search);
const kakaoJavascriptKey =
  dashboardConfig.kakaoJavascriptKey ||
  queryParams.get("kakaoKey") ||
  document.body.dataset.kakaoKey ||
  "";

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

function matchesZoneFilter(item, filterValue) {
  if (!filterValue) return true;
  const [filterKind, filterTarget] = filterValue.split(":");
  if (filterKind === "ZONE") {
    const normalized = String(item.facility_type_code || "").trim();
    if (filterTarget === "OTHER") {
      return !["1", "2", "3"].includes(normalized);
    }
    return normalized === filterTarget;
  }
  return true;
}

function currentItemKey(props) {
  return `${props.layer_type}:${props.facility_id || props.source_manage_no || props.zone_group_id}`;
}

function buildCurrentItems(zones, points) {
  return [...(zones.features || []), ...(points.features || [])]
    .map((feature) => ({
      layer_type: feature.geometry?.type === "Point" ? "Point" : "Polygon",
      ...(feature.properties || {}),
    }))
    .sort((left, right) =>
      [
        zoneTypeInfo(left.facility_type_code).label.localeCompare(
          zoneTypeInfo(right.facility_type_code).label,
          "ko-KR",
        ),
        String(left.facility_name || "").localeCompare(String(right.facility_name || ""), "ko-KR"),
        String(left.layer_type || "").localeCompare(String(right.layer_type || ""), "ko-KR"),
      ].find((result) => result !== 0) || 0,
    );
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

function centerFromFeature(feature) {
  const bounds = boundsFromFeature(feature);
  return bounds?.isValid() ? bounds.getCenter() : null;
}

function setSelectedLocation(latlng, props = {}) {
  if (!latlng) return;
  state.selectedLocation = {
    lat: latlng.lat,
    lng: latlng.lng,
    title: props.facility_name || "선택 위치",
    props,
  };
  syncKakaoLocation({ pan: true });
}

function isMobileLayout() {
  return window.matchMedia("(max-width: 900px)").matches;
}

function setPanelCollapsed(collapsed) {
  const shouldCollapse = Boolean(collapsed) && isMobileLayout();
  document.body.classList.toggle("panel-collapsed", shouldCollapse);
  const button = document.querySelector(".panel-toggle");
  if (!button) return;
  button.setAttribute("aria-expanded", String(!shouldCollapse));
  button.textContent = shouldCollapse ? "현황판 열기" : "현황판 접기";
}

function collapsePanelForMapFocus() {
  if (isMobileLayout()) setPanelCollapsed(true);
}

function leafletZoomToKakaoLevel(zoom) {
  return Math.max(1, Math.min(14, 18 - Math.round(zoom || 7)));
}

function kakaoLevelToLeafletZoom(level) {
  return Math.max(5, Math.min(19, 18 - Math.round(level || 7)));
}

function currentOsmView() {
  const center = map.getCenter();
  return {
    lat: center.lat,
    lng: center.lng,
    zoom: map.getZoom(),
    level: leafletZoomToKakaoLevel(map.getZoom()),
  };
}

function currentKakaoView() {
  if (!state.kakao.enabled) return null;
  const center = state.kakao.map.getCenter();
  return {
    lat: center.getLat(),
    lng: center.getLng(),
    level: state.kakao.map.getLevel(),
    zoom: kakaoLevelToLeafletZoom(state.kakao.map.getLevel()),
  };
}

function rememberVisibleMapView() {
  if (!document.getElementById("map").hidden) {
    state.lastOsmView = currentOsmView();
  }
  if (state.kakao.enabled && !document.getElementById("kakao-map").hidden) {
    state.lastKakaoView = currentKakaoView();
  }
}

function kakaoPositionFromLatLng(latlng) {
  return new kakao.maps.LatLng(latlng.lat, latlng.lng);
}

function kakaoPathFromRing(ring) {
  return ring
    .filter((coordinate) => Array.isArray(coordinate) && coordinate.length >= 2)
    .map(([lng, lat]) => new kakao.maps.LatLng(lat, lng));
}

function polygonRingsFromGeometry(geometry) {
  if (!geometry) return [];
  if (geometry.type === "Polygon") return geometry.coordinates || [];
  if (geometry.type === "MultiPolygon") {
    return (geometry.coordinates || []).flatMap((polygon) => polygon || []);
  }
  return [];
}

function kakaoPointFromFeature(feature) {
  const geometry = feature?.geometry;
  if (geometry?.type === "Point") {
    const [lng, lat] = geometry.coordinates;
    return new kakao.maps.LatLng(lat, lng);
  }
  const center = centerFromFeature(feature);
  return center ? kakaoPositionFromLatLng(center) : null;
}

function kakaoOverlayStyle(props, feature) {
  if (props.change_type) {
    return {
      color: changeColor(props.change_type),
      weight: 3,
      opacity: 0.9,
      fillColor: changeColor(props.change_type),
      fillOpacity: feature.geometry?.type === "Point" ? 0.95 : 0.16,
      radius: 7,
    };
  }
  const zoneType = zoneTypeInfo(props.facility_type_code);
  return {
    color: zoneType.color,
    weight: feature.geometry?.type === "Point" ? 1 : 2,
    opacity: 0.85,
    fillColor: zoneType.color,
    fillOpacity: feature.geometry?.type === "Point" ? 0.9 : zoneType.fillOpacity,
    radius: 5,
  };
}

function activeLayerKeys() {
  return new Set(
    [...document.querySelectorAll("[data-layer]")]
      .filter((input) => input.checked)
      .map((input) => input.dataset.layer),
  );
}

function kakaoCategoryForProps(props) {
  return props.change_type ? changeCategory(props.change_type) : currentLayerKey(props.facility_type_code);
}

function setKakaoOverlayVisibility() {
  if (!state.kakao.enabled) return;
  const visibleKeys = activeLayerKeys();
  state.kakao.overlays.forEach((items, category) => {
    const targetMap = visibleKeys.has(category) ? state.kakao.map : null;
    items.forEach((overlay) => overlay.setMap(targetMap));
  });
}

function openKakaoInfo(feature, props, position) {
  if (!state.kakao.infoWindow || !position) return;
  setSelectedLocation({ lat: position.getLat(), lng: position.getLng() }, props);
  state.kakao.infoWindow.setContent(`<div class="kakao-info">${popupContent(props)}</div>`);
  state.kakao.infoWindow.setPosition(position);
  state.kakao.infoWindow.open(state.kakao.map);
}

function focusKakaoFeature(feature, props, bounds) {
  if (!state.kakao.enabled || !feature) return false;
  const position = kakaoPointFromFeature(feature);
  if (!position) return false;
  state.kakao.map.setCenter(position);
  if (feature.geometry?.type === "Point" || bounds?.getNorthEast?.().equals(bounds.getSouthWest())) {
    state.kakao.map.setLevel(Math.min(state.kakao.map.getLevel(), 3));
  }
  openKakaoInfo(feature, props, position);
  state.lastKakaoView = currentKakaoView();
  return true;
}

function createKakaoPointMarker(feature, props, position, style) {
  const marker = document.createElement("button");
  marker.type = "button";
  marker.className = `kakao-point-marker${props.change_type ? " has-change" : ""}`;
  marker.style.setProperty("--marker-color", style.fillColor);
  marker.title = props.facility_name || "Safety zone";
  marker.setAttribute("aria-label", marker.title);
  marker.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openKakaoInfo(feature, props, position);
  });
  return marker;
}

function registerKakaoOverlay(category, overlay) {
  if (!state.kakao.overlays.has(category)) state.kakao.overlays.set(category, []);
  state.kakao.overlays.get(category).push(overlay);
}

function addKakaoFeature(feature, rawProps = {}) {
  const props = enrichReviewProperties(rawProps);
  const category = kakaoCategoryForProps(props);
  const style = kakaoOverlayStyle(props, feature);

  if (feature.geometry?.type === "Point") {
    const position = kakaoPointFromFeature(feature);
    if (!position) return;
    const overlay = new kakao.maps.CustomOverlay({
      position,
      content: createKakaoPointMarker(feature, props, position, style),
      xAnchor: 0.5,
      yAnchor: 0.5,
      zIndex: props.change_type ? 5 : 3,
    });
    registerKakaoOverlay(category, overlay);
    return;
  }

  polygonRingsFromGeometry(feature.geometry).forEach((ring) => {
    const path = kakaoPathFromRing(ring);
    if (path.length < 3) return;
    const overlay = new kakao.maps.Polygon({
      path,
      strokeWeight: style.weight,
      strokeColor: style.color,
      strokeOpacity: style.opacity,
      fillColor: style.fillColor,
      fillOpacity: style.fillOpacity,
      zIndex: props.change_type ? 4 : 2,
    });
    const position = kakaoPointFromFeature(feature);
    kakao.maps.event.addListener(overlay, "click", () => openKakaoInfo(feature, props, position));
    registerKakaoOverlay(category, overlay);
  });
}

function buildKakaoOverlays() {
  if (!state.kakao.enabled || state.kakao.overlays.size) return;
  state.currentFeatures.forEach((feature) => addKakaoFeature(feature, feature.properties || {}));
  state.eventFeatures.forEach((feature) => addKakaoFeature(feature, feature.properties || {}));
  setKakaoOverlayVisibility();
}

function showRoadviewStatus(message) {
  const status = document.getElementById("roadview-status");
  if (status) status.textContent = message;
}

function roadviewPanelBounds(panelRect) {
  const mapRect = document.querySelector(".map-panel").getBoundingClientRect();
  const margin = window.innerWidth <= 900 ? 12 : 16;
  const sideRect = document.querySelector(".side-panel")?.getBoundingClientRect();
  let minX = mapRect.left + margin;
  let minY = mapRect.top + margin;
  let maxX = mapRect.right - panelRect.width - margin;
  let maxY = mapRect.bottom - panelRect.height - margin;

  if (window.innerWidth <= 900 && sideRect) {
    maxY = Math.min(maxY, sideRect.top - panelRect.height - margin);
  }

  return {
    mapRect,
    minX,
    minY,
    maxX: Math.max(minX, maxX),
    maxY: Math.max(minY, maxY),
  };
}

function placeRoadviewPanelAt(panel, bounds, clientX, clientY) {
  panel.style.left = `${clientX - bounds.mapRect.left}px`;
  panel.style.top = `${clientY - bounds.mapRect.top}px`;
  panel.style.right = "auto";
  panel.style.bottom = "auto";
}

function clampRoadviewPanel() {
  const panel = document.querySelector(".roadview-panel");
  if (!panel || panel.hidden) return;
  const panelRect = panel.getBoundingClientRect();
  const bounds = roadviewPanelBounds(panelRect);
  const nextX = Math.max(bounds.minX, Math.min(bounds.maxX, panelRect.left));
  const nextY = Math.max(bounds.minY, Math.min(bounds.maxY, panelRect.top));
  placeRoadviewPanelAt(panel, bounds, nextX, nextY);
}

function roadviewResizeLimits(panel) {
  const mapRect = document.querySelector(".map-panel").getBoundingClientRect();
  const sideRect = document.querySelector(".side-panel")?.getBoundingClientRect();
  const panelRect = panel.getBoundingClientRect();
  const roadview = document.getElementById("roadview");
  const roadviewRect = roadview.getBoundingClientRect();
  const margin = window.innerWidth <= 900 ? 12 : 16;
  const bottomLimit =
    window.innerWidth <= 900 && sideRect ? Math.min(mapRect.bottom, sideRect.top - margin) : mapRect.bottom - margin;
  const fixedPanelHeight = panelRect.height - roadviewRect.height;
  const minWidth = window.innerWidth <= 520 ? 260 : 320;
  const minRoadviewHeight = window.innerWidth <= 520 ? 180 : 220;

  return {
    minWidth,
    minRoadviewHeight,
    maxWidth: Math.max(minWidth, mapRect.right - panelRect.left - margin),
    maxRoadviewHeight: Math.max(minRoadviewHeight, bottomLimit - panelRect.top - fixedPanelHeight),
  };
}

function resizeRoadviewPanel(panel, width, roadviewHeight) {
  const limits = roadviewResizeLimits(panel);
  const nextWidth = Math.max(limits.minWidth, Math.min(limits.maxWidth, width));
  const nextRoadviewHeight = Math.max(
    limits.minRoadviewHeight,
    Math.min(limits.maxRoadviewHeight, roadviewHeight),
  );
  panel.style.width = `${nextWidth}px`;
  document.getElementById("roadview").style.height = `${nextRoadviewHeight}px`;
  clampRoadviewPanel();
  if (state.kakao.enabled) {
    state.kakao.map.relayout();
    state.kakao.roadview.relayout();
  }
}

function setRoadviewPanelVisible(visible) {
  const panel = document.querySelector(".roadview-panel");
  panel.hidden = !visible;
  if (visible) requestAnimationFrame(clampRoadviewPanel);
}

function loadKakaoSdk() {
  if (!kakaoJavascriptKey) {
    return Promise.reject(new Error("Kakao JavaScript key is not configured."));
  }
  if (window.kakao?.maps) {
    return new Promise((resolve) => window.kakao.maps.load(resolve));
  }
  if (state.kakao.loading) return state.kakao.loading;

  state.kakao.loading = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${encodeURIComponent(
      kakaoJavascriptKey,
    )}&autoload=false`;
    script.async = true;
    script.onload = () => window.kakao.maps.load(resolve);
    script.onerror = () => reject(new Error("Failed to load Kakao Maps SDK."));
    document.head.appendChild(script);
  });
  return state.kakao.loading;
}

async function ensureKakaoMap() {
  if (state.kakao.enabled) return true;
  await loadKakaoSdk();
  const location = currentOsmView();
  const center = new kakao.maps.LatLng(location.lat, location.lng);
  state.kakao.map = new kakao.maps.Map(document.getElementById("kakao-map"), {
    center,
    level: location.level || 5,
  });
  state.kakao.marker = new kakao.maps.Marker({
    map: state.kakao.map,
    position: center,
  });
  state.kakao.infoWindow = new kakao.maps.InfoWindow({ removable: true });
  state.kakao.roadview = new kakao.maps.Roadview(document.getElementById("roadview"));
  state.kakao.roadviewClient = new kakao.maps.RoadviewClient();
  kakao.maps.event.addListener(state.kakao.roadview, "position_changed", () => {
    const position = state.kakao.roadview.getPosition();
    if (!position) return;
    state.kakao.marker.setPosition(position);
    state.kakao.map.setCenter(position);
    if (state.selectedLocation) {
      state.selectedLocation.lat = position.getLat();
      state.selectedLocation.lng = position.getLng();
    }
    state.lastKakaoView = currentKakaoView();
  });
  kakao.maps.event.addListener(state.kakao.map, "click", (mouseEvent) => {
    if (document.body.dataset.mapMode !== "roadview") return;
    moveRoadviewToPosition(mouseEvent.latLng, "지정한 위치 주변 로드뷰를 찾는 중입니다.");
  });
  state.kakao.enabled = true;
  buildKakaoOverlays();
  syncKakaoLocation();
  return true;
}

function syncKakaoLocation({ pan = false } = {}) {
  if (!state.kakao.enabled || !state.selectedLocation) return;
  const position = new kakao.maps.LatLng(state.selectedLocation.lat, state.selectedLocation.lng);
  if (pan) state.kakao.map.setCenter(position);
  state.kakao.marker.setPosition(position);
  document.getElementById("roadview-title").textContent = state.selectedLocation.title;
}

function setRoadviewLayerVisible(visible) {
  if (!state.kakao.enabled || state.kakao.roadviewLayerVisible === visible) return;
  if (visible) {
    state.kakao.map.addOverlayMapTypeId(kakao.maps.MapTypeId.ROADVIEW);
  } else {
    state.kakao.map.removeOverlayMapTypeId(kakao.maps.MapTypeId.ROADVIEW);
  }
  state.kakao.roadviewLayerVisible = visible;
}

function moveRoadviewToPosition(position, loadingMessage) {
  if (!state.kakao.enabled || !position) return;
  const search = (radius) => {
    state.kakao.roadviewClient.getNearestPanoId(position, radius, (panoId) => {
      if (!panoId && radius < 300) {
        search(300);
        return;
      }
      if (!panoId) {
        showRoadviewStatus("주변 300m 안에서 로드뷰를 찾지 못했습니다.");
        return;
      }
      state.kakao.marker.setPosition(position);
      state.kakao.map.setCenter(position);
      state.kakao.roadview.setPanoId(panoId, position);
      showRoadviewStatus("로드뷰 위치가 지도와 동기화되었습니다.");
      state.lastKakaoView = currentKakaoView();
    });
  };
  showRoadviewStatus(loadingMessage || "주변 로드뷰를 찾는 중입니다.");
  search(100);
}

async function setMapMode(mode) {
  const isOsm = mode === "osm";
  const isKakaoMode = mode === "kakao" || mode === "roadview";
  rememberVisibleMapView();
  const osmViewBeforeSwitch = state.lastOsmView;
  const kakaoViewBeforeSwitch = state.lastKakaoView;
  if (isKakaoMode) {
    try {
      await ensureKakaoMap();
    } catch (error) {
      showRoadviewStatus("Kakao JavaScript 키와 도메인 등록이 필요합니다.");
      console.warn(error);
      return;
    }
  }

  document.body.dataset.mapMode = mode;
  document.getElementById("map").hidden = !isOsm;
  document.getElementById("kakao-map").hidden = isOsm;
  if (mode !== "roadview") setRoadviewPanelVisible(false);
  document.querySelectorAll(".map-mode-button[data-map-mode]").forEach((button) => {
    button.classList.toggle("active", button.dataset.mapMode === mode);
  });

  if (isKakaoMode) {
    if (mode === "kakao") {
      const view = kakaoViewBeforeSwitch || osmViewBeforeSwitch;
      state.kakao.map.setCenter(new kakao.maps.LatLng(view.lat, view.lng));
      state.kakao.map.setLevel(view.level);
    }
    setRoadviewLayerVisible(mode === "roadview");
    buildKakaoOverlays();
    requestAnimationFrame(() => {
      state.kakao.map.relayout();
      if (mode === "kakao") {
        const view = kakaoViewBeforeSwitch || osmViewBeforeSwitch;
        state.kakao.map.setCenter(new kakao.maps.LatLng(view.lat, view.lng));
        state.kakao.map.setLevel(view.level);
        syncKakaoLocation({ pan: false });
        state.lastKakaoView = currentKakaoView();
      } else {
        syncKakaoLocation({ pan: true });
        state.lastKakaoView = currentKakaoView();
      }
      setKakaoOverlayVisibility();
    });
  } else {
    setRoadviewLayerVisible(false);
    const view = kakaoViewBeforeSwitch || state.lastOsmView;
    map.setView([view.lat, view.lng], view.zoom || kakaoLevelToLeafletZoom(view.level), {
      animate: false,
    });
    requestAnimationFrame(() => {
      map.invalidateSize();
      map.setView([view.lat, view.lng], view.zoom || kakaoLevelToLeafletZoom(view.level), {
        animate: false,
      });
      state.lastOsmView = currentOsmView();
    });
  }
}

async function openRoadview() {
  const location = state.selectedLocation;
  collapsePanelForMapFocus();
  setRoadviewPanelVisible(true);

  try {
    await setMapMode("roadview");
    if (!location) {
      document.getElementById("roadview-title").textContent = "로드뷰";
      showRoadviewStatus("지도에서 위치를 클릭하면 주변 로드뷰를 찾습니다.");
      return;
    }
    document.getElementById("roadview-title").textContent = location.title;
    const position = new kakao.maps.LatLng(location.lat, location.lng);
    moveRoadviewToPosition(position, "가장 가까운 로드뷰를 찾는 중입니다.");
  } catch (error) {
    showRoadviewStatus("Kakao JavaScript 키와 도메인 등록이 필요합니다.");
    console.warn(error);
  }
}

async function toggleRoadview() {
  if (document.body.dataset.mapMode === "roadview") {
    setRoadviewPanelVisible(false);
    await setMapMode("kakao");
    return;
  }
  await openRoadview();
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
  collapsePanelForMapFocus();
  const center = bounds.getCenter();
  setSelectedLocation(center, event);
  if (document.body.dataset.mapMode !== "osm" && focusKakaoFeature(feature, event, bounds)) {
    document.body.dataset.lastPopup = key;
    return;
  }
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

function focusCurrentItem(item) {
  const category = currentLayerKey(item.facility_type_code);
  ensureLayerVisible(category);

  const key = currentItemKey(item);
  const layer = state.currentLayers.get(key);
  const feature = state.currentFeatures.get(key);
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
  collapsePanelForMapFocus();
  const center = bounds.getCenter();
  setSelectedLocation(center, item);
  if (document.body.dataset.mapMode !== "osm" && focusKakaoFeature(feature, item, bounds)) {
    document.body.dataset.lastPopup = key;
    return;
  }
  if (item.layer_type === "Point" || bounds.getNorthEast().equals(bounds.getSouthWest())) {
    map.setView(center, Math.max(map.getZoom(), 17), { animate: true });
  } else {
    map.fitBounds(bounds.pad(0.35), { maxZoom: 17, animate: true });
  }
  L.popup({ maxWidth: 320 })
    .setLatLng(center)
    .setContent(popupContent(item))
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
    <button class="popup-roadview-button" type="button">카카오 로드뷰</button>
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

function renderCurrentItems() {
  const query = document.getElementById("current-search").value.trim().toLowerCase();
  const filterValue = document.getElementById("current-zone-type").value;
  const filtered = state.currentItems.filter((item) => {
    const haystack = [
      item.facility_name,
      item.source_manage_no,
      item.sgg_code,
      item.zone_group_id,
      item.layer_type,
      item.facility_type_code,
      zoneTypeInfo(item.facility_type_code).label,
    ]
      .join(" ")
      .toLowerCase();
    return matchesZoneFilter(item, filterValue) && (!query || haystack.includes(query));
  });

  document.getElementById("current-total").textContent = `${numberText(filtered.length)}건`;
  const currentList = document.getElementById("current-list");
  currentList.replaceChildren(
    ...filtered.slice(0, 200).map((item) => {
      const zoneType = zoneTypeInfo(item.facility_type_code);
      const listItem = document.createElement("li");
      listItem.className = "current-item";
      listItem.tabIndex = 0;
      listItem.setAttribute("role", "button");
      listItem.setAttribute("aria-label", `${item.facility_name || "이름 없음"} 위치로 이동`);
      listItem.innerHTML = `
        <div class="event-topline">
          <span class="event-title">${item.facility_name || "이름 없음"}</span>
          <span class="badge current-badge">${item.layer_type}</span>
        </div>
        <div class="event-meta">
          <span class="zone-type" style="--zone-type-color: ${zoneType.color}">${zoneType.label}</span><br>
          ${item.layer_type} · ${item.source_manage_no || "-"} · ${item.sgg_code || "-"}<br>
          그룹 ${item.zone_group_id || "-"}
          ${
            item.api_last_modified_on
              ? `<br><span>API 최종수정 ${formatApiDate(item.api_last_modified_on)}</span>`
              : ""
          }
        </div>
      `;
      listItem.addEventListener("click", () => {
        document.querySelectorAll(".current-item.selected").forEach((selectedItem) => {
          selectedItem.classList.remove("selected");
        });
        listItem.classList.add("selected");
        focusCurrentItem(item);
      });
      listItem.addEventListener("keydown", (keyboardEvent) => {
        if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
          keyboardEvent.preventDefault();
          focusCurrentItem(item);
        }
      });
      return listItem;
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
          state.currentLayers.set(currentItemKey(props), itemLayer);
          state.currentFeatures.set(currentItemKey(props), feature);
          itemLayer.on("click", () => setSelectedLocation(centerFromFeature(feature), props));
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
          state.currentLayers.set(currentItemKey(props), itemLayer);
          state.currentFeatures.set(currentItemKey(props), feature);
          itemLayer.on("click", () => setSelectedLocation(centerFromFeature(feature), props));
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
        itemLayer.on("click", () => setSelectedLocation(centerFromFeature(item), props));
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
      setKakaoOverlayVisibility();
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

function bindMapTools() {
  map.on("moveend zoomend", () => {
    if (!document.getElementById("map").hidden) state.lastOsmView = currentOsmView();
  });
  document.querySelector(".panel-toggle").addEventListener("click", () => {
    setPanelCollapsed(!document.body.classList.contains("panel-collapsed"));
  });
  document.querySelectorAll(".map-mode-button[data-map-mode]").forEach((button) => {
    if (button.classList.contains("roadview-action")) return;
    button.addEventListener("click", () => setMapMode(button.dataset.mapMode));
  });
  document.querySelector(".roadview-action").addEventListener("click", toggleRoadview);
  document.addEventListener("click", (event) => {
    if (event.target.closest(".popup-roadview-button")) openRoadview();
  });
  document.getElementById("roadview-close").addEventListener("click", () => {
    setRoadviewPanelVisible(false);
    if (document.body.dataset.mapMode === "roadview") setMapMode("kakao");
  });
}

function bindRoadviewDrag() {
  const panel = document.querySelector(".roadview-panel");
  const header = document.querySelector(".roadview-header");
  let dragState = null;

  header.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    const panelRect = panel.getBoundingClientRect();
    const bounds = roadviewPanelBounds(panelRect);
    dragState = {
      offsetX: event.clientX - panelRect.left,
      offsetY: event.clientY - panelRect.top,
      minX: bounds.minX,
      minY: bounds.minY,
      maxX: bounds.maxX,
      maxY: bounds.maxY,
      mapRect: bounds.mapRect,
    };
    panel.classList.add("dragging");
    header.setPointerCapture(event.pointerId);
  });

  header.addEventListener("pointermove", (event) => {
    if (!dragState) return;
    const nextX = Math.max(dragState.minX, Math.min(dragState.maxX, event.clientX - dragState.offsetX));
    const nextY = Math.max(dragState.minY, Math.min(dragState.maxY, event.clientY - dragState.offsetY));
    placeRoadviewPanelAt(panel, dragState, nextX, nextY);
  });

  const stopDrag = (event) => {
    if (!dragState) return;
    dragState = null;
    panel.classList.remove("dragging");
    if (header.hasPointerCapture(event.pointerId)) header.releasePointerCapture(event.pointerId);
  };
  header.addEventListener("pointerup", stopDrag);
  header.addEventListener("pointercancel", stopDrag);
}

function bindRoadviewResize() {
  const panel = document.querySelector(".roadview-panel");
  const handle = document.querySelector(".roadview-resize");
  const roadview = document.getElementById("roadview");
  let resizeState = null;

  handle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const panelRect = panel.getBoundingClientRect();
    resizeState = {
      startX: event.clientX,
      startY: event.clientY,
      width: panelRect.width,
      roadviewHeight: roadview.getBoundingClientRect().height,
    };
    panel.classList.add("resizing");
    handle.setPointerCapture(event.pointerId);
  });

  handle.addEventListener("pointermove", (event) => {
    if (!resizeState) return;
    resizeRoadviewPanel(
      panel,
      resizeState.width + event.clientX - resizeState.startX,
      resizeState.roadviewHeight + event.clientY - resizeState.startY,
    );
  });

  const stopResize = (event) => {
    if (!resizeState) return;
    resizeState = null;
    panel.classList.remove("resizing");
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
  };
  handle.addEventListener("pointerup", stopResize);
  handle.addEventListener("pointercancel", stopResize);
}

async function main() {
  bindLayerToggles();
  bindActivityTabs();
  bindMapTools();
  bindRoadviewDrag();
  bindRoadviewResize();
  document.getElementById("event-search").addEventListener("input", renderEvents);
  document.getElementById("event-type").addEventListener("change", renderEvents);
  document.getElementById("current-search").addEventListener("input", renderCurrentItems);
  document.getElementById("current-zone-type").addEventListener("change", renderCurrentItems);

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
  state.currentItems = buildCurrentItems(zones, points);
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
  buildKakaoOverlays();
  renderEvents();
  renderCurrentItems();

  requestAnimationFrame(() => map.invalidateSize());
}

function relayoutMaps() {
  if (!isMobileLayout()) setPanelCollapsed(false);
  map.invalidateSize();
  const roadviewPanel = document.querySelector(".roadview-panel");
  if (roadviewPanel && !roadviewPanel.hidden) {
    resizeRoadviewPanel(
      roadviewPanel,
      roadviewPanel.getBoundingClientRect().width,
      document.getElementById("roadview").getBoundingClientRect().height,
    );
  }
  if (state.kakao.enabled) {
    state.kakao.map.relayout();
    state.kakao.roadview.relayout();
    syncKakaoLocation();
  }
}

window.addEventListener("resize", () => relayoutMaps());

new ResizeObserver(() => {
  requestAnimationFrame(relayoutMaps);
}).observe(document.getElementById("map"));

main().catch((error) => {
  document.getElementById("last-updated").textContent =
    "대시보드 데이터를 불러오지 못했습니다";
  console.error(error);
});
