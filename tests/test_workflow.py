from pathlib import Path


def test_daily_workflow_uses_dispatch_and_quality_gate() -> None:
    workflow = Path(".github/workflows/daily-monitor.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "schedule:" in workflow
    assert 'cron: "0 0 * * *"' in workflow
    assert 'cron: "20 0 * * *"' in workflow
    assert 'cron: "40 0 * * *"' in workflow
    assert 'cron: "0 1 * * *"' in workflow
    assert 'cron: "20 1 * * *"' in workflow
    assert 'cron: "40 1 * * *"' in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "runs-on: [self-hosted, windows, x64]" not in workflow
    assert "shell: cmd" not in workflow
    assert "contents: write" in workflow
    assert "SAFETYZONE_DB_MODE: cloud" in workflow
    assert "actions/setup-python@v5" in workflow
    assert 'python-version: "3.11"' in workflow
    assert "prepare_db:" in workflow
    assert "inputs.prepare_db == 'true'" in workflow
    assert "python -m safety_zone_monitor init-ops-db" in workflow
    assert "python -m safety_zone_monitor audit-ops-db" in workflow
    assert "python -m safety_zone_monitor audit-db" not in workflow
    assert (
        "python -m safety_zone_monitor run $baseline_arg --summary-json run_summary.json"
        in workflow
    )
    assert "python -m safety_zone_monitor quality-report" in workflow
    assert "steps.detected_changes.outputs.full_dashboard_export == 'true'" in workflow
    assert "Check detected changes" in workflow
    assert "run_summary.json" in workflow
    assert "baseline_load:" in workflow
    assert 'baseline_arg="--baseline"' in workflow
    assert "full_dashboard_export=true" in workflow
    assert "python -m safety_zone_monitor export-dashboard" in workflow
    assert "Update dashboard data after safety-zone changes" in workflow
    assert "Export monitoring history" in workflow
    assert "export-dashboard --output dashboard/data --overview-only" in workflow
    assert "dashboard/data/overview.json" in workflow
    assert "Update dashboard monitoring history" in workflow
    assert "git add dashboard/data" in workflow
    assert "sgg_codes_file:" in workflow
    assert "Resolve SGG codes file" in workflow
    assert "SGG_CODES_FILE_DEFAULT:" in workflow
    assert "config/sgg_chunks/nationwide_chunk_01.txt" in workflow
    assert "config/sgg_chunks/nationwide_chunk_06.txt" in workflow
    assert 'echo "SGG_CODES_FILE=$selected_file" >> "$GITHUB_ENV"' in workflow
