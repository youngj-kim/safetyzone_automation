from __future__ import annotations

from dataclasses import dataclass

import requests

from safety_zone_monitor.db import RunSummary
from safety_zone_monitor.diff import ChangeType, PointChangeType


def format_summary(summary: RunSummary) -> str:
    diff = summary.diff
    lines = [
        "[보호구역 변경 감지]",
        f"실행 ID: {summary.run_id}",
        "[Polygon]",
        (
            f"신규 {diff.count(ChangeType.NEW)} / "
            f"도형변경 {diff.count(ChangeType.GEOMETRY_CHANGED)} / "
            f"속성변경 {diff.count(ChangeType.ATTRIBUTE_CHANGED)} / "
            f"도형+속성변경 {diff.count(ChangeType.GEOMETRY_ATTRIBUTE_CHANGED)} / "
            f"삭제 {diff.count(ChangeType.DELETED)} / "
            f"동일 {diff.count(ChangeType.UNCHANGED)}"
        ),
        "[시설 Point]",
        (
            f"신규 {summary.point_diff.count(PointChangeType.NEW)} / "
            f"위치변경 {summary.point_diff.count(PointChangeType.POINT_CHANGED)} / "
            f"속성변경 {summary.point_diff.count(PointChangeType.ATTRIBUTE_CHANGED)} / "
            f"위치+속성변경 "
            f"{summary.point_diff.count(PointChangeType.POINT_ATTRIBUTE_CHANGED)} / "
            f"삭제 {summary.point_diff.count(PointChangeType.DELETED)} / "
            f"누락 {summary.point_diff.count(PointChangeType.MISSING)} / "
            f"동일 {summary.point_diff.count(PointChangeType.UNCHANGED)}"
        ),
    ]
    detail_lines = []
    for change in diff.changes:
        snapshot = change.new_snapshot or change.old_snapshot or {}
        name = snapshot.get("facility_name") or "이름 없음"
        sgg = snapshot.get("sgg_code") or "-"
        detail_lines.append(f"- Polygon {change.change_type.value}: {name} ({sgg})")
    for change in summary.point_diff.changes:
        snapshot = change.new_snapshot or change.old_snapshot or {}
        name = snapshot.get("facility_name") or "이름 없음"
        sgg = snapshot.get("sgg_code") or "-"
        detail_lines.append(f"- Point {change.change_type.value}: {name} ({sgg})")
    lines.extend(detail_lines[:10])
    if len(detail_lines) > 10:
        lines.append(f"... 외 {len(detail_lines) - 10}건")
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
        if not summary.has_changes:
            return ()
        return self.send_text(format_summary(summary))

    def send_text(self, message: str) -> tuple[str, ...]:
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
