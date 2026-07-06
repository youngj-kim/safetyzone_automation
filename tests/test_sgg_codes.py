from pathlib import Path

import pytest

from safety_zone_monitor.sgg_codes import extract_current_sgg_codes, write_sgg_codes


def test_extracts_active_sgg_codes_from_official_style_csv(tmp_path: Path) -> None:
    source = tmp_path / "legal_codes.csv"
    source.write_bytes(
        (
            "법정동코드,법정동명,폐지여부\n"
            "1100000000,서울특별시,존재\n"
            "1111000000,서울특별시 종로구,존재\n"
            "1111010100,서울특별시 종로구 청운동,존재\n"
            "4159000000,경기도 화성시,폐지\n"
            "4159010100,경기도 화성시 진안동,폐지\n"
            "4159100000,경기도 화성시 만세구,존재\n"
        ).encode("cp949")
    )
    output = tmp_path / "sgg_codes.txt"

    assert extract_current_sgg_codes(source) == ("11110", "41591")
    assert write_sgg_codes(source, output) == ("11110", "41591")
    assert output.read_text(encoding="utf-8") == "11110\n41591\n"


def test_rejects_csv_without_abolition_status(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.csv"
    source.write_text("법정동코드,법정동명\n1111000000,서울특별시 종로구\n", encoding="utf-8")

    with pytest.raises(ValueError, match="abolition-status"):
        extract_current_sgg_codes(source)
