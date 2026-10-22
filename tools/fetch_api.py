#!/usr/bin/env python3
"""
tools/fetch_api.py — 공공데이터포털 표준데이터 API 를 **같은 방법으로 다시 받는다** (PLAN #141)

    uv run python tools/fetch_api.py                      받을 수 있는 자료와 키 설정 여부(값은 안 찍는다)
    uv run python tools/fetch_api.py hydrant_point        어떻게 부를지(URL · 파라미터)만 찍는다 — 호출 안 한다
    uv run python tools/fetch_api.py hydrant_point --run  실제로 받아 `$FIRE_LANE_INBOX` 에 JSON 한 벌을 쓴다
    uv run python tools/fetch_api.py --selftest           ★ 키·망 없이 URL 조립·쪽 넘김·키 가림을 민다

── 왜 만들었나 ─────────────────────────────────────────────────
대장 72종 중 API 로 받은 것은 `hydrant_point` 하나인데, 그때 쓴 `fetch_api` 는 **일회성 도구라 저장소에 없다.**
받은 파일만 있고 받는 법이 없어서 같은 자료를 다시 받으려면 아무도 방법을 몰랐다(PLAN #141 · DECISIONS §315).
`sources.yaml` 의 취득 기록(`api.data.go.kr/openapi/tn_pubr_public_ffus_wtrcns_api` · `type=json` ·
`ctprvnNm=광주광역시` · 잘림 없음 `fetched == totalCount`)을 **그대로 도구로 옮겼다.**

★ **키는 지금 필요 없다.** 이 도구는 받는 법을 남길 뿐이고, 재취득이 필요한 상황이 아니다.
★ 키 값은 `.env` 의 `FIRE_LANE_DATA_GO_KR_KEY` 하나에 산다. `.env.example` 에는 이름만 있고 `env_check` 가 대조한다.
  읽는 자리는 `paths.secret` 하나다 — **어디에도 값을 찍지 않는다**(`repr` 만 쓴다).
★ 받은 것을 `data/raw` 에 직접 쓰지 않는다. `$FIRE_LANE_INBOX` 로 내고 편입은 `acquire.py --stage` 가 한다.

IN    `$FIRE_LANE_DATA_GO_KR_KEY` · 망 (`--run` 일 때만)
OUT   `$FIRE_LANE_INBOX/<name>_api.json` (`--run` 일 때만)
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
밖    **받은 자료의 옳음은 안 본다** — 쪽을 다 넘겼나(`fetched == totalCount`)만 본다. 대장에 올리는 일(`ledger`)과
      raw 편입(`acquire.py`)도 이 도구의 일이 아니다. 포털의 다른 API 를 아는 척하지 않는다 — 아래 `SOURCES` 의 것만.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from firelane import paths

KEY_NAME = "FIRE_LANE_DATA_GO_KR_KEY"
PAGE = 1000          # 쪽당 행. 포털 상한 안에서 크게 — 호출 수를 줄인다

#: 받는 법을 아는 자료. `sources.yaml` 의 항목 이름과 같다. **대장의 취득 기록을 옮긴 것**이고 새로 지어낸 것이 아니다.
SOURCES: dict[str, dict] = {
    "hydrant_point": {
        "url": "https://api.data.go.kr/openapi/tn_pubr_public_ffus_wtrcns_api",
        "params": {"type": "json", "ctprvnNm": "광주광역시"},
        "note": "전국소방용수시설표준데이터 · 광주 5,002 · 동구 651(2026-08-30 취득). 포털 CSV 는 50,000 상한에 잘려 이 API 로 받았다.",
    },
}


def build_url(name: str, page: int, key: str = "<KEY>") -> str:
    """`serviceKey` 를 맨 앞에 두고 쪽을 붙인다. `key` 는 **값이 아니라 자리표시자**로 찍을 수 있다."""
    s = SOURCES[name]
    q = {"serviceKey": key, "pageNo": page, "numOfRows": PAGE, **s["params"]}
    return s["url"] + "?" + urllib.parse.urlencode(q, safe="<>")


def parse_page(body: dict) -> tuple[list, int]:
    """포털 응답에서 (행 목록, totalCount). 모양이 다르면 **조용히 비우지 않고** 운다."""
    r = body.get("response")
    if not isinstance(r, dict) or "body" not in r:
        raise ValueError(f"응답 모양이 다르다 — 키 오류일 수 있다: {str(body)[:120]}")
    b = r["body"]
    items = b.get("items") or []
    if isinstance(items, dict):          # 포털이 한 건을 dict 로 주는 경우
        items = items.get("item", [])
    if isinstance(items, dict):
        items = [items]
    return list(items), int(b.get("totalCount", 0))


def fetch_all(name: str, key: str, opener=urllib.request.urlopen) -> list:
    rows: list = []
    page = 1
    while True:
        with opener(build_url(name, page, key), timeout=60) as resp:
            got, total = parse_page(json.loads(resp.read().decode("utf-8")))
        rows += got
        if not got or len(rows) >= total:
            break
        page += 1
    if len(rows) != total:
        raise RuntimeError(f"잘렸다 — fetched {len(rows)} ≠ totalCount {total}")
    return rows


def selftest() -> int:
    import io
    bad: list[str] = []
    u = build_url("hydrant_point", 2)
    for need in ("serviceKey=<KEY>", "pageNo=2", "type=json", "ctprvnNm=", "api.data.go.kr"):
        if need not in u:
            bad.append(f"URL 에 {need} 가 없다 — {u}")
    pages = {1: {"response": {"body": {"totalCount": 3, "items": [{"a": 1}, {"a": 2}]}}},
             2: {"response": {"body": {"totalCount": 3, "items": {"item": {"a": 3}}}}}}
    seen: list[str] = []

    def fake(url, timeout):
        seen.append(url)
        n = int(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["pageNo"][0])
        return io.BytesIO(json.dumps(pages[n]).encode())
    fake_cm = type("C", (), {"__init__": lambda s, b: setattr(s, "b", b), "__enter__": lambda s: s.b, "__exit__": lambda s, *a: False})
    rows = fetch_all("hydrant_point", "K", lambda url, timeout: fake_cm(fake(url, timeout)))
    if len(rows) != 3:
        bad.append(f"쪽을 넘겨 3행이어야 하는데 {len(rows)}")
    try:
        parse_page({"error": "x"})
        bad.append("모양이 다른 응답을 조용히 통과시켰다")
    except ValueError:
        pass
    try:
        def cut(url, timeout):      # 첫 쪽만 주고 둘째 쪽부터 빈다 — 중간에 끊긴 수집
            first = "pageNo=1" in url
            return fake_cm(io.BytesIO(json.dumps(
                {"response": {"body": {"totalCount": 5, "items": [{"a": 1}] if first else []}}}).encode()))
        fetch_all("hydrant_point", "K", cut)
        bad.append("잘린 수집(1 < 5)을 통과시켰다")
    except RuntimeError:
        pass
    sec = paths.secret("__NO_SUCH_KEY__")
    if "__NO_SUCH_KEY__" in repr(sec) or repr(sec) != "<secret 없음>":
        bad.append("비밀의 repr 이 이상하다")
    for b in bad:
        print("  ✗", b)
    print("✓ 살아 있다" if not bad else f"✗ {len(bad)}건")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("name", nargs="?", choices=sorted(SOURCES))
    ap.add_argument("--run", action="store_true", help="실제로 호출한다(키 필요)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    key = paths.secret("FIRE_LANE_DATA_GO_KR_KEY")
    if a.name is None:
        print(f"키 {KEY_NAME}: {'설정됨' if key else '비어 있음'} (값은 안 찍는다)\n")
        for n, s in SOURCES.items():
            print(f"  {n:<14} {s['note']}")
        return 0
    print(f"{a.name}\n  {build_url(a.name, 1)}\n  쪽당 {PAGE}행 · 쪽을 넘기며 fetched == totalCount 를 확인한다")
    if not a.run:
        return 0
    if not key:
        print(f"✗ {KEY_NAME} 가 비어 있다 — .env 에 채워라(키는 지금 필요 없다면 여기서 멈춘다)", file=sys.stderr)
        return 2
    inbox = paths.env("FIRE_LANE_INBOX")
    if not inbox:
        print("✗ FIRE_LANE_INBOX 가 비어 있다", file=sys.stderr)
        return 2
    rows = fetch_all(a.name, str(key))
    dst = Path(inbox) / f"{a.name}_api.json"
    dst.write_text(json.dumps(rows, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ {len(rows)}행 → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
