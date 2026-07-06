from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shapely import from_wkt, make_valid, to_wkt
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFC", str(value)).strip()
    text = re.sub(r"\s+", " ", text)
    return text or None


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{8,14}", text):
        text = text[:8]
    elif re.match(r"^\d{4}-\d{2}-\d{2}[ T]", text):
        text = text[:10]
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unsupported date value: {text}")


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _polygon_parts(geometry: BaseGeometry) -> list[Polygon]:
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, MultiPolygon):
        return list(geometry.geoms)
    if hasattr(geometry, "geoms"):
        parts: list[Polygon] = []
        for child in geometry.geoms:
            parts.extend(_polygon_parts(child))
        return parts
    return []


def _point_count(geometry: BaseGeometry) -> int:
    if geometry.geom_type == "Point":
        return 1
    if geometry.geom_type == "MultiPoint":
        return len(geometry.geoms)
    if hasattr(geometry, "geoms"):
        return sum(_point_count(child) for child in geometry.geoms)
    return 0


def _point_parts(geometry: BaseGeometry) -> list[Point]:
    if isinstance(geometry, Point):
        return [geometry]
    if hasattr(geometry, "geoms"):
        parts: list[Point] = []
        for child in geometry.geoms:
            parts.extend(_point_parts(child))
        return parts
    return []


def normalize_point_geometries(value: Any) -> list[str]:
    """Return stable, individually addressable Point WKTs from the source geometry."""
    text = clean_text(value)
    if not text:
        return []
    try:
        geometry = from_wkt(text)
    except Exception as exc:
        raise ValueError("Invalid WKT geometry") from exc
    point_wkts = [
        to_wkt(point.normalize(), rounding_precision=-1, trim=True, output_dimension=2)
        for point in _point_parts(geometry)
        if not point.is_empty
    ]
    return sorted(point_wkts)


def normalize_polygon_geometry(value: Any) -> tuple[str, dict[str, Any]] | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        geometry = from_wkt(text)
    except Exception as exc:
        raise ValueError("Invalid WKT geometry") from exc
    source_polygons = _polygon_parts(geometry)
    if not source_polygons:
        return None

    cleaned_polygons: list[Polygon] = []
    had_invalid_component = False
    for polygon in source_polygons:
        candidate: BaseGeometry = polygon
        if not candidate.is_valid:
            had_invalid_component = True
            candidate = make_valid(candidate)
        cleaned_polygons.extend(_polygon_parts(candidate))
    if not cleaned_polygons:
        return None

    source_area_sum = sum(polygon.area for polygon in cleaned_polygons)
    dissolved = unary_union(cleaned_polygons)
    if not dissolved.is_valid:
        dissolved = make_valid(dissolved)
    dissolved_polygons = _polygon_parts(dissolved)
    if not dissolved_polygons:
        return None
    normalized = MultiPolygon(dissolved_polygons).normalize()
    if normalized.is_empty or not normalized.is_valid:
        raise ValueError("Polygon normalization did not produce a valid geometry")

    union_area = normalized.area
    overlap_area = max(source_area_sum - union_area, 0.0)
    qc = {
        "normalization_version": "polygon-union-v1",
        "source_geometry_type": geometry.geom_type,
        "source_geometry_valid": geometry.is_valid,
        "source_polygon_count": len(source_polygons),
        "source_point_count": _point_count(geometry),
        "normalized_polygon_count": len(dissolved_polygons),
        "source_polygon_area_sum_m2": round(source_area_sum, 3),
        "source_union_area_m2": round(union_area, 3),
        "source_overlap_area_m2": round(overlap_area, 3),
        "source_overlap_ratio": round(overlap_area / source_area_sum, 6)
        if source_area_sum
        else 0.0,
        "repair_applied": had_invalid_component or overlap_area > 0.001,
        "non_polygon_component_discarded": _point_count(geometry) > 0,
        "qc_status": "PASS",
    }
    wkt = to_wkt(normalized, rounding_precision=-1, trim=True, output_dimension=2)
    return wkt, qc


def canonical_polygon_wkt(value: Any) -> str | None:
    result = normalize_polygon_geometry(value)
    return result[0] if result else None


@dataclass(frozen=True)
class ZoneRecord:
    zone_id: str
    zone_group_id: str
    attr_hash: str
    geom_hash: str
    data_hash: str
    source_manage_no: str | None
    project_no: str | None
    facility_name: str | None
    facility_type_code: str | None
    facility_detail_type_code: str | None
    representative_manage_no: str | None
    use_yn: str | None
    sgg_code: str
    emdong_code: str | None
    stdg_code: str | None
    assign_type: str | None
    road_address: str | None
    road_detail_address: str | None
    lot_address: str | None
    lot_detail_address: str | None
    first_registered_on: date | None
    last_modified_on: date | None
    geometry_wkt: str
    geometry_qc: dict[str, Any]

    def attributes(self) -> dict[str, Any]:
        return {
            "source_manage_no": self.source_manage_no,
            "project_no": self.project_no,
            "facility_name": self.facility_name,
            "facility_type_code": self.facility_type_code,
            "facility_detail_type_code": self.facility_detail_type_code,
            "representative_manage_no": self.representative_manage_no,
            "use_yn": self.use_yn,
            "sgg_code": self.sgg_code,
            "emdong_code": self.emdong_code,
            "stdg_code": self.stdg_code,
            "assign_type": self.assign_type,
            "road_address": self.road_address,
            "road_detail_address": self.road_detail_address,
            "lot_address": self.lot_address,
            "lot_detail_address": self.lot_detail_address,
            "first_registered_on": (
                self.first_registered_on.isoformat() if self.first_registered_on else None
            ),
            "last_modified_on": (
                self.last_modified_on.isoformat() if self.last_modified_on else None
            ),
        }

    def snapshot(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "zone_group_id": self.zone_group_id,
            "attr_hash": self.attr_hash,
            "geom_hash": self.geom_hash,
            "data_hash": self.data_hash,
            **self.attributes(),
        }


@dataclass(frozen=True)
class FacilityPointRecord:
    facility_id: str
    point_ordinal: int
    zone_group_id: str
    attr_hash: str
    point_hash: str
    data_hash: str
    source_manage_no: str | None
    facility_name: str | None
    sgg_code: str
    use_yn: str | None
    geometry_wkt: str
    attrs: dict[str, Any]


@dataclass(frozen=True)
class NormalizationResult:
    zones: list[ZoneRecord]
    facility_points: list[FacilityPointRecord]
    skipped_non_polygon_count: int
    skipped_inactive_count: int
    point_only_record_count: int


def normalize_attributes(item: dict[str, Any]) -> dict[str, Any]:
    attributes = {
        "source_manage_no": clean_text(item.get("ptznMngNo")),
        "project_no": clean_text(item.get("pjtNo")),
        "facility_name": clean_text(item.get("trgtFcltNm")),
        "facility_type_code": clean_text(item.get("fcltTypeCd")),
        "facility_detail_type_code": clean_text(item.get("fcltDtlTypeCd")),
        "representative_manage_no": clean_text(item.get("rprsPtznMngNo")),
        "use_yn": clean_text(item.get("useYn")),
        "sgg_code": clean_text(item.get("sggCd")),
        "emdong_code": clean_text(item.get("emdongCd")),
        "stdg_code": clean_text(item.get("stdgCd")),
        "assign_type": clean_text(item.get("assignType")),
        "road_address": clean_text(item.get("roadNmAddr")),
        "road_detail_address": clean_text(item.get("roadNmDaddr")),
        "lot_address": clean_text(item.get("lotnoAddr")),
        "lot_detail_address": clean_text(item.get("lotnoDaddr")),
        "first_registered_on": parse_date(item.get("frstRegDt")),
        "last_modified_on": parse_date(item.get("lastMdfcnDt")),
    }
    if not attributes["sgg_code"]:
        raise ValueError("Record is missing required sggCd")
    return attributes


def _identity(attributes: dict[str, Any]) -> dict[str, Any]:
    if attributes["source_manage_no"]:
        return {
            "source": "police-safety-zone-v1",
            "source_manage_no": attributes["source_manage_no"],
        }
    return {
        "source": "police-safety-zone-v1-fallback",
        "sgg_code": attributes["sgg_code"],
        "representative_manage_no": attributes["representative_manage_no"],
        "facility_name": attributes["facility_name"],
        "facility_type_code": attributes["facility_type_code"],
        "road_address": attributes["road_address"],
        "lot_address": attributes["lot_address"],
        "first_registered_on": (
            attributes["first_registered_on"].isoformat()
            if attributes["first_registered_on"]
            else None
        ),
    }


def _hashable_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    result = dict(attributes)
    for field in ("first_registered_on", "last_modified_on"):
        if result[field]:
            result[field] = result[field].isoformat()
    return result


def _group_id(attributes: dict[str, Any], facility_id: str) -> str:
    return (
        attributes["representative_manage_no"]
        or attributes["source_manage_no"]
        or facility_id
    )


def normalize_item(item: dict[str, Any]) -> ZoneRecord | None:
    geometry_result = normalize_polygon_geometry(item.get("fturGeomVl"))
    if geometry_result is None:
        return None
    geometry_wkt, geometry_qc = geometry_result

    attributes = normalize_attributes(item)
    hashable_attributes = _hashable_attributes(attributes)
    zone_id = stable_hash(_identity(attributes))
    zone_group_id = _group_id(attributes, zone_id)
    attr_hash = stable_hash(hashable_attributes)
    geom_hash = stable_hash(geometry_wkt)
    data_hash = stable_hash({"attr_hash": attr_hash, "geom_hash": geom_hash})
    return ZoneRecord(
        zone_id=zone_id,
        zone_group_id=zone_group_id,
        attr_hash=attr_hash,
        geom_hash=geom_hash,
        data_hash=data_hash,
        geometry_wkt=geometry_wkt,
        geometry_qc=geometry_qc,
        **attributes,  # type: ignore[arg-type]
    )


def normalize_facility_points(item: dict[str, Any]) -> list[FacilityPointRecord]:
    attributes = normalize_attributes(item)
    hashable_attributes = _hashable_attributes(attributes)
    attr_hash = stable_hash(hashable_attributes)
    facility_id = stable_hash(_identity(attributes))
    zone_group_id = _group_id(attributes, facility_id)
    result = []
    for point_ordinal, geometry_wkt in enumerate(
        normalize_point_geometries(item.get("fturGeomVl")), start=1
    ):
        point_hash = stable_hash(geometry_wkt)
        result.append(
            FacilityPointRecord(
                facility_id=facility_id,
                point_ordinal=point_ordinal,
                zone_group_id=zone_group_id,
                attr_hash=attr_hash,
                point_hash=point_hash,
                data_hash=stable_hash(
                    {
                        "attr_hash": attr_hash,
                        "point_hash": point_hash,
                    }
                ),
                source_manage_no=attributes["source_manage_no"],
                facility_name=attributes["facility_name"],
                sgg_code=attributes["sgg_code"],
                use_yn=attributes["use_yn"],
                geometry_wkt=geometry_wkt,
                attrs=hashable_attributes,
            )
        )
    return result


def normalize_records(items: list[dict[str, Any]]) -> NormalizationResult:
    records_by_id: dict[str, ZoneRecord] = {}
    points_by_id: dict[tuple[str, int], FacilityPointRecord] = {}
    skipped_non_polygon = 0
    skipped_inactive = 0
    point_only_records = 0
    for item in items:
        record = normalize_item(item)
        points = normalize_facility_points(item)
        use_yn = record.use_yn if record else (points[0].use_yn if points else None)
        if use_yn and use_yn.upper() not in {"Y", "1"}:
            skipped_inactive += 1
            continue
        if record is None:
            if points:
                point_only_records += 1
            else:
                skipped_non_polygon += 1
        else:
            previous = records_by_id.get(record.zone_id)
            if previous and previous.data_hash != record.data_hash:
                raise ValueError(f"Conflicting duplicate zone_id: {record.zone_id}")
            records_by_id[record.zone_id] = record
        for point in points:
            key = (point.facility_id, point.point_ordinal)
            previous_point = points_by_id.get(key)
            if previous_point and previous_point.data_hash != point.data_hash:
                raise ValueError(f"Conflicting duplicate facility point: {key}")
            points_by_id[key] = point
    return NormalizationResult(
        zones=list(records_by_id.values()),
        facility_points=list(points_by_id.values()),
        skipped_non_polygon_count=skipped_non_polygon,
        skipped_inactive_count=skipped_inactive,
        point_only_record_count=point_only_records,
    )
