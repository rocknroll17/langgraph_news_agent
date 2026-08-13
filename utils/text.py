"""본문 다듬기와 인용 색인.

프롬프트로 100% 막히지 않는 형식 문제를 코드가 마지막에 정리한다.
URL·마크업 같은 기계적인 것은 기계가 다루는 편이 확실하다.
"""

import ast
import re
from urllib.parse import urlparse

# 내부용 표기 — 독자가 볼 글에 남으면 안 된다
_MARKERS = re.compile(r"\s*(\(?\[(?:미확인|불일치)\]\)?|[→↑↔](?:원인|결과|대조|후속):)")

# 내용이 사실상 비어 있는 섹션 본문
_EMPTY = re.compile(r"^(없음|없습니다|없다|해당\s*없음|특이사항\s*없음|N/?A|-{1,3}|\.)$", re.I)


def strip_markers(body: str) -> str:
    """검증·정리용 표기를 떼어낸다."""
    return _MARKERS.sub("", body)


def drop_empty_sections(body: str) -> tuple[str, list[str]]:
    """내용이 '없음' 뿐인 섹션을 제목째 지운다. (본문, 지운 제목들) 을 돌려준다."""
    lines = body.splitlines()
    kept: list[str] = []
    dropped: list[str] = []
    i = 0

    while i < len(lines):
        if not lines[i].startswith("#"):
            kept.append(lines[i])
            i += 1
            continue

        end = next((j for j in range(i + 1, len(lines)) if lines[j].startswith("#")), len(lines))
        content = [ln.strip() for ln in lines[i + 1 : end] if ln.strip()]

        if not content or all(_EMPTY.match(ln) for ln in content):
            dropped.append(lines[i].lstrip("# ").strip())
        else:
            kept.extend(lines[i:end])
        i = end

    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip(), dropped


def build_index(messages) -> list[dict]:
    """ToolMessage 원문에서 (매체, 제목, URL, 발췌) 색인을 만든다.

    검색 원문을 통째로 넘기면 컨텍스트가 넘친다.
    인용에 필요한 건 '어떤 기사에 무슨 내용이 있었나' 뿐이다.
    """
    index: list[dict] = []
    seen: set[str] = set()

    for m in messages:
        if type(m).__name__ != "ToolMessage":
            continue
        try:
            payload = ast.literal_eval(str(m.content))
        except (ValueError, SyntaxError):
            continue
        for r in (payload or {}).get("results", []) if isinstance(payload, dict) else []:
            url = (r.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            index.append({
                "media": media_name(url),
                "title": (r.get("title") or "").strip(),
                # 짧으면 verifier 가 근거를 못 찾아 NOT_ENOUGH_INFO 가 늘어난다
                "snippet": " ".join((r.get("content") or "").split())[:700],
                "url": url,
            })
    return index


def render_index(index: list[dict]) -> str:
    """verifier 프롬프트에 넣을 색인 문자열."""
    return "\n".join(
        f"[{i}] 매체: {r['media']}\n    제목: {r['title']}\n"
        f"    URL: {r['url']}\n    내용: {r['snippet']}"
        for i, r in enumerate(index, 1)
    )


def media_name(url: str) -> str:
    """도메인에서 읽기 좋은 매체명을 만든다. news.bbc.co.uk -> Bbc"""
    host = urlparse(url).netloc.removeprefix("www.")
    if not host:
        return url
    skip = {"com", "co", "net", "org", "kr", "uk", "ph", "io", "news"}
    parts = [p for p in host.split(".") if p not in skip]
    return (parts[-1] if parts else host.split(".")[0]).capitalize()
