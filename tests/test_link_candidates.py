from pathlib import Path


def test_link_candidate_migration_documents_expected_grades() -> None:
    migration = Path(
        "src/safety_zone_monitor/migrations/007_standard_link_match_candidates.sql"
    ).read_text(encoding="utf-8")

    assert "analysis.zone_link_match_candidate" in migration
    assert "candidate_grade IN ('A', 'B', 'C', 'D')" in migration
    assert "analysis.v_zone_link_match_candidate" in migration
    assert "mobility.std_link" in migration


def test_link_candidate_cli_is_registered() -> None:
    cli = Path("src/safety_zone_monitor/cli.py").read_text(encoding="utf-8")

    assert '"build-link-candidates"' in cli
    assert "build_link_match_candidates" in cli


def test_link_candidate_v2_migration_documents_review_objects() -> None:
    migration = Path(
        "src/safety_zone_monitor/migrations/008_standard_link_match_candidates_v2.sql"
    ).read_text(encoding="utf-8")

    assert "analysis.zone_link_match_candidate_v2" in migration
    assert "analysis.zone_link_match_excluded_v2" in migration
    assert "analysis.v_zone_link_match_coverage_v2" in migration


def test_link_candidate_v2_cli_is_registered() -> None:
    cli = Path("src/safety_zone_monitor/cli.py").read_text(encoding="utf-8")

    assert '"build-link-candidates-v2"' in cli
    assert "build_link_match_candidates_v2" in cli


def test_link_candidate_v2_builder_tracks_touch_or_graze_exclusions() -> None:
    db = Path("src/safety_zone_monitor/db.py").read_text(encoding="utf-8")

    assert "TOUCH_OR_GRAZE" in db
    assert "same_road_as_seed" in db
    assert "connected_to_seed" in db


def test_link_candidate_v21_builder_has_pattern_rules() -> None:
    db = Path("src/safety_zone_monitor/db.py").read_text(encoding="utf-8")

    assert "A_SHORT_INSIDE" in db
    assert "A_NEAR_PARALLEL_CORRIDOR" in db
    assert "A_JUNCTION_COMPONENT" in db
    assert "TINY_ADJACENCY" in db
    assert "B_POTENTIAL_GRADE_SEPARATED" in db


def test_link_candidate_v21_migration_adds_review_metrics() -> None:
    migration = Path(
        "src/safety_zone_monitor/migrations/009_standard_link_match_v21_metrics.sql"
    ).read_text(encoding="utf-8")

    assert "proximity_overlap_length_m" in migration
    assert "proximity_overlap_ratio" in migration
    assert "potential_grade_separated" in migration


def test_link_candidate_v22_migration_adds_structure_review_fields() -> None:
    migration = Path(
        "src/safety_zone_monitor/migrations/010_standard_link_structure_review_fields.sql"
    ).read_text(encoding="utf-8")

    assert "road_type_name" in migration
    assert "link_structure_category" in migration
    assert "structure_review_flag" in migration
    assert "UNDERPASS_REVIEW" in migration
    assert "ELEVATED_ROAD_REVIEW" in migration
    assert "RAMP_CONNECTOR_REVIEW" in migration
