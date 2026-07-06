from __future__ import annotations

import csv
import re
from pathlib import Path


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unsupported CSV encoding: {path}")


def _normalized_header(value: str) -> str:
    return re.sub(r"[\s_()-]", "", value).lower()


def extract_current_sgg_codes(source: str | Path) -> tuple[str, ...]:
    """Extract current five-digit SGG codes from the official legal-dong CSV."""
    path = Path(source)
    text = _read_text(path)
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t|")
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("The legal-code CSV has no header row")

    headers = {_normalized_header(name): name for name in reader.fieldnames}
    code_column = next(
        (
            headers[name]
            for name in (
                "법정동코드",
                "지역코드",
                "법정동코드주민",
                "regioncode",
                "code",
            )
            if name in headers
        ),
        None,
    )
    status_column = next(
        (
            headers[name]
            for name in ("폐지여부", "폐지구분", "존재여부", "status")
            if name in headers
        ),
        None,
    )
    if code_column is None or status_column is None:
        raise ValueError("CSV must contain legal-dong code and abolition-status columns")

    abolished_values = {"폐지", "말소", "y", "yes", "1", "repl", "abolished"}
    codes = set()
    for row in reader:
        status = str(row.get(status_column) or "").strip().lower()
        if status in abolished_values:
            continue
        legal_code = re.sub(r"\D", "", str(row.get(code_column) or ""))
        if len(legal_code) != 10:
            continue
        sgg_code = legal_code[:5]
        if sgg_code[2:] == "000":
            continue
        codes.add(sgg_code)
    if not codes:
        raise ValueError("No active SGG codes were found in the CSV")
    return tuple(sorted(codes))


def write_sgg_codes(source: str | Path, output: str | Path) -> tuple[str, ...]:
    codes = extract_current_sgg_codes(source)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(codes) + "\n", encoding="utf-8")
    return codes
