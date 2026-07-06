from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from shapely import from_wkt, make_valid, to_wkt
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry


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


def canonical_polygon_wkt(value: Any) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        geometry = from_wkt(text)
    except Exception as exc:
        raise ValueError("Invalid WKT geometry") from exc
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    polygons = _polygon_parts(geometry)
    if not polygons:
        return None
    normalized = MultiPolygon(polygons).normalize()
    return to_wkt(normalized, rounding_precision=-1, trim=True, output_dimension=2)


@dataclass(frozen=True)
class ZoneRecord:
    zone_id: str
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
            "attr_hash": self.attr_hash,
            "geom_hash": self.geom_hash,
            "data_hash": self.data_hash,
            **self.attributes(),
        }


def normalize_item(item: dict[str, Any]) -> ZoneRecord | None:
    geometry_wkt = canonical_polygon_wkt(item.get("fturGeomVl"))
    if geometry_wkt is None:
        return None

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

    if attributes["source_manage_no"]:
        identity = {
            "source": "police-safety-zone-v1",
            "source_manage_no": attributes["source_manage_no"],
        }
    else:
        identity = {
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

    hashable_attributes = dict(attributes)
    for field in ("first_registered_on", "last_modified_on"):
        if hashable_attributes[field]:
            hashable_attributes[field] = hashable_attributes[field].isoformat()
    zone_id = stable_hash(identity)
    attr_hash = stable_hash(hashable_attributes)
    geom_hash = stable_hash(geometry_wkt)
    data_hash = stable_hash({"attr_hash": attr_hash, "geom_hash": geom_hash})
    return ZoneRecord(
        zone_id=zone_id,
        attr_hash=attr_hash,
        geom_hash=geom_hash,
        data_hash=data_hash,
        geometry_wkt=geometry_wkt,
        **attributes,  # type: ignore[arg-type]
    )


def normalize_records(items: list[dict[str, Any]]) -> tuple[list[ZoneRecord], int, int]:
    records_by_id: dict[str, ZoneRecord] = {}
    skipped_non_polygon = 0
    skipped_inactive = 0
    for item in items:
        record = normalize_item(item)
        if record is None:
            skipped_non_polygon += 1
            continue
        if record.use_yn and record.use_yn.upper() not in {"Y", "1"}:
            skipped_inactive += 1
            continue
        previous = records_by_id.get(record.zone_id)
        if previous and previous.data_hash != record.data_hash:
            raise ValueError(f"Conflicting duplicate zone_id: {record.zone_id}")
        records_by_id[record.zone_id] = record
    return list(records_by_id.values()), skipped_non_polygon, skipped_inactive
