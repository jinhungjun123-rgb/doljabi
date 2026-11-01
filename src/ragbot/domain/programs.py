"""앱이 보여 주는 지원사업과 청년미래센터 (data/programs/programs.json).

이 파일은 scripts/build_programs.py 가 팀 검수 결과(data/programs/review/)에서 만든다. 손으로 고치지 않는다.
"""
import json
from pathlib import Path

from ragbot.config import DATA_DIR

PROGRAMS_FILE = DATA_DIR / "programs" / "programs.json"
REGIONS = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
           "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
_PROGRAM_KEYS = {"id", "group", "name", "summary", "region", "apply_type", "target", "income", "benefit", "how",
                 "period", "contact", "source", "notice", "closed", "checked"}
_CENTER_KEYS = {"region", "name", "status", "phone", "email"}


def load_programs(path: Path = PROGRAMS_FILE) -> dict:
    """{"updated", "programs": [...], "centers": [...]}. 형식이 어긋나면 앱이 시작하지 않도록 ValueError."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for p in data["programs"]:
        if missing := _PROGRAM_KEYS - p.keys():
            raise ValueError(f"program {p.get('id')} lacks {sorted(missing)}")
    for c in data["centers"]:
        if missing := _CENTER_KEYS - c.keys():
            raise ValueError(f"center {c.get('region')} lacks {sorted(missing)}")
    return data


def center_for(region: str | None, data: dict) -> dict | None:
    return next((c for c in data["centers"] if c["region"] == region), None) if region else None
