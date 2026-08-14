"""브리핑 보관 — reports/YYYY-MM-DD.md

오늘 브리핑을 남겨두고 다음 실행 때 planner 가 참고한다.
"""

from datetime import date as Date
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import PREV_DAYS, REPORTS_DIR


def today_kst() -> Date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def load_previous_reports(today: Date, n: int = PREV_DAYS) -> list[tuple[str, str]]:
    """오늘 것을 뺀 최근 브리핑 n개를 최신순으로. [(날짜, 본문), ...]"""
    if not REPORTS_DIR.exists():
        return []
    files = (f for f in sorted(REPORTS_DIR.glob("*.md"), reverse=True) if f.stem != str(today))
    return [(f.stem, f.read_text(encoding="utf-8")) for f in list(files)[:n]]


def save_report(today: Date, body: str) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"{today}.md"
    path.write_text(body, encoding="utf-8")
    return path
