"""발행 직전 본문 정리.

프롬프트로 100% 막히지 않는 형식 문제를 코드가 마지막에 걷어낸다.
"""

import re

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
