from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
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
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unsupported date value: {text}")


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
    zone_key: str
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
    geometry_wkt: str

    def snapshot(self) -> dict[str, Any]:
        result = asdict(self)
        result["first_registered_on"] = (
            self.first_registered_on.isoformat() if self.first_registered_on else None
        )
        return result


def _sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_item(item: dict[str, Any]) -> ZoneRecord | None:
    geometry_wkt = canonical_polygon_wkt(item.get("fturGeomVl"))
    if geometry_wkt is None:
        return None

    fields = {
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
        "geometry_wkt": geometry_wkt,
    }
    if not fields["sgg_code"]:
        raise ValueError("Record is missing required sggCd")

    if fields["source_manage_no"]:
        identity = {
            "source": "police-safety-zone-v1",
            "source_manage_no": fields["source_manage_no"],
        }
    else:
        identity = {
            "source": "police-safety-zone-v1-fallback",
            "sgg_code": fields["sgg_code"],
            "representative_manage_no": fields["representative_manage_no"],
            "facility_name": fields["facility_name"],
            "facility_type_code": fields["facility_type_code"],
            "road_address": fields["road_address"],
            "lot_address": fields["lot_address"],
            "first_registered_on": (
                fields["first_registered_on"].isoformat() if fields["first_registered_on"] else None
            ),
        }
    zone_key = _sha256(identity)
    hash_payload = dict(fields)
    if hash_payload["first_registered_on"]:
        hash_payload["first_registered_on"] = hash_payload["first_registered_on"].isoformat()
    data_hash = _sha256(hash_payload)
    return ZoneRecord(zone_key=zone_key, data_hash=data_hash, **fields)  # type: ignore[arg-type]


def normalize_records(items: list[dict[str, Any]]) -> tuple[list[ZoneRecord], int]:
    records_by_key: dict[str, ZoneRecord] = {}
    skipped_non_polygon = 0
    for item in items:
        record = normalize_item(item)
        if record is None:
            skipped_non_polygon += 1
            continue
        previous = records_by_key.get(record.zone_key)
        if previous and previous.data_hash != record.data_hash:
            raise ValueError(f"Conflicting duplicate zone_key: {record.zone_key}")
        records_by_key[record.zone_key] = record
    return list(records_by_key.values()), skipped_non_polygon
