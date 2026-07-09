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
