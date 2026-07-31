from pathlib import Path

from safety_zone_monitor.db import (
    OPERATIONAL_MIGRATION_NAMES,
    OPERATIONAL_TABLE_NAMES,
    change_summary_by_sido,
    classify_sgg_coverage,
    current_region_index,
    current_search_index_by_sido,
    dashboard_change_exclusion_policies,
    dashboard_changed_fields,
    dashboard_geometry_change_info,
    group_feature_collection_by_sido,
    sanitize_error_message,
)


def test_sanitize_error_message_redacts_sensitive_query_params() -> None:
    message = (
        "Failed url: /get?serviceKey=abc123&numOfRows=1000 "
        "callback?token=secret-value&sggCd=11110"
    )

    sanitized = sanitize_error_message(message)

    assert "abc123" not in sanitized
    assert "secret-value" not in sanitized
    assert "serviceKey=[REDACTED]" in sanitized
    assert "token=[REDACTED]" in sanitized


def test_operational_migration_subset_excludes_link_matching_objects() -> None:
    migration_dir = Path("src/safety_zone_monitor/migrations")
    combined = "\n".join(
        (migration_dir / name).read_text(encoding="utf-8")
        for name in OPERATIONAL_MIGRATION_NAMES
    )

    assert "zone_link_match" not in combined
    assert "mobility.std_link" not in combined
    assert "ngii_road_centerline" not in combined
    assert set(OPERATIONAL_MIGRATION_NAMES) == {
        "001_initial.sql",
        "002_inactive_metrics.sql",
        "003_make_transformed_geometry_valid.sql",
        "004_geometry_qc.sql",
        "005_facility_points_and_zone_groups.sql",
        "006_facility_point_change_events.sql",
        "012_facility_point_deleted_events.sql",
        "013_facility_point_absence_tracking.sql",
    }


def test_operational_copy_subset_excludes_local_matching_tables() -> None:
    combined = "\n".join(OPERATIONAL_TABLE_NAMES)

    assert "raw.raw_std_" not in combined
    assert "mobility." not in combined
    assert "ngii" not in combined
    assert "zone_link_match" not in combined
    assert set(OPERATIONAL_TABLE_NAMES) == {
        "ops.pipeline_run",
        "raw.police_zone_api_run",
        "raw.police_zone_item_snapshot",
        "analysis.zone_snapshot",
        "analysis.zone_current",
        "analysis.zone_change_event",
        "ops.notification_log",
        "analysis.zone_facility_point_snapshot",
        "analysis.zone_facility_point_current",
        "analysis.zone_facility_point_change_event",
        "analysis.zone_facility_point_absence",
    }


def test_sanitize_error_message_allows_empty_value() -> None:
    assert sanitize_error_message(None) is None


def test_classify_sgg_coverage_downgrades_expected_codes_without_raw_rows() -> None:
    coverage = classify_sgg_coverage(
        expected_sgg_codes=("11110", "28125", "41110", "41111"),
        current_sgg_codes=("11110", "41111"),
        raw_sgg_codes=("11110", "41111"),
    )

    assert coverage["critical"] == ()
    assert coverage["without_raw_rows"] == ("28125", "41110")


def test_classify_sgg_coverage_keeps_missing_raw_codes_critical() -> None:
    coverage = classify_sgg_coverage(
        expected_sgg_codes=("11110", "28125"),
        current_sgg_codes=("11110",),
        raw_sgg_codes=("11110", "28125"),
    )

    assert coverage["critical"] == ("28125",)
    assert coverage["without_raw_rows"] == ()


def test_current_dashboard_split_indexes_by_sido() -> None:
    zones = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "sgg_code": "11110",
                    "source_manage_no": "Z-1",
                    "zone_group_id": "G-1",
                    "facility_name": "A",
                    "facility_type_code": "1",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[[126.0, 37.0], [127.0, 37.0], [127.0, 38.0], [126.0, 37.0]]]],
                },
            }
        ],
    }
    points = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "sgg_code": "41110",
                    "facility_id": "P-1",
                    "point_ordinal": 2,
                    "source_manage_no": "P-Z-1",
                    "zone_group_id": "G-2",
                    "facility_name": "B",
                    "facility_type_code": "2",
                },
                "geometry": {"type": "Point", "coordinates": [127.1, 37.2]},
            }
        ],
    }

    zones_by_sido = group_feature_collection_by_sido(zones)
    points_by_sido = group_feature_collection_by_sido(points)
    region_index = current_region_index(zones_by_sido, points_by_sido)
    search_index = current_search_index_by_sido(zones_by_sido, points_by_sido)

    assert sorted(zones_by_sido) == ["11"]
    assert sorted(points_by_sido) == ["41"]
    assert region_index["totals"] == {"zones": 1, "points": 1, "sgg_codes": 2}
    assert {item["id"] for items in search_index.values() for item in items["items"]} == {
        "Polygon:Z-1",
        "Point:P-1-2",
    }


def test_change_summary_by_sido_groups_change_categories() -> None:
    summary = change_summary_by_sido(
        {
            "events": [
                {"sgg_code": "11110", "change_type": "NEW"},
                {"sgg_code": "11140", "change_type": "ATTRIBUTE_CHANGED"},
                {"sgg_code": "41110", "change_type": "MISSING"},
            ]
        }
    )

    assert summary["totals"] == {"total": 3, "new": 1, "changed": 1, "deleted_or_review": 1}
    assert [(region["sido_code"], region["total"]) for region in summary["regions"]] == [
        ("11", 2),
        ("41", 1),
    ]


def test_dashboard_changed_fields_lists_only_changed_attributes() -> None:
    changes = dashboard_changed_fields(
        {
            "facility_name": "Old School",
            "project_no": "P-1",
            "last_modified_on": None,
        },
        {
            "facility_name": "Old School",
            "project_no": "P-2",
            "last_modified_on": "2026-07-28",
        },
    )

    assert changes == [
        {"field": "project_no", "label": "사업번호", "old": "P-1", "new": "P-2"},
        {"field": "last_modified_on", "label": "최종수정일", "old": None, "new": "2026-07-28"},
    ]


def test_dashboard_geometry_change_info_classifies_area_direction() -> None:
    expanded = dashboard_geometry_change_info(
        "GEOMETRY_CHANGED",
        old_area_m2=100.0,
        new_area_m2=125.0,
        intersection_area_m2=95.0,
    )
    reshaped = dashboard_geometry_change_info(
        "GEOMETRY_ATTRIBUTE_CHANGED",
        old_area_m2=100.0,
        new_area_m2=100.4,
        intersection_area_m2=80.0,
    )

    assert expanded == {
        "direction": "EXPANDED",
        "old_area_m2": 100.0,
        "new_area_m2": 125.0,
        "area_delta_m2": 25.0,
        "area_delta_ratio": 0.25,
        "intersection_area_m2": 95.0,
        "overlap_ratio": 0.76,
    }
    assert reshaped["direction"] == "RESHAPED"
    assert dashboard_geometry_change_info("NEW", None, 100.0, None) is None


def test_dashboard_change_exclusion_policies_document_incheon_reorg() -> None:
    policies = dashboard_change_exclusion_policies()

    assert policies["rules"][0]["rule_id"] == "incheon-admin-reorg-20260701"
    assert policies["rules"][0]["detected_date"] == "2026-07-28"
    assert policies["rules"][0]["change_type"] == "NEW"
    assert policies["rules"][0]["sgg_codes"] == ["28125", "28155", "28275", "28290"]
    assert "행정구역 개편" in policies["rules"][0]["reason"]
