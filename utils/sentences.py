"""문장 번호 — checker 와 reviser 가 본문을 가리키는 주소.

작은 모델에게 문장을 받아 적게 하면 글자가 바뀐다. 그러면 코드가 그 문장을
본문에서 다시 찾지 못하고, URL 은 지어낼 수 있다. 그래서 역할을 나눈다.

    코드   문장 경계를 정하고 ⟦n⟧ 을 붙여 보여준다. 판정대로 갈아 끼우고 인용을 단다.
    모델   번호로 가리키기만 한다. 텍스트를 내는 건 "고친 문장 한 개" 뿐이다.

경계 규칙은 하나다 — 한글이나 닫는 괄호 뒤의 마침표 + 공백.
7,718.60 이나 U.S. 안의 마침표는 앞 글자가 숫자·영문이라 걸리지 않는다.
경계가 어긋나도 글은 다치지 않는다. 조각을 이어 붙이면 언제나 원문 그대로다.
"""

import re

_END = re.compile(r"(?<=[가-힣)])\.\s+")          # 문장 끝: 마침표 + 공백
_SENTENCE = re.compile(r"\S.*[가-힣)]\.\s*$", re.S)  # 번호를 받을 조각의 모양
_CITE_MAX = 2                                       # 문장 하나에 다는 인용 수


def split(text: str) -> list[str]:
    """본문을 조각으로 자른다. 이어 붙이면 원문과 같다.

    문장 모양인 조각만 번호를 받는다. 제목·빈 줄·마침표로 안 끝나는 줄은
    그대로 지나간다.
    """
    pieces: list[str] = []
    for line in text.splitlines(keepends=True):
        pos = 0
        for m in _END.finditer(line):
            pieces += [line[pos : m.start() + 1], line[m.start() + 1 : m.end()]]
            pos = m.end()
        pieces.append(line[pos:])
    return [p for p in pieces if p]


def is_sentence(piece: str) -> bool:
    return bool(_SENTENCE.match(piece))


def count(text: str) -> int:
    return sum(map(is_sentence, split(text)))


def mark(text: str) -> str:
    """모델에게 보여줄 본문. 문장 앞에 ⟦n⟧ 을 붙인다."""
    out, n = [], 0
    for piece in split(text):
        if is_sentence(piece):
            n += 1
            piece = f"⟦{n}⟧{piece}"
        out.append(piece)
    return "".join(out)


def assemble(text: str, verdicts: list[dict], fixes: dict[int, str], articles: list[dict]) -> str:
    """판정대로 문장을 갈아 끼우고 인용을 단다.

    판정이 없는 문장은 손대지 않는다. CONTRADICTED 인데 고친 문장이 없으면
    원문을 그대로 두고 인용도 달지 않는다 — 틀린 문장에 출처를 붙이지 않는다.
    """
    by_no = {v["sentence"]: v for v in verdicts}
    out, n = [], 0
    for piece in split(text):
        if not is_sentence(piece):
            out.append(piece)
            continue
        n += 1
        v = by_no.get(n)
        if v is None:
            out.append(piece)
            continue

        body, tail = piece.rstrip(), piece[len(piece.rstrip()) :]
        fixed = v["verdict"] == "CONTRADICTED" and n in fixes
        if fixed:
            body = fixes[n]
        if v["verdict"] == "SUPPORTED" or fixed:
            body = _cite(body, v["articles"], articles)
        out.append(body + tail)
    return "".join(out)


def _cite(body: str, numbers: list[int], articles: list[dict]) -> str:
    """마침표 앞에 ([매체](URL)) 을 끼운다. 번호는 checker 가 검증한 것만 온다."""
    links = ", ".join(
        f"[{articles[i - 1]['media']}]({articles[i - 1]['url']})" for i in numbers[:_CITE_MAX]
    )
    if not links or not body.endswith("."):
        return body
    return f"{body[:-1]}({links})."


def numbers(text: str) -> list[str]:
    """문장 속 수치 토큰. 수정값이 근거에 실제로 있는지 확인할 때 쓴다."""
    return re.findall(r"\d[\d,]*(?:\.\d+)?", text)
