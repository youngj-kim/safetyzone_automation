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
  ngiiZones: L.layerGroup().addTo(map),
  ngiiMatchedLinks: L.layerGroup().addTo(map),
  ngiiReviewLinks: L.layerGroup().addTo(map),
};

const state = {
  events: [],
  eventLayers: new Map(),
  eventFeatures: new Map(),
  currentItems: [],
  currentLayers: new Map(),
  currentFeatures: new Map(),
  currentIndex: null,
  currentSearchItems: [],
  currentSearchIndexLoading: null,
  selectedSido: "11",
  currentRegionLoading: null,
  language: localStorage.getItem("dashboardLanguage") || "ko",
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
    changeOverlaysBuilt: false,
  },
  timelines: new Map(),
  polygonDeletedManageNos: new Set(),
  currentGroups: new Map(),
  changeSummaryBySido: null,
  changeExclusions: null,
  ngiiSummary: null,
  ngiiItems: [],
  ngiiLayers: new Map(),
  ngiiFeatures: new Map(),
  ngiiRepresentativeLinkFeatures: [],
  ngiiReviewLinkFeatures: [],
};
document.body.dataset.dashboardVersion = "20260728-2";

const dashboardConfig = window.SAFETYZONE_CONFIG || {};
const queryParams = new URLSearchParams(window.location.search);
const kakaoJavascriptKey =
  dashboardConfig.kakaoJavascriptKey ||
  queryParams.get("kakaoKey") ||
  document.body.dataset.kakaoKey ||
  "";

const I18N = {
  ko: {
    appTitle: "보호구역 변경 현황",
    loadingData: "데이터를 불러오는 중",
    sgg: "시군구",
    child: "어린이",
    senior: "노인",
    disabled: "장애인",
    other: "기타",
    new: "신규",
    changed: "변경",
    review: "삭제(검토)",
    recentChanges: "최근 변경",
    currentObjects: "현재 객체",
    monitoringRuns: "모니터링 이력",
    searchPlaceholder: "시설명, 관리번호, 시군구 검색",
    allChangeStatus: "전체 변경 상태",
    attributeChanged: "속성변경",
    geometryChanged: "도형변경",
    geometryAttributeChanged: "도형+속성변경",
    pointChanged: "위치변경",
    pointAttributeChanged: "위치+속성변경",
    deleted: "삭제",
    missingReview: "누락 검토",
    allZoneTypes: "전체 보호구역 종류",
    panelOpen: "현황판 열기",
    panelClose: "현황판 접기",
    roadview: "로드뷰",
    roadviewHint: "보호구역을 선택하면 로드뷰를 확인할 수 있습니다.",
    latestRun: "최근 실행",
    noRuns: "실행 이력이 없습니다",
    countSuffix: "건",
    collected: "수집",
    polygonChanged: "Polygon 변경",
    pointChangedCount: "Point 변경",
    failureReason: "실패 사유",
    noName: "이름 없음",
    moveToLocation: "위치로 이동",
    type: "종류",
    manageNo: "관리번호",
    group: "그룹",
    detected: "감지",
    updated: "시스템 갱신",
    apiFirst: "API 최초등록",
    apiLast: "API 최종수정",
    reviewLabel: "검토",
    kakaoRoadview: "카카오 로드뷰",
    noRegion: "선택된 지역이 없습니다.",
    noChangesAfterBaseline: "기준선 이후 전국 변경 이벤트가 없습니다.",
  },
  en: {
    appTitle: "Safety Zone Changes",
    loadingData: "Loading data",
    sgg: "District",
    child: "Child",
    senior: "Senior",
    disabled: "Disabled",
    other: "Other",
    new: "New",
    changed: "Changed",
    review: "Deleted/Review",
    recentChanges: "Recent Changes",
    currentObjects: "Current Objects",
    monitoringRuns: "Monitoring Runs",
    searchPlaceholder: "Search facility, management no., district",
    allChangeStatus: "All Change Status",
    attributeChanged: "Attribute Changed",
    geometryChanged: "Geometry Changed",
    geometryAttributeChanged: "Geometry + Attribute Changed",
    pointChanged: "Location Changed",
    pointAttributeChanged: "Location + Attribute Changed",
    deleted: "Deleted",
    missingReview: "Missing Review",
    allZoneTypes: "All Safety Zone Types",
    panelOpen: "Open Panel",
    panelClose: "Collapse Panel",
    roadview: "Roadview",
    roadviewHint: "Select a safety zone to inspect Roadview imagery.",
    latestRun: "Latest Run",
    noRuns: "No monitoring runs",
    countSuffix: "",
    collected: "Fetched",
    polygonChanged: "Polygon Changes",
    pointChangedCount: "Point Changes",
    failureReason: "Failure reason",
    noName: "Unnamed",
    moveToLocation: "Move to location",
    type: "Type",
    manageNo: "Management No.",
    group: "Group",
    detected: "Detected",
    updated: "System Updated",
    apiFirst: "API First Registered",
    apiLast: "API Last Modified",
    reviewLabel: "Review",
    kakaoRoadview: "Kakao Roadview",
    noRegion: "No region selected.",
    noChangesAfterBaseline: "No nationwide change events after baseline.",
  },
};

const CHANGE_LABELS = {
  NEW: { ko: "신규", en: "New" },
  ATTRIBUTE_CHANGED: { ko: "속성변경", en: "Attribute Changed" },
  GEOMETRY_CHANGED: { ko: "도형변경", en: "Geometry Changed" },
  GEOMETRY_ATTRIBUTE_CHANGED: { ko: "도형+속성변경", en: "Geometry + Attribute Changed" },
  POINT_CHANGED: { ko: "위치변경", en: "Location Changed" },
  POINT_ATTRIBUTE_CHANGED: { ko: "위치+속성변경", en: "Location + Attribute Changed" },
  DELETED: { ko: "삭제", en: "Deleted" },
  MISSING: { ko: "누락 검토", en: "Missing Review" },
};

const SIDO_NAME_EN = {
  "11": "Seoul",
  "12": "Jeollanam-do",
  "26": "Busan",
  "27": "Daegu",
  "28": "Incheon",
  "30": "Daejeon",
  "31": "Ulsan",
  "36": "Sejong",
  "41": "Gyeonggi-do",
  "43": "Chungcheongbuk-do",
  "44": "Chungcheongnam-do",
  "47": "Gyeongsangbuk-do",
  "48": "Gyeongsangnam-do",
  "50": "Jeju",
  "51": "Gangwon State",
  "52": "Jeonbuk State",
};

const FACILITY_SUFFIX_RULES = [
  ["장애인복지관", "Welfare Center for Disabled People"],
  ["노인복지관", "Senior Welfare Center"],
  ["초등학교", "Elementary School"],
  ["중학교", "Middle School"],
  ["고등학교", "High School"],
  ["유치원", "Kindergarten"],
  ["어린이집", "Childcare Center"],
  ["경로당", "Senior Center"],
  ["복지관", "Welfare Center"],
  ["학교", "School"],
];

const HANGUL_LEADS = [
  "g",
  "kk",
  "n",
  "d",
  "tt",
  "r",
  "m",
  "b",
  "pp",
  "s",
  "ss",
  "",
  "j",
  "jj",
  "ch",
  "k",
  "t",
  "p",
  "h",
];
const HANGUL_VOWELS = [
  "a",
  "ae",
  "ya",
  "yae",
  "eo",
  "e",
  "yeo",
  "ye",
  "o",
  "wa",
  "wae",
  "oe",
  "yo",
  "u",
  "wo",
  "we",
  "wi",
  "yu",
  "eu",
  "ui",
  "i",
];
const HANGUL_TAILS = [
  "",
  "k",
  "k",
  "ks",
  "n",
  "nj",
  "nh",
  "t",
  "l",
  "lk",
  "lm",
  "lb",
  "ls",
  "lt",
  "lp",
  "lh",
  "m",
  "p",
  "ps",
  "t",
  "t",
  "ng",
  "t",
  "t",
  "k",
  "t",
  "p",
  "t",
];

function t(key) {
  return I18N[state.language]?.[key] || I18N.ko[key] || key;
}

function countText(value) {
  const count = numberText(value);
  return state.language === "ko" ? `${count}${t("countSuffix")}` : count;
}

function changeTypeLabel(type) {
  return CHANGE_LABELS[type]?.[state.language] || type || "-";
}

function formatSidoName(regionOrCode) {
  const code = typeof regionOrCode === "string" ? regionOrCode : regionOrCode?.sido_code;
  const koName = typeof regionOrCode === "string" ? regionOrCode : regionOrCode?.sido_name;
  return state.language === "en" ? SIDO_NAME_EN[code] || koName || code || "-" : koName || code || "-";
}

function romanizeHangul(text) {
  return String(text || "")
    .split("")
    .map((char) => {
      const code = char.charCodeAt(0) - 0xac00;
      if (code < 0 || code > 11171) return char;
      const lead = Math.floor(code / 588);
      const vowel = Math.floor((code % 588) / 28);
      const tail = code % 28;
      return `${HANGUL_LEADS[lead]}${HANGUL_VOWELS[vowel]}${HANGUL_TAILS[tail]}`;
    })
    .join("");
}

function titleCaseRomanized(text) {
  return romanizeHangul(text)
    .replace(/[^A-Za-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function facilityNameEn(name) {
  const rawName = String(name || "").trim();
  if (!rawName) return "";
  const rule = FACILITY_SUFFIX_RULES.find(([suffix]) => rawName.endsWith(suffix));
  if (!rule) return titleCaseRomanized(rawName) || rawName;
  const [suffix, englishSuffix] = rule;
  const baseName = rawName.slice(0, -suffix.length).trim();
  const romanizedBase = titleCaseRomanized(baseName);
  return romanizedBase ? `${romanizedBase} ${englishSuffix}` : englishSuffix;
}

function facilityNameParts(props) {
  const koName = props?.facility_name || t("noName");
  if (state.language !== "en") return { primary: koName, secondary: "" };
  const enName = facilityNameEn(koName);
  return {
    primary: enName || koName,
    secondary: enName && enName !== koName ? koName : "",
  };
}

function numberText(value) {
  return Number(value || 0).toLocaleString(state.language === "en" ? "en-US" : "ko-KR");
}

function formatDate(value) {
  if (!value) return "-";
  return new Intl.DateTimeFormat(state.language === "en" ? "en-US" : "ko-KR", {
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

function runFailureReason(errorMessage) {
  if (!errorMessage) return "";
  const message = String(errorMessage);
  if (message.includes("too many 429")) {
    return state.language === "en"
      ? "Open API request limit exceeded (429)"
      : "공공 API 요청 제한(429)으로 수집 실패";
  }
  if (message.includes("ERR_03") || message.includes("조회된 데이터가 없습니다")) {
    return state.language === "en" ? "Open API returned no data" : "공공 API 응답 데이터 없음";
  }
  if (message.includes("timeout") || message.includes("Timeout")) {
    return state.language === "en" ? "Open API response timeout" : "공공 API 응답 시간 초과";
  }
  return message
    .replace(/([?&](?:serviceKey|service_key|key|token)=)[^&\s]+/gi, "$1[REDACTED]")
    .slice(0, 160);
}

function zoneTypeInfo(code) {
  const normalized = String(code || "").trim();
  const types = {
    1: {
      label: state.language === "en" ? "Child Safety Zone" : "어린이보호구역",
      color: "#2563eb",
      fillOpacity: 0.1,
    },
    2: {
      label: state.language === "en" ? "Senior Safety Zone" : "노인보호구역",
      color: "#be185d",
      fillOpacity: 0.12,
    },
    3: {
      label: state.language === "en" ? "Disabled Safety Zone" : "장애인보호구역",
      color: "#0891b2",
      fillOpacity: 0.12,
    },
  };
  return types[normalized] || {
    label: state.language === "en" ? "Other Safety Zone" : "보호구역 유형 미분류",
    color: "#707985",
    fillOpacity: 0.08,
  };
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
  if (props.layer_type === "Point" && props.facility_id) {
    return `Point:${props.facility_id}-${props.point_ordinal ?? 0}`;
  }
  return `${props.layer_type}:${props.source_manage_no || props.zone_group_id || props.facility_id}`;
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

function renderSelectionHistory(props) {
  const panel = document.getElementById("selection-history");
  const title = document.getElementById("selection-history-title");
  const summary = document.getElementById("selection-history-summary");
  const list = document.getElementById("selection-history-list");
  if (!panel || !title || !summary || !list) return;

  const timeline = timelineForProps(props);
  const names = facilityNameParts(props);
  title.textContent = `${names.primary} 변경 이력`;
  summary.textContent = timeline
    ? timelineSummary(timeline)
    : `${props.layer_type || "객체"} · ${props.source_manage_no || props.zone_group_id || "-"}`;

  const events = (timeline?.events || []).slice(0, 8);
  const items = events.map((event) => {
    const item = document.createElement("li");
    item.textContent = `${formatDate(event.detected_at)} · ${event.layer_type} · ${changeTypeLabel(
      event.change_type,
    )}`;
    return item;
  });
  if (!items.length && props.api_last_modified_on) {
    const item = document.createElement("li");
    item.textContent = `${t("apiLast")} ${formatApiDate(props.api_last_modified_on)}`;
    items.push(item);
  }
  list.replaceChildren(...items);
  panel.hidden = false;
}

function statusHintLabel(status) {
  const labels = {
    CURRENT: { ko: "현재 유지", en: "Current" },
    NEW: { ko: "신규", en: "New" },
    UPDATED: { ko: "변경 추적", en: "Updated" },
    MISSING_REVIEW: { ko: "삭제 검토 1회", en: "Missing Review" },
    DELETE_CANDIDATE: { ko: "반복 누락, 삭제 의심", en: "Repeated Missing" },
    DELETED_CONFIRMED: { ko: "삭제 확인", en: "Deleted Confirmed" },
    RETURNED: { ko: "누락 후 재등장", en: "Returned" },
  };
  return labels[status]?.[state.language] || status || "";
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

function setSelectedLocation(latlng, props = {}) {
  if (!latlng) return;
  const names = facilityNameParts(props);
  state.selectedLocation = {
    lat: latlng.lat,
    lng: latlng.lng,
    title: names.primary || t("moveToLocation"),
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
  button.textContent = shouldCollapse ? t("panelOpen") : t("panelClose");
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

function kakaoPathFromLineCoordinates(coordinates) {
  return (coordinates || [])
    .filter((coordinate) => Array.isArray(coordinate) && coordinate.length >= 2)
    .map(([lng, lat]) => new kakao.maps.LatLng(lat, lng));
}

function linePathsFromGeometry(geometry) {
  if (!geometry) return [];
  if (geometry.type === "LineString") return [geometry.coordinates || []];
  if (geometry.type === "MultiLineString") return geometry.coordinates || [];
  return [];
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
  if (props.ngii_bucket) {
    const bucket = ngiiBucketInfo(props.ngii_bucket);
    return {
      color: bucket.color,
      weight: props.link_role || props.link_id ? 4 : 2,
      opacity: props.link_role || props.link_id ? 0.95 : 0.82,
      fillColor: bucket.color,
      fillOpacity: props.ngii_bucket === "AUTO_APPLY_LIKE_READY" ? 0.05 : 0.18,
      radius: 5,
    };
  }
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
  if (props.ngii_category) return props.ngii_category;
  if (props.ngii_bucket) return "ngiiZones";
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
  const content =
    props.ngii_category === "ngiiMatchedLinks" || props.ngii_category === "ngiiReviewLinks"
      ? ngiiLinkPopupContent(props)
      : props.ngii_bucket
        ? ngiiPopupContent(props)
        : popupContent(props);
  state.kakao.infoWindow.setContent(`<div class="kakao-info">${content}</div>`);
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
  marker.title = facilityNameParts(props).primary || "Safety zone";
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

function removeKakaoOverlays(categories) {
  if (!state.kakao.enabled) return;
  categories.forEach((category) => {
    const overlays = state.kakao.overlays.get(category) || [];
    overlays.forEach((overlay) => overlay.setMap(null));
    state.kakao.overlays.delete(category);
  });
}

function addKakaoFeature(feature, rawProps = {}) {
  const props = enrichReviewProperties(rawProps);
  const category = kakaoCategoryForProps(props);
  const style = kakaoOverlayStyle(props, feature);

  if (feature.geometry?.type === "LineString" || feature.geometry?.type === "MultiLineString") {
    linePathsFromGeometry(feature.geometry).forEach((coordinates) => {
      const path = kakaoPathFromLineCoordinates(coordinates);
      if (path.length < 2) return;
      const overlay = new kakao.maps.Polyline({
        path,
        strokeWeight: style.weight,
        strokeColor: style.color,
        strokeOpacity: style.opacity,
        zIndex: props.ngii_category === "ngiiReviewLinks" ? 7 : 6,
      });
      const position = kakaoPointFromFeature(feature);
      kakao.maps.event.addListener(overlay, "click", () => openKakaoInfo(feature, props, position));
      registerKakaoOverlay(category, overlay);
    });
    return;
  }

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

function buildKakaoChangeOverlays() {
  if (!state.kakao.enabled || state.kakao.changeOverlaysBuilt) return;
  state.eventFeatures.forEach((feature) => addKakaoFeature(feature, feature.properties || {}));
  state.kakao.changeOverlaysBuilt = true;
}

function buildKakaoCurrentOverlays() {
  if (!state.kakao.enabled) return;
  removeKakaoOverlays(["currentChild", "currentSenior", "currentDisabled", "currentOther"]);
  state.currentFeatures.forEach((feature) => addKakaoFeature(feature, feature.properties || {}));
}

function buildKakaoNgiiOverlays() {
  if (!state.kakao.enabled) return;
  removeKakaoOverlays(["ngiiZones", "ngiiMatchedLinks", "ngiiReviewLinks"]);
  state.ngiiFeatures.forEach((feature) => addKakaoFeature(feature, feature.properties || {}));
  state.ngiiRepresentativeLinkFeatures.forEach((feature) =>
    addKakaoFeature(feature, {
      ngii_category: "ngiiMatchedLinks",
      ...(feature.properties || {}),
    }),
  );
  state.ngiiReviewLinkFeatures.forEach((feature) =>
    addKakaoFeature(feature, {
      ngii_category: "ngiiReviewLinks",
      ...(feature.properties || {}),
    }),
  );
}

function buildKakaoOverlays() {
  if (!state.kakao.enabled) return;
  buildKakaoChangeOverlays();
  buildKakaoCurrentOverlays();
  buildKakaoNgiiOverlays();
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
  const isKakaoMode = mode === "kakao" || mode === "satellite" || mode === "roadview";
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
    if (mode === "kakao" || mode === "satellite") {
      const view = kakaoViewBeforeSwitch || osmViewBeforeSwitch;
      state.kakao.map.setCenter(new kakao.maps.LatLng(view.lat, view.lng));
      state.kakao.map.setLevel(view.level);
    }
    state.kakao.map.setMapTypeId(
      mode === "satellite" ? kakao.maps.MapTypeId.HYBRID : kakao.maps.MapTypeId.ROADMAP,
    );
    setRoadviewLayerVisible(mode === "roadview");
    buildKakaoOverlays();
    requestAnimationFrame(() => {
      state.kakao.map.relayout();
      if (mode === "kakao" || mode === "satellite") {
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

async function openRoadview() {
  const location = state.selectedLocation;
  collapsePanelForMapFocus();
  setRoadviewPanelVisible(true);

  try {
    await setMapMode("roadview");
    if (!location) {
      document.getElementById("roadview-title").textContent = t("roadview");
      showRoadviewStatus(
        state.language === "en"
          ? "Click the Kakao map to search nearby Roadview imagery."
          : "지도에서 위치를 클릭하면 주변 로드뷰를 찾습니다.",
      );
      return;
    }
    document.getElementById("roadview-title").textContent = location.title;
    const position = new kakao.maps.LatLng(location.lat, location.lng);
    moveRoadviewToPosition(
      position,
      state.language === "en" ? "Searching nearest Roadview imagery." : "가장 가까운 로드뷰를 찾는 중입니다.",
    );
  } catch (error) {
    showRoadviewStatus(
      state.language === "en"
        ? "Kakao JavaScript domain configuration is required."
        : "Kakao JavaScript 도메인 등록이 필요합니다.",
    );
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
  renderSelectionHistory(event);
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

  const key = item.id || currentItemKey(item);
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
  renderSelectionHistory(item);
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

async function focusCurrentSearchItem(item) {
  if (item.sido_code && item.sido_code !== state.selectedSido) {
    await loadCurrentRegion(item.sido_code);
  }
  focusCurrentItem(item);
}

function popupContent(props) {
  const enriched = enrichReviewProperties(props);
  const names = facilityNameParts(props);
  const title = escapeHtml(names.primary);
  const subtitle = names.secondary ? `<span class="name-original">${escapeHtml(names.secondary)}</span><br>` : "";
  const type = props.change_type ? `<b>${changeTypeLabel(props.change_type)}</b><br>` : "";
  const review = enriched.review_reason
    ? `${t("reviewLabel")}: ${escapeHtml(enriched.review_reason)}<br>`
    : "";
  const zoneType = zoneTypeInfo(props.facility_type_code);
  const apiDates =
    props.api_first_registered_on || props.api_last_modified_on
      ? `${t("apiFirst")}: ${formatApiDate(props.api_first_registered_on)}<br>
    ${t("apiLast")}: ${formatApiDate(props.api_last_modified_on)}<br>`
      : "";
  return `
    <strong>${title}</strong><br>
    ${subtitle}
    ${type}
    ${t("type")}: ${zoneType.label}<br>
    ${t("manageNo")}: ${props.source_manage_no || "-"}<br>
    ${t("sgg")}: ${props.sgg_code || "-"}<br>
    ${t("group")}: ${props.zone_group_id || "-"}<br>
    ${apiDates}
    ${review}
    ${popupTimelineContent(props)}
    ${props.detected_at ? `${t("detected")}: ${formatDate(props.detected_at)}<br>` : ""}
    ${props.updated_at ? `${t("updated")}: ${formatDate(props.updated_at)}<br>` : ""}
    <button class="popup-roadview-button" type="button">${t("kakaoRoadview")}</button>
  `;
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

function popupContent(props) {
  const enriched = enrichReviewProperties(props);
  const names = facilityNameParts(props);
  const title = escapeHtml(names.primary);
  const subtitle = names.secondary ? `<span class="name-original">${escapeHtml(names.secondary)}</span><br>` : "";
  const type = props.change_type ? `<b>${changeTypeLabel(props.change_type)}</b><br>` : "";
  const review = enriched.review_reason
    ? `${t("reviewLabel")}: ${escapeHtml(enriched.review_reason)}<br>`
    : "";
  const zoneType = zoneTypeInfo(props.facility_type_code);
  const apiDates =
    props.api_first_registered_on || props.api_last_modified_on
      ? `${t("apiFirst")}: ${formatApiDate(props.api_first_registered_on)}<br>
    ${t("apiLast")}: ${formatApiDate(props.api_last_modified_on)}<br>`
      : "";
  return `
    <strong>${title}</strong><br>
    ${subtitle}
    ${type}
    ${t("type")}: ${zoneType.label}<br>
    ${t("manageNo")}: ${props.source_manage_no || "-"}<br>
    ${t("sgg")}: ${props.sgg_code || "-"}<br>
    ${t("group")}: ${props.zone_group_id || "-"}<br>
    ${apiDates}
    ${review}
    ${popupTimelineContent(props)}
    ${props.detected_at ? `${t("detected")}: ${formatDate(props.detected_at)}<br>` : ""}
    ${props.updated_at ? `${t("updated")}: ${formatDate(props.updated_at)}<br>` : ""}
    <button class="popup-roadview-button" type="button">${t("kakaoRoadview")}</button>
  `;
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

async function ensureCurrentSearchIndex() {
  if (state.currentSearchItems.length) return;
  if (!state.currentSearchIndexLoading) {
    const regions = state.currentIndex?.regions || [];
    state.currentSearchIndexLoading = Promise.all(
      regions.map((region) => loadJson(`data/current_search/${region.sido_code}.json`)),
    ).then((payloads) => {
      state.currentSearchItems = payloads.flatMap((payload) => payload.items || []);
      return state.currentSearchItems;
    });
  }
  await state.currentSearchIndexLoading;
}

async function handleCurrentSearchInput() {
  const query = document.getElementById("current-search").value.trim();
  if (query) await ensureCurrentSearchIndex();
  renderCurrentItems();
}

function currentRegion(code) {
  return (state.currentIndex?.regions || []).find((region) => region.sido_code === code);
}

function selectedCurrentRegion() {
  return currentRegion(state.selectedSido);
}

function renderCurrentRegionSummary() {
  const target = document.getElementById("current-region-summary");
  if (!target) return;
  const region = selectedCurrentRegion();
  if (!region) {
    target.textContent = "No region selected.";
    return;
  }
  target.textContent = `${region.sido_name} · Polygon ${numberText(region.zone_count)} · Point ${numberText(
    region.point_count,
  )} · SGG ${numberText(region.sgg_count)}`;
}

function renderCurrentRegionSelect() {
  const select = document.getElementById("current-sido");
  if (!select || !state.currentIndex) return;
  const regions = state.currentIndex.regions || [];
  select.replaceChildren(
    ...regions.map((region) => {
      const option = document.createElement("option");
      option.value = region.sido_code;
      option.textContent = `${region.sido_name} (${numberText(region.zone_count)} / ${numberText(
        region.point_count,
      )})`;
      return option;
    }),
  );
  if (!currentRegion(state.selectedSido) && regions.length) {
    state.selectedSido = regions[0].sido_code;
  }
  select.value = state.selectedSido;
  renderCurrentRegionSummary();
}

function renderCurrentRegionSummary() {
  const target = document.getElementById("current-region-summary");
  if (!target) return;
  const region = selectedCurrentRegion();
  if (!region) {
    target.textContent = t("noRegion");
    return;
  }
  target.textContent = `${formatSidoName(region)} · Polygon ${numberText(region.zone_count)} · Point ${numberText(
    region.point_count,
  )} · ${t("sgg")} ${numberText(region.sgg_count)}`;
}

function renderCurrentRegionSelect() {
  const select = document.getElementById("current-sido");
  if (!select || !state.currentIndex) return;
  const regions = state.currentIndex.regions || [];
  select.replaceChildren(
    ...regions.map((region) => {
      const option = document.createElement("option");
      option.value = region.sido_code;
      option.textContent = `${formatSidoName(region)} (${numberText(region.zone_count)} / ${numberText(
        region.point_count,
      )})`;
      return option;
    }),
  );
  if (!currentRegion(state.selectedSido) && regions.length) {
    state.selectedSido = regions[0].sido_code;
  }
  select.value = state.selectedSido;
  renderCurrentRegionSummary();
}

function applyStaticLanguage() {
  document.documentElement.lang = state.language;
  document.title = t("appTitle");
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-change-label]").forEach((element) => {
    element.textContent = changeTypeLabel(element.dataset.changeLabel);
  });
  document.querySelectorAll("[data-language]").forEach((button) => {
    const active = button.dataset.language === state.language;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  setPanelCollapsed(document.body.classList.contains("panel-collapsed"));
  renderCurrentRegionSelect();
}

function rerenderDynamicLanguage() {
  renderEvents();
  renderCurrentItems();
  renderChangeSummaryBySido();
  if (window.dashboardOverview) renderOverview(window.dashboardOverview);
}

function setLanguage(language) {
  if (!I18N[language] || state.language === language) return;
  state.language = language;
  localStorage.setItem("dashboardLanguage", language);
  applyStaticLanguage();
  rerenderDynamicLanguage();
  removeKakaoOverlays(["new", "changed", "review"]);
  state.kakao.changeOverlaysBuilt = false;
  buildKakaoOverlays();
  setKakaoOverlayVisibility();
}

function clearCurrentLayers() {
  ["currentChild", "currentSenior", "currentDisabled", "currentOther"].forEach((key) => {
    layerGroups[key].clearLayers();
  });
  state.currentItems = [];
  state.currentLayers.clear();
  state.currentFeatures.clear();
  state.currentGroups = new Map();
  removeKakaoOverlays(["currentChild", "currentSenior", "currentDisabled", "currentOther"]);
}

function regionBoundsFromCurrentFeatures() {
  const bounds = L.latLngBounds([]);
  state.currentFeatures.forEach((feature) => {
    const featureBounds = boundsFromFeature(feature);
    if (featureBounds?.isValid()) bounds.extend(featureBounds);
  });
  return bounds.isValid() ? bounds : null;
}

async function loadCurrentRegion(sidoCode, { fit = false } = {}) {
  const region = currentRegion(sidoCode);
  if (!region) return;
  state.selectedSido = sidoCode;
  renderCurrentRegionSummary();
  const select = document.getElementById("current-sido");
  if (select) select.value = sidoCode;

  const loadingKey = `${sidoCode}:${Date.now()}`;
  state.currentRegionLoading = loadingKey;
  const [zones, points] = await Promise.all([
    loadJson(`data/${region.zones_file}`),
    loadJson(`data/${region.points_file}`),
  ]);
  if (state.currentRegionLoading !== loadingKey) return;

  clearCurrentLayers();
  state.currentItems = buildCurrentItems(zones, points);
  state.currentGroups = buildCurrentGroupIndex(zones, points);
  addCurrentZones(zones);
  addCurrentPoints(points);
  buildKakaoCurrentOverlays();
  setKakaoOverlayVisibility();
  renderCurrentItems();

  if (fit) {
    const bounds = regionBoundsFromCurrentFeatures();
    if (bounds) map.fitBounds(bounds.pad(0.25), { maxZoom: 14, animate: true });
  }
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

function renderOverview(overview) {
  window.dashboardOverview = overview;
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
    ? `${t("latestRun")} ${formatDate(latest.finished_at || latest.started_at)}`
    : t("noRuns");
  document.getElementById("run-total").textContent = countText(recentRuns.length);

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
          ${t("collected")} ${countText(run.fetched_count)} · ${t("polygonChanged")} ${numberText(
            polygonChanges,
          )} · ${t("pointChangedCount")} ${numberText(pointChanges)}<br>
          ${
            run.status !== "SUCCESS" && run.error_message
              ? `<span class="run-error">${t("failureReason")}: ${escapeHtml(
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

function renderChangeSummaryBySido() {
  const target = document.getElementById("change-region-summary");
  if (!target || !state.changeSummaryBySido) return;
  const regions = state.changeSummaryBySido.regions || [];
  if (!regions.length) {
    target.textContent = "No nationwide change events after baseline.";
    return;
  }
  target.replaceChildren(
    ...regions.map((region) => {
      const item = document.createElement("span");
      item.className = "region-chip";
      item.textContent = `${region.sido_name} ${numberText(region.total)} · N ${numberText(
        region.new,
      )} · C ${numberText(region.changed)} · R ${numberText(region.deleted_or_review)}`;
      return item;
    }),
  );
  for (const rule of exclusionRules) {
    const item = document.createElement("span");
    item.className = "region-chip exclusion-note";
    item.textContent = `${rule.label}: ${rule.reason}`;
    target.appendChild(item);
  }
}

function renderChangeSummaryBySido() {
  const target = document.getElementById("change-region-summary");
  if (!target || !state.changeSummaryBySido) return;
  const regions = state.changeSummaryBySido.regions || [];
  const exclusionRules = state.changeExclusions?.rules || [];
  if (!regions.length && !exclusionRules.length) {
    target.textContent = t("noChangesAfterBaseline");
    return;
  }
  target.replaceChildren(
    ...regions.map((region) => {
      const item = document.createElement("span");
      item.className = "region-chip";
      item.textContent = `${formatSidoName(region)} ${countText(region.total)} · ${t("new")} ${numberText(
        region.new,
      )} · ${t("changed")} ${numberText(region.changed)} · ${t("review")} ${numberText(
        region.deleted_or_review,
      )}`;
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
  const sourceItems = query ? state.currentSearchItems : state.currentItems;
  const filtered = sourceItems.filter((item) => {
    const haystack = [
      item.facility_name,
      item.source_manage_no,
      item.sgg_code,
      item.zone_group_id,
      item.sido_name,
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
        void focusCurrentSearchItem(item);
      });
      listItem.addEventListener("keydown", (keyboardEvent) => {
        if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
          keyboardEvent.preventDefault();
          void focusCurrentSearchItem(item);
        }
      });
      return listItem;
    }),
  );
}

function searchableText(item) {
  return [
    item.facility_name,
    facilityNameEn(item.facility_name),
    item.source_manage_no,
    item.sgg_code,
    item.zone_group_id,
    item.sido_name,
    formatSidoName(item.sido_code),
    item.run_id,
    item.layer_type,
    item.facility_type_code,
    zoneTypeInfo(item.facility_type_code).label,
  ]
    .join(" ")
    .toLowerCase();
}

function renderEvents() {
  const query = document.getElementById("event-search").value.trim().toLowerCase();
  const type = document.getElementById("event-type").value;
  const filtered = state.events.filter((event) => {
    const matchesType = !type || event.change_type === type;
    return matchesType && (!query || searchableText(event).includes(query));
  });

  document.getElementById("event-total").textContent = countText(filtered.length);
  const eventList = document.getElementById("event-list");
  eventList.replaceChildren(
    ...filtered.slice(0, 120).map((event) => {
      const enriched = enrichReviewProperties(event);
      const zoneType = zoneTypeInfo(event.facility_type_code);
      const names = facilityNameParts(event);
      const item = document.createElement("li");
      item.className = "event-item";
      item.tabIndex = 0;
      item.setAttribute("role", "button");
      item.setAttribute("aria-label", `${names.primary} ${t("moveToLocation")}`);
      item.innerHTML = `
        <div class="event-topline">
          <span class="event-title">${escapeHtml(names.primary)}</span>
          <span class="badge ${event.change_type}">${changeTypeLabel(event.change_type)}</span>
        </div>
        <div class="event-meta">
          ${names.secondary ? `<span class="name-original">${escapeHtml(names.secondary)}</span><br>` : ""}
          <span class="zone-type" style="--zone-type-color: ${zoneType.color}">${zoneType.label}</span><br>
          ${event.layer_type} · ${event.source_manage_no || "-"} · ${event.sgg_code || "-"}<br>
          ${
            enriched.review_reason
              ? `<span class="review-reason">${escapeHtml(enriched.review_reason)}</span><br>`
              : ""
          }
          ${
            event.api_last_modified_on
              ? `<span>${t("apiLast")} ${formatApiDate(event.api_last_modified_on)}</span><br>`
              : ""
          }
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
  const sourceItems = query ? state.currentSearchItems : state.currentItems;
  const filtered = sourceItems.filter(
    (item) => matchesZoneFilter(item, filterValue) && (!query || searchableText(item).includes(query)),
  );

  document.getElementById("current-total").textContent = countText(filtered.length);
  const currentList = document.getElementById("current-list");
  currentList.replaceChildren(
    ...filtered.slice(0, 200).map((item) => {
      const zoneType = zoneTypeInfo(item.facility_type_code);
      const names = facilityNameParts(item);
      const listItem = document.createElement("li");
      listItem.className = "current-item";
      listItem.tabIndex = 0;
      listItem.setAttribute("role", "button");
      listItem.setAttribute("aria-label", `${names.primary} ${t("moveToLocation")}`);
      listItem.innerHTML = `
        <div class="event-topline">
          <span class="event-title">${escapeHtml(names.primary)}</span>
          <span class="badge current-badge">${item.layer_type}</span>
        </div>
        <div class="event-meta">
          ${names.secondary ? `<span class="name-original">${escapeHtml(names.secondary)}</span><br>` : ""}
          <span class="zone-type" style="--zone-type-color: ${zoneType.color}">${zoneType.label}</span><br>
          ${item.layer_type} · ${item.source_manage_no || "-"} · ${item.sgg_code || "-"}<br>
          ${query && item.sido_name ? `${formatSidoName(item.sido_code || item.sido_name)}<br>` : ""}
          ${t("group")} ${item.zone_group_id || "-"}
          ${
            item.api_last_modified_on
              ? `<br><span>${t("apiLast")} ${formatApiDate(item.api_last_modified_on)}</span>`
              : ""
          }
        </div>
      `;
      listItem.addEventListener("click", () => {
        document.querySelectorAll(".current-item.selected").forEach((selectedItem) => {
          selectedItem.classList.remove("selected");
        });
        listItem.classList.add("selected");
        void focusCurrentSearchItem(item);
      });
      listItem.addEventListener("keydown", (keyboardEvent) => {
        if (keyboardEvent.key === "Enter" || keyboardEvent.key === " ") {
          keyboardEvent.preventDefault();
          void focusCurrentSearchItem(item);
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

function ngiiBucketInfo(bucket) {
  const labels = {
    AUTO_APPLY_LIKE_READY: "자동 후보 유사",
    A_NEAR_PARALLEL_ONLY_REVIEW: "근접 평행도로 확인",
    B_WEAK_OVERLAP_REVIEW: "약한 중첩 확인",
    NO_ACCEPTED_CANDIDATE_WITHIN_20M: "주변 도로 있으나 후보 탈락",
    NO_CANDIDATE_WITHIN_20M: "NGII도 주변 도로 없음",
  };
  const colors = {
    AUTO_APPLY_LIKE_READY: "#16a34a",
    A_NEAR_PARALLEL_ONLY_REVIEW: "#d97706",
    B_WEAK_OVERLAP_REVIEW: "#f59e0b",
    NO_ACCEPTED_CANDIDATE_WITHIN_20M: "#dc2626",
    NO_CANDIDATE_WITHIN_20M: "#475569",
  };
  return {
    label: labels[bucket] || bucket || "Unknown",
    color: colors[bucket] || "#64748b",
  };
}

function ngiiBucketPriority(bucket) {
  return {
    NO_CANDIDATE_WITHIN_20M: 1,
    NO_ACCEPTED_CANDIDATE_WITHIN_20M: 2,
    A_NEAR_PARALLEL_ONLY_REVIEW: 3,
    B_WEAK_OVERLAP_REVIEW: 4,
    AUTO_APPLY_LIKE_READY: 5,
  }[bucket] || 9;
}

function ngiiBucketReason(bucket) {
  return {
    NO_CANDIDATE_WITHIN_20M: "NGII 도로중심선으로도 20m 안 도로가 없어 원천 위치나 polygon 범위를 먼저 확인해야 합니다.",
    NO_ACCEPTED_CANDIDATE_WITHIN_20M: "주변 도로는 있지만 스침/미세 인접 등으로 후보 기준을 통과하지 못했습니다.",
    A_NEAR_PARALLEL_ONLY_REVIEW: "보호구역과 평행한 도로축이 있어 실제 적용 도로인지 확인이 필요합니다.",
    B_WEAK_OVERLAP_REVIEW: "겹치기는 하지만 길이나 비율이 약해서 경계 스침인지 확인이 필요합니다.",
    AUTO_APPLY_LIKE_READY: "geometry 기준으로는 자동 후보에 가깝지만 최종 확정은 표준링크 기준과 함께 봅니다.",
  }[bucket] || "NGII 매칭 상태를 확인합니다.";
}

function ngiiSearchText(item) {
  return [
    item.facility_name,
    facilityNameEn(item.facility_name),
    item.source_manage_no,
    item.sgg_code,
    item.zone_group_id,
    item.ngii_bucket,
  ]
    .join(" ")
    .toLowerCase();
}

function ngiiPopupContent(props) {
  const bucket = ngiiBucketInfo(props.ngii_bucket);
  const representativeLink = props.representative_link_id
    ? `
    <hr>
    <strong>대표 링크</strong><br>
    ID: ${props.representative_link_id}<br>
    이름: ${escapeHtml(props.representative_link_name || "-")}<br>
    역할: ${props.representative_link_role || "-"}<br>
    규칙: ${props.representative_rule_code || "-"}<br>
    거리: ${props.representative_distance_m ?? "-"}m<br>
    내부중첩: ${props.representative_inside_m ?? "-"}m / ${props.representative_inside_ratio ?? "-"}<br>
    버퍼중첩: ${props.representative_buffer_overlap_m ?? "-"}m / ${
      props.representative_buffer_overlap_ratio ?? "-"
    }<br>`
    : "<hr><strong>대표 링크 없음</strong><br>";
  return `
    <strong>${escapeHtml(props.facility_name || t("noName"))}</strong><br>
    <span style="color: ${bucket.color}; font-weight: 700">${bucket.label}</span><br>
    ${escapeHtml(ngiiBucketReason(props.ngii_bucket))}<br>
    ${t("manageNo")}: ${props.source_manage_no || "-"}<br>
    ${t("sgg")}: ${props.sgg_code || "-"}<br>
    NGII candidates: ${numberText(props.candidate_count)}<br>
    Auto-like: ${numberText(props.auto_apply_like_count)}<br>
    A: ${numberText(props.grade_a_count)} / B: ${numberText(props.grade_b_count)}<br>
    Nearby within 20m: ${numberText(props.nearby_count)}<br>
    Nearest: ${props.nearest_distance_m ?? "-"}m
    ${representativeLink}
  `;
}

function ngiiLinkPopupContent(props) {
  return `
    <strong>NGII ${escapeHtml(props.rule_code || "link")}</strong><br>
    Link: ${props.link_id || "-"}<br>
    Name: ${escapeHtml(props.name || props.rdnm || "-")}<br>
    Role: ${props.link_role || "-"}<br>
    Grade: ${props.candidate_grade || "-"}<br>
    Distance: ${props.distance_m ?? "-"}m<br>
    Inside: ${props.intersection_length_m ?? "-"}m / ${props.intersection_ratio ?? "-"}<br>
    Buffer overlap: ${props.proximity_overlap_length_m ?? "-"}m / ${props.proximity_overlap_ratio ?? "-"}
  `;
}

function renderNgiiSummary() {
  const target = document.getElementById("ngii-summary");
  if (!target || !state.ngiiSummary) return;
  const rates = state.ngiiSummary.zone_coverage_rates || {};
  const counts = state.ngiiSummary.zone_coverage_counts || {};
  target.replaceChildren(
    ...[
      `서울 ${numberText(state.ngiiSummary.zone_total)}건`,
      `1순위 ${numberText(counts.NO_CANDIDATE_WITHIN_20M || 0)}건`,
      `2순위 ${numberText(counts.NO_ACCEPTED_CANDIDATE_WITHIN_20M || 0)}건`,
      `자동 후보 유사 ${numberText(counts.AUTO_APPLY_LIKE_READY || 0)}건 (${rates.auto_apply_like_rate || 0}%)`,
    ].map((text) => {
      const chip = document.createElement("span");
      chip.className = "region-chip";
      chip.textContent = text;
      return chip;
    }),
  );
}

function renderNgiiItems() {
  const bucket = document.getElementById("ngii-bucket")?.value || "";
  const query = (document.getElementById("ngii-search")?.value || "").trim().toLowerCase();
  const filtered = state.ngiiItems.filter(
    (item) => (!bucket || item.ngii_bucket === bucket) && (!query || ngiiSearchText(item).includes(query)),
  ).sort((a, b) => {
    const priority = ngiiBucketPriority(a.ngii_bucket) - ngiiBucketPriority(b.ngii_bucket);
    if (priority !== 0) return priority;
    return Number(a.nearest_distance_m ?? 9999) - Number(b.nearest_distance_m ?? 9999);
  });
  document.getElementById("ngii-total").textContent = numberText(filtered.length);
  const list = document.getElementById("ngii-list");
  if (!list) return;
  list.replaceChildren(
    ...filtered.slice(0, 180).map((item) => {
      const bucketInfo = ngiiBucketInfo(item.ngii_bucket);
      const names = facilityNameParts(item);
      const listItem = document.createElement("li");
      listItem.className = "ngii-item";
      listItem.tabIndex = 0;
      listItem.setAttribute("role", "button");
      listItem.innerHTML = `
        <div class="event-topline">
          <span class="event-title">${escapeHtml(names.primary)}</span>
          <span class="badge ngii-badge" style="--ngii-bucket-color: ${bucketInfo.color}">${bucketInfo.label}</span>
        </div>
        <div class="event-meta">
          ${names.secondary ? `<span class="name-original">${escapeHtml(names.secondary)}</span><br>` : ""}
          <span class="review-reason">${escapeHtml(ngiiBucketReason(item.ngii_bucket))}</span><br>
          ${item.source_manage_no || "-"} · ${item.sgg_code || "-"}<br>
          후보 ${numberText(item.candidate_count)} · 20m 내 도로 ${numberText(item.nearby_count)} · 최근접 ${
            item.nearest_distance_m ?? "-"
          }m
          ${
            item.representative_link_id
              ? `<br><span class="ngii-link-line">대표 링크 ${escapeHtml(item.representative_link_id)} · ${
                  item.representative_rule_code || "-"
                } · ${item.representative_distance_m ?? "-"}m</span>`
              : `<br><span class="ngii-link-line">대표 링크 없음</span>`
          }
        </div>
      `;
      const focus = () => focusNgiiItem(item);
      listItem.addEventListener("click", focus);
      listItem.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          focus();
        }
      });
      return listItem;
    }),
  );
}

function focusNgiiItem(item) {
  ensureLayerVisible("ngiiZones");
  ensureLayerVisible("ngiiMatchedLinks");
  const key = item.zone_id || item.source_manage_no;
  const layer = state.ngiiLayers.get(key);
  const feature = state.ngiiFeatures.get(key);
  if (!layer || !feature) return;
  const bounds = boundsFromFeature(feature);
  const center = centerFromFeature(feature);
  setSelectedLocation(center, item);
  if (document.body.dataset.mapMode !== "osm" && focusKakaoFeature(feature, item, bounds)) {
    return;
  }
  if (bounds?.isValid()) {
    map.fitBounds(bounds.pad(0.35), { maxZoom: 17, animate: true });
  }
  layer.openPopup();
}

function addNgiiLayers(zoneGeojson, representativeLinkGeojson, reviewLinkGeojson) {
  layerGroups.ngiiZones.clearLayers();
  layerGroups.ngiiMatchedLinks.clearLayers();
  layerGroups.ngiiReviewLinks.clearLayers();
  state.ngiiItems = [];
  state.ngiiLayers.clear();
  state.ngiiFeatures.clear();
  state.ngiiRepresentativeLinkFeatures = representativeLinkGeojson.features || [];
  state.ngiiReviewLinkFeatures = reviewLinkGeojson.features || [];

  L.geoJSON(zoneGeojson, {
    style: (feature) => {
      const bucket = ngiiBucketInfo(feature.properties?.ngii_bucket);
      const isAuto = feature.properties?.ngii_bucket === "AUTO_APPLY_LIKE_READY";
      return {
        color: bucket.color,
        weight: isAuto ? 1.1 : 2.4,
        opacity: isAuto ? 0.45 : 0.95,
        fillColor: bucket.color,
        fillOpacity: isAuto ? 0.04 : 0.18,
      };
    },
    onEachFeature: (feature, itemLayer) => {
      const props = feature.properties || {};
      const key = props.zone_id || props.source_manage_no;
      state.ngiiItems.push(props);
      state.ngiiLayers.set(key, itemLayer);
      state.ngiiFeatures.set(key, feature);
      itemLayer.on("click", () => setSelectedLocation(centerFromFeature(feature), props));
      itemLayer.bindPopup(ngiiPopupContent(props));
    },
  }).addTo(layerGroups.ngiiZones);

  L.geoJSON(representativeLinkGeojson, {
    style: (feature) => {
      const role = feature.properties?.link_role;
      return {
        color: role === "MATCHED_CANDIDATE" ? "#2563eb" : "#64748b",
        weight: role === "MATCHED_CANDIDATE" ? 3.5 : 2.5,
        opacity: role === "MATCHED_CANDIDATE" ? 0.88 : 0.58,
        dashArray: role === "MATCHED_CANDIDATE" ? null : "6 5",
      };
    },
    onEachFeature: (feature, itemLayer) => {
      itemLayer.bindPopup(ngiiLinkPopupContent(feature.properties || {}));
    },
  }).addTo(layerGroups.ngiiMatchedLinks);

  L.geoJSON(reviewLinkGeojson, {
    style: (feature) => {
      const rule = feature.properties?.rule_code;
      const color = rule?.startsWith("A_") ? "#d97706" : rule?.startsWith("B_") ? "#f59e0b" : "#dc2626";
      return {
        color,
        weight: 4,
        opacity: 0.9,
      };
    },
    onEachFeature: (feature, itemLayer) => {
      itemLayer.bindPopup(ngiiLinkPopupContent(feature.properties || {}));
    },
  }).addTo(layerGroups.ngiiReviewLinks);

  renderNgiiSummary();
  renderNgiiItems();
  buildKakaoNgiiOverlays();
  setKakaoOverlayVisibility();
}

function bindLayerToggles() {
  document.querySelectorAll("[data-layer]").forEach((input) => {
    const applyLayerState = () => {
      const group = layerGroups[input.dataset.layer];
      if (input.checked) group.addTo(map);
      else group.removeFrom(map);
      setKakaoOverlayVisibility();
    };
    input.addEventListener("change", applyLayerState);
    applyLayerState();
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

function bindLanguageToggle() {
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => setLanguage(button.dataset.language));
  });
}

async function main() {
  applyStaticLanguage();
  bindLayerToggles();
  bindActivityTabs();
  bindMapTools();
  bindRoadviewDrag();
  bindRoadviewResize();
  bindLanguageToggle();
  document.getElementById("event-search").addEventListener("input", renderEvents);
  document.getElementById("event-type").addEventListener("change", renderEvents);
  document.getElementById("current-search").addEventListener("input", () => {
    void handleCurrentSearchInput();
  });
  document.getElementById("current-zone-type").addEventListener("change", renderCurrentItems);
  document.getElementById("ngii-bucket").addEventListener("change", renderNgiiItems);
  document.getElementById("ngii-search").addEventListener("input", renderNgiiItems);
  document.getElementById("current-sido").addEventListener("change", (event) => {
    void loadCurrentRegion(event.target.value, { fit: true });
  });

  const [
    overview,
    events,
    currentIndex,
    changeSummaryBySido,
    changeExclusions,
    changeZones,
    changePoints,
    timelines,
    ngiiSummary,
    ngiiZones,
    ngiiRepresentativeLinks,
    ngiiReviewLinks,
  ] = await Promise.all([
    loadJson("data/overview.json"),
    loadJson("data/change_events.json"),
    loadJson("data/current_index.json"),
    loadJson("data/change_summary_by_sido.json"),
    loadJson("data/change_exclusions.json"),
    loadJson("data/change_zones.geojson"),
    loadJson("data/change_points.geojson"),
    loadJson("data/timelines.json"),
    loadJson("data/ngii_seoul_match_summary.json"),
    loadJson("data/ngii_seoul_match_zones.geojson"),
    loadJson("data/ngii_seoul_representative_links.geojson"),
    loadJson("data/ngii_seoul_review_links.geojson"),
  ]);

  renderOverview(overview);
  state.events = events.events || [];
  state.currentIndex = currentIndex;
  state.changeSummaryBySido = changeSummaryBySido;
  state.changeExclusions = changeExclusions;
  state.ngiiSummary = ngiiSummary;
  renderCurrentRegionSelect();
  renderChangeSummaryBySido();
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
  addChangeLayer(changeZones);
  addChangeLayer(changePoints);
  addNgiiLayers(ngiiZones, ngiiRepresentativeLinks, ngiiReviewLinks);
  buildKakaoChangeOverlays();
  await loadCurrentRegion(state.selectedSido);
  renderEvents();

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
