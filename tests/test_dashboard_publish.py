import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "push_dashboard.py"


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


@pytest.mark.parametrize("overlap", [False, True])
def test_publish_after_remote_advances(tmp_path: Path, overlap: bool) -> None:
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    writer = tmp_path / "writer"
    git(tmp_path, "clone", str(remote), str(writer))
    git(writer, "checkout", "-b", "main")
    git(writer, "config", "user.name", "Test")
    git(writer, "config", "user.email", "test@example.com")
    (writer / "overview.json").write_text("base\n", encoding="utf-8")
    git(writer, "add", ".")
    git(writer, "commit", "-m", "Initial")
    git(writer, "push", "-u", "origin", "main")
    runner = tmp_path / "runner"
    git(tmp_path, "clone", "--branch", "main", str(remote), str(runner))
    git(runner, "config", "user.name", "Test")
    git(runner, "config", "user.email", "test@example.com")
    (runner / "overview.json").write_text("generated\n", encoding="utf-8")
    git(runner, "add", ".")
    git(runner, "commit", "-m", "Dashboard")
    filename = "overview.json" if overlap else "README.md"
    (writer / filename).write_text("remote change\n", encoding="utf-8")
    git(writer, "add", ".")
    git(writer, "commit", "-m", "Concurrent edit")
    git(writer, "push")
    remote_head = git(writer, "rev-parse", "HEAD")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=runner,
        env={**os.environ, "GITHUB_REF_NAME": "main"},
        capture_output=True,
        text=True,
    )
    if overlap:
        assert result.returncode != 0
        assert git(remote, "rev-parse", "main") == remote_head
    else:
        assert result.returncode == 0, result.stderr
        assert git(remote, "show", "main:overview.json") == "generated"
        assert git(remote, "show", "main:README.md") == "remote change"


def test_successful_monitor_refreshes_and_triggers_pages() -> None:
    root = SCRIPT.parents[1]
    daily = (root / ".github/workflows/daily-monitor.yml").read_text(encoding="utf-8")
    pages = (root / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "fetch-depth: 0" in daily
    assert daily.count("python scripts/push_dashboard.py") == 2
    assert "full_dashboard_export=false" not in daily
    assert "workflow_run:" in pages
    assert 'workflows: ["Daily safety-zone monitor"]' in pages
    assert "types: [completed]" in pages
    assert "github.event_name == 'workflow_run' && 'main' || github.ref" in pages
