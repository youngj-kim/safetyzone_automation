from pathlib import Path


def test_daily_workflow_uses_dispatch_and_quality_gate() -> None:
    workflow = Path(".github/workflows/daily-monitor.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert 'cron: "0 0 * * *"' in workflow
    assert "runs-on: [self-hosted, windows, x64]" in workflow
    assert "shell: cmd" in workflow
    assert "contents: write" in workflow
    assert "python -m safety_zone_monitor run --summary-json run_summary.json" in workflow
    assert "python -m safety_zone_monitor quality-report" in workflow
    assert "steps.detected_changes.outputs.has_changes == 'true'" in workflow
    assert "python -m safety_zone_monitor export-dashboard" in workflow
    assert "git add dashboard\\data" in workflow
    assert "actions/setup-python" not in workflow
    assert "python --version" in workflow
    assert "sgg_codes_file:" in workflow
    assert "SGG_CODES_FILE: ${{ inputs.sgg_codes_file || vars.SGG_CODES_FILE }}" in workflow
