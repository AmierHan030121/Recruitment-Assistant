from pathlib import Path


def read_fixture(*parts: str) -> str:
    fixture_path = Path(__file__).parent / "fixtures" / Path(*parts)
    return fixture_path.read_text(encoding="utf-8")
