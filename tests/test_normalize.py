from safety_zone_monitor.normalize import (
    canonical_polygon_wkt,
    normalize_item,
    normalize_polygon_geometry,
    normalize_records,
)


def sample_item(**updates: str) -> dict[str, str]:
    item = {
        "ptznMngNo": "  Z-001 ",
        "pjtNo": "P-1",
        "trgtFcltNm": "Test School",
        "fcltTypeCd": "1",
        "fcltDtlTypeCd": "11",
        "rprsPtznMngNo": "R-1",
        "useYn": "Y",
        "sggCd": "11110",
        "emdongCd": "11110101",
        "stdgCd": "1111010100",
        "assignType": "1",
        "roadNmAddr": "1 Test Road, Jongno-gu, Seoul",
        "roadNmDaddr": "",
        "lotnoAddr": "1 Test-dong, Jongno-gu, Seoul",
        "lotnoDaddr": "",
        "frstRegDt": "20250102",
        "lastMdfcnDt": "20250603",
        "fturGeomVl": "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))",
    }
    item.update(updates)
    return item


def test_normalize_is_stable_for_whitespace_and_ring_orientation() -> None:
    first = normalize_item(sample_item(trgtFcltNm="Test  School"))
    second = normalize_item(
        sample_item(
            trgtFcltNm="Test School",
            fturGeomVl="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        )
    )
    assert first is not None and second is not None
    assert first.zone_id == second.zone_id
    assert first.attr_hash == second.attr_hash
    assert first.geom_hash == second.geom_hash
    assert first.data_hash == second.data_hash
    assert first.first_registered_on.isoformat() == "2025-01-02"
    assert first.last_modified_on.isoformat() == "2025-06-03"


def test_zone_id_survives_district_code_change() -> None:
    first = normalize_item(sample_item(sggCd="11110"))
    moved = normalize_item(sample_item(sggCd="11140"))
    assert first is not None and moved is not None
    assert first.zone_id == moved.zone_id
    assert first.attr_hash != moved.attr_hash
    assert first.geom_hash == moved.geom_hash


def test_point_is_skipped() -> None:
    records, skipped, inactive = normalize_records([sample_item(fturGeomVl="POINT (1 2)")])
    assert records == []
    assert skipped == 1
    assert inactive == 0


def test_inactive_record_is_kept_out_of_analysis() -> None:
    records, skipped, inactive = normalize_records([sample_item(useYn="N")])
    assert records == []
    assert skipped == 0
    assert inactive == 1


def test_geometry_collection_keeps_only_polygon() -> None:
    wkt = canonical_polygon_wkt(
        "GEOMETRYCOLLECTION (POINT (1 2), POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0)))"
    )
    assert wkt is not None
    assert wkt.startswith("MULTIPOLYGON")


def test_overlapping_polygons_are_dissolved_without_area_loss() -> None:
    result = normalize_polygon_geometry(
        "GEOMETRYCOLLECTION ("
        "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0)), "
        "POLYGON ((5 0, 5 10, 15 10, 15 0, 5 0)), "
        "POINT (2 2))"
    )
    assert result is not None
    _, qc = result
    assert qc["source_polygon_count"] == 2
    assert qc["source_point_count"] == 1
    assert qc["normalized_polygon_count"] == 1
    assert qc["source_polygon_area_sum_m2"] == 200.0
    assert qc["source_union_area_m2"] == 150.0
    assert qc["source_overlap_area_m2"] == 50.0
    assert qc["repair_applied"] is True
