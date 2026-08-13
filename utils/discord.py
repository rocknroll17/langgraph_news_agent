"""디스코드 웹훅 전송.

제약 두 가지를 여기서 흡수한다.
- 메시지 1건당 2000자
- 웹훅당 2초에 5건 (초과하면 429)
"""

import os
import re
import time

import requests

MESSAGE_LIMIT = 1900   # 실제 제한은 2000자. 헤더 여유분을 뺀 값.
SEND_INTERVAL = 0.5    # 조각 사이 대기 (2초당 5건 제한 회피)
TIMEOUT = 30

# Discord 메시지 플래그. SUPPRESS_EMBEDS = 1 << 2.
# 이걸 켜면 링크 미리보기 카드가 안 붙어서, 출처 링크가 많아도 화면이 안 지저분하다.
SUPPRESS_EMBEDS = 1 << 2


def split_message(text: str, limit: int = MESSAGE_LIMIT) -> list[str]:
    """길이 제한에 맞춰 자른다. 줄 단위로 끊어 문장이 잘리지 않게 한다."""
    chunks: list[str] = []
    buf = ""
    for line in text.splitlines(keepends=True):
        # 한 줄 자체가 제한을 넘으면 어쩔 수 없이 강제로 자른다
        while len(line) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) > limit:
            chunks.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        chunks.append(buf)
    return chunks


def webhook_urls() -> list[str]:
    """DISCORD_WEBHOOK_URL 에서 웹훅 목록을 읽는다.

    쉼표나 줄바꿈으로 여러 개를 넣을 수 있다. 채널을 늘려도 코드는 그대로다.
        DISCORD_WEBHOOK_URL=https://.../a,https://.../b
    """
    raw = os.environ.get("DISCORD_WEBHOOK_URL", "")
    return [u.strip() for u in re.split(r"[,\n]", raw) if u.strip()]


def send(
    text: str,
    webhook_url: str | list[str] | None = None,
    suppress_embeds: bool = True,
) -> int:
    """웹훅으로 보낸다. 길면 나눠 보내고, 보낸 메시지 총 건수를 돌려준다.

    웹훅을 여러 개 주면 모두에게 보낸다. 하나가 실패해도 나머지는 계속 보내고,
    끝난 뒤에 실패를 모아서 알린다 — 한 채널 때문에 전체가 날아가면 안 된다.

    suppress_embeds=True 면 링크 미리보기 카드를 붙이지 않는다.
    출처 링크가 여러 개 달리는 브리핑에서는 켜두는 편이 읽기 좋다.
    """
    if webhook_url is None:
        urls = webhook_urls()
    elif isinstance(webhook_url, str):
        urls = [webhook_url]
    else:
        urls = list(webhook_url)

    if not urls:
        raise ValueError("보낼 웹훅이 없습니다. DISCORD_WEBHOOK_URL 을 확인하세요.")

    chunks = split_message(text)
    payload_base = {"flags": SUPPRESS_EMBEDS} if suppress_embeds else {}

    sent, failed = 0, []
    for url in urls:
        try:
            sent += _send_one(url, chunks, payload_base)
        except Exception as e:
            failed.append(f"{_mask(url)}: {type(e).__name__}")

    if failed:
        print(f"[discord] 발송 실패 {len(failed)}/{len(urls)} — {', '.join(failed)}")
    if not sent:
        raise RuntimeError("모든 웹훅 발송에 실패했습니다.")
    return sent


def _send_one(url: str, chunks: list[str], payload_base: dict) -> int:
    for i, chunk in enumerate(chunks):
        if i:
            time.sleep(SEND_INTERVAL)
        payload = {**payload_base, "content": chunk}
        r = requests.post(url, json=payload, timeout=TIMEOUT)
        if r.status_code == 429:   # 그래도 걸리면 Discord 가 알려준 만큼 기다렸다 재시도
            time.sleep(float(r.json().get("retry_after", 1)))
            r = requests.post(url, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
    return len(chunks)


def _mask(url: str) -> str:
    """로그에 토큰이 남지 않게 웹훅 ID 뒷부분만 보여준다."""
    return f"…{url.rsplit('/', 1)[0][-12:]}"
