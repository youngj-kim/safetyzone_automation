from pathlib import Path


def test_daily_workflow_keeps_kst_schedule_and_quality_gate() -> None:
    workflow = Path(".github/workflows/daily-monitor.yml").read_text(encoding="utf-8")

    assert 'cron: "0 0 * * *"' in workflow
    assert "runs-on: [self-hosted, windows, x64]" in workflow
    assert "shell: cmd" in workflow
    assert "python -m safety_zone_monitor run" in workflow
    assert "python -m safety_zone_monitor quality-report" in workflow
    assert "SGG_CODES_FILE: ${{ vars.SGG_CODES_FILE }}" in workflow
