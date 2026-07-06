from safety_zone_monitor.normalize import canonical_polygon_wkt, normalize_item, normalize_records


def sample_item(**updates: str) -> dict[str, str]:
    item = {
        "ptznMngNo": "  Z-001 ",
        "pjtNo": "P-1",
        "trgtFcltNm": "테스트  학교",
        "fcltTypeCd": "1",
        "fcltDtlTypeCd": "11",
        "rprsPtznMngNo": "R-1",
        "useYn": "Y",
        "sggCd": "11110",
        "emdongCd": "11110101",
        "stdgCd": "1111010100",
        "assignType": "1",
        "roadNmAddr": "서울 종로구 테스트로 1",
        "roadNmDaddr": "",
        "lotnoAddr": "서울 종로구 테스트동 1",
        "lotnoDaddr": "",
        "frstRegDt": "20250102",
        "fturGeomVl": "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))",
    }
    item.update(updates)
    return item


def test_normalize_is_stable_for_whitespace_and_ring_orientation() -> None:
    first = normalize_item(sample_item())
    second = normalize_item(
        sample_item(
            trgtFcltNm="테스트 학교",
            fturGeomVl="POLYGON ((0 0, 10 0, 10 10, 0 10, 0 0))",
        )
    )
    assert first is not None and second is not None
    assert first.zone_key == second.zone_key
    assert first.data_hash == second.data_hash
    assert first.facility_name == "테스트 학교"
    assert first.first_registered_on.isoformat() == "2025-01-02"


def test_zone_key_survives_district_code_change() -> None:
    first = normalize_item(sample_item(sggCd="11110"))
    moved = normalize_item(sample_item(sggCd="11140"))
    assert first is not None and moved is not None
    assert first.zone_key == moved.zone_key
    assert first.data_hash != moved.data_hash


def test_point_is_skipped() -> None:
    records, skipped = normalize_records([sample_item(fturGeomVl="POINT (1 2)")])
    assert records == []
    assert skipped == 1


def test_geometry_collection_keeps_only_polygon() -> None:
    wkt = canonical_polygon_wkt(
        "GEOMETRYCOLLECTION (POINT (1 2), POLYGON ((0 0, 0 1, 1 1, 1 0, 0 0)))"
    )
    assert wkt is not None
    assert wkt.startswith("MULTIPOLYGON")
