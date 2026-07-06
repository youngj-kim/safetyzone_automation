from __future__ import annotations

from dataclasses import dataclass

import requests

from safety_zone_monitor.db import RunSummary
from safety_zone_monitor.diff import ChangeType


def format_summary(summary: RunSummary) -> str:
    diff = summary.diff
    lines = [
        "[보호구역 변경 감지]",
        f"실행 ID: {summary.run_id}",
        (
            f"신규 {diff.count(ChangeType.NEW)} / "
            f"도형변경 {diff.count(ChangeType.GEOMETRY_CHANGED)} / "
            f"속성변경 {diff.count(ChangeType.ATTRIBUTE_CHANGED)} / "
            f"도형+속성변경 {diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED)} / "
            f"삭제 {diff.count(ChangeType.DELETED)} / "
            f"동일 {diff.count(ChangeType.UNCHANGED)}"
        ),
    ]
    for change in diff.changes[:10]:
        snapshot = change.new_snapshot or change.old_snapshot or {}
        name = snapshot.get("facility_name") or "이름 없음"
        sgg = snapshot.get("sgg_code") or "-"
        lines.append(f"- {change.change_type.value}: {name} ({sgg})")
    if len(diff.changes) > 10:
        lines.append(f"... 외 {len(diff.changes) - 10}건")
    return "\n".join(lines)


@dataclass(frozen=True)
class Notifier:
    slack_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    timeout_seconds: float = 15.0

    @property
    def channels(self) -> tuple[str, ...]:
        result = []
        if self.slack_webhook_url:
            result.append("slack")
        if self.telegram_bot_token and self.telegram_chat_id:
            result.append("telegram")
        return tuple(result)

    @property
    def configured(self) -> bool:
        return bool(self.channels)

    def send(self, summary: RunSummary) -> tuple[str, ...]:
        if not summary.diff.has_changes:
            return ()
        message = format_summary(summary)
        sent: list[str] = []
        if self.slack_webhook_url:
            response = requests.post(
                self.slack_webhook_url,
                json={"text": message},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            sent.append("slack")
        if self.telegram_bot_token and self.telegram_chat_id:
            response = requests.post(
                f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage",
                json={"chat_id": self.telegram_chat_id, "text": message},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            sent.append("telegram")
        return tuple(sent)
