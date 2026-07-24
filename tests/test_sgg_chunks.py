from pathlib import Path


def _read_codes(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_nationwide_chunks_cover_nationwide_codes_in_order() -> None:
    nationwide = _read_codes(Path("config/sgg_codes_nationwide.txt"))
    chunk_paths = sorted(Path("config/sgg_chunks").glob("nationwide_chunk_*.txt"))
    chunked = [code for path in chunk_paths for code in _read_codes(path)]

    assert len(chunk_paths) == 6
    assert chunked == nationwide
    assert all(len(_read_codes(path)) <= 50 for path in chunk_paths)
