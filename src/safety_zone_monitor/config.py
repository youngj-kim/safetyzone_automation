from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_API_URL = "https://apis.data.go.kr/1320000/safetyzonedtlinfo/getdtllist"


def load_dotenv(path: str | Path = ".env") -> None:
    """Load a small, dependency-free subset of dotenv syntax."""
    dotenv = Path(path)
    if not dotenv.exists():
        return
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _read_sgg_codes() -> tuple[str, ...]:
    raw_codes = os.getenv("SGG_CODES", "")
    file_name = os.getenv("SGG_CODES_FILE", "")
    values: list[str] = []
    if raw_codes:
        values.extend(raw_codes.replace("\n", ",").split(","))
    if file_name:
        for line in Path(file_name).read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                values.append(line)
    codes = tuple(sorted({value.strip() for value in values if value.strip()}))
    invalid = [code for code in codes if len(code) != 5 or not code.isdigit()]
    if invalid:
        raise ValueError(f"Invalid SGG code(s): {', '.join(invalid)}")
    return codes


@dataclass(frozen=True)
class Settings:
    service_key: str
    database_url: str
    sgg_codes: tuple[str, ...]
    api_url: str = DEFAULT_API_URL
    num_rows: int = 1000
    request_delay_seconds: float = 0.2
    timeout_seconds: float = 30.0
    slack_webhook_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv()
        service_key = os.getenv("OPEN_API_SERVICE_KEY", "").strip()
        database_url = os.getenv("DATABASE_URL", "").strip()
        sgg_codes = _read_sgg_codes()
        missing = []
        if not service_key:
            missing.append("OPEN_API_SERVICE_KEY")
        if not database_url:
            missing.append("DATABASE_URL")
        if not sgg_codes:
            missing.append("SGG_CODES or SGG_CODES_FILE")
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        num_rows = int(os.getenv("API_NUM_ROWS", "1000"))
        if not 1 <= num_rows <= 1000:
            raise ValueError("API_NUM_ROWS must be between 1 and 1000")
        return cls(
            service_key=service_key,
            database_url=database_url,
            sgg_codes=sgg_codes,
            api_url=os.getenv("OPEN_API_URL", DEFAULT_API_URL).strip(),
            num_rows=num_rows,
            request_delay_seconds=float(os.getenv("API_REQUEST_DELAY_SECONDS", "0.2")),
            timeout_seconds=float(os.getenv("API_TIMEOUT_SECONDS", "30")),
            slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL") or None,
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID") or None,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
