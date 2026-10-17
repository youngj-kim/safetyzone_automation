"""Publish a generated-data commit without overwriting concurrent remote changes."""

import os
import subprocess
import time


def publish(branch: str, attempts: int = 3) -> None:
    for attempt in range(attempts):
        subprocess.run(["git", "fetch", "origin", branch], check=True)
        # Refuse overlapping edits instead of silently replacing remote data.
        subprocess.run(["git", "rebase", "FETCH_HEAD"], check=True)
        result = subprocess.run(["git", "push", "origin", f"HEAD:refs/heads/{branch}"])
        if result.returncode == 0:
            return
        if attempt + 1 < attempts:
            time.sleep(2)
    raise RuntimeError(f"Dashboard push failed after {attempts} attempts")


if __name__ == "__main__":
    publish(os.environ.get("GITHUB_REF_NAME", "main"))
