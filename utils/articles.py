"""검색 결과를 기사 단위로 다루는 도구.

Tavily 응답은 파이썬 dict 을 문자열로 만든 형태라 그대로 쓰기 어렵다.
여기서 기사 한 건씩으로 쪼개고, 매체명을 붙이고, 프롬프트에 넣을 형태로 편다.
"""

import ast
from urllib.parse import urlparse


def to_sends(messages, date) -> list[dict]:
    """직전 검색 결과를 refiner 한 건씩으로 쪼갠다. Send 페이로드 목록."""
    out: list[dict] = []
    seen: set[str] = set()

    for m in reversed(messages):
        if type(m).__name__ != "ToolMessage":
            break                      # 직전 한 회차분만
        for r in _results(m):
            url = (r.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.append({
                "date": str(date),
                "media": media_name(url),
                "title": (r.get("title") or "").strip(),
                "url": url,
                "published": (r.get("published_date") or "").strip(),
                "content": " ".join((r.get("content") or "").split()),
            })
    return out


def render(articles: list[dict], start: int = 1) -> str:
    """프롬프트에 넣을 기사 본문. 번호는 회차를 넘어 이어진다.

    발행일을 같이 준다. synthesizer 와 checker 의 "당일 자료가 아니면 버려라/틀렸다"
    규칙은 이 줄이 있어야 작동한다.
    """
    return "\n\n".join(
        f"[{i}] 매체: {a['media']}\n    제목: {a['title']}\n    발행: {a['published'] or '미상'}\n"
        f"    URL: {a['url']}\n    내용: {a['content']}"
        for i, a in enumerate(articles, start)
    )


def media_name(url: str) -> str:
    """도메인에서 읽기 좋은 매체명을 만든다.
    news.bbc.co.uk -> Bbc, businesstimes.com.sg -> Businesstimes
    """
    host = urlparse(url).netloc.removeprefix("www.")
    if not host:
        return url
    skip = {"com", "co", "net", "org", "gov", "news",          # 일반 접미사
            "kr", "uk", "sg", "jp", "hk", "cn", "in", "tr"}    # 국가 코드
    parts = [p for p in host.split(".") if p not in skip]
    return (parts[-1] if parts else host.split(".")[0]).capitalize()


def _results(message) -> list[dict]:
    """ToolMessage 안의 검색 결과 목록. 형식이 깨졌으면 건너뛴다."""
    try:
        payload = ast.literal_eval(str(message.content))
    except (ValueError, SyntaxError):
        return []
    return payload.get("results") or [] if isinstance(payload, dict) else []
