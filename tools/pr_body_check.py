#!/usr/bin/env python3
"""
pr_body_check.py — PR 본문이 템플릿을 실제로 채웠는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-27. PR 템플릿을 도입했다. **템플릿만으로는 아무것도 강제되지
않는다** — 지우고 한 줄 쓰면 그만이다. 이 저장소가 반복해 배운 형태가
정확히 그것이다. 규약은 문서에 존재하고 강제자가 없다(MASTER §17).

승인이 도장이 되는 것을 규율로 막을 수 없다. 형식으로 막는다.
**"어디를 보라" 가 없으면 사람은 전부를 안 보고 도장을 찍는다.**
한 곳을 지목하면 그 한 곳은 실제로 본다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. `리뷰어가 볼 곳` 에 `파일:줄` 또는 파일 경로가 있는가
    2. `전체 확인` 류의 회피 문구가 없는가
    3. 산출물 체크박스 중 정확히 하나가 찍혔는가
    4. 계약 체크박스 중 정확히 하나가 찍혔는가

★ 본문 길이나 문체는 보지 않는다. 검사가 시끄러우면 사람이 우회하고,
  우회가 습관이 되면 강제자 전체가 무력해진다.

IN    GITHUB_EVENT_PATH (pull_request.body)  또는  --body-file
OUT   없음 (검사). 실패 시 종료코드 1
PARAM 없음
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# 회피 문구. 이게 있으면 지목이 아니다.
DODGE = re.compile(r"전체\s*(확인|리뷰|검토)|전부\s*(확인|봐)|알아서|아무데나|"
                   r"다\s*확인|특별히\s*없", re.I)

# 파일 경로처럼 보이는 것. `src/cv/mask.py:212` · `web/js/map.js`
PATHISH = re.compile(
    # 확장자가 있는 경로
    r"[\w./-]+\.(?:py|js|md|yml|yaml|json|html|css|toml|sh|txt|lock|geojson)(?::\d+)?"
    # 확장자 없는 관례적 파일. 2026-08-30 에 `.github/CODEOWNERS:64` 를
    # 지목한 PR 이 "경로가 없다" 로 막혔다. 규칙이 현실을 못 따라간 것이다.
    r"|(?:[\w./-]*/)?(?:CODEOWNERS|Dockerfile|Makefile|LICENSE)(?:\.\w+)?(?::\d+)?"
    # 디렉토리 지목도 인정한다. `src/contracts/` 처럼
    r"|(?:[\w-]+/){1,}(?::\d+)?"
)

CHECKED = re.compile(r"^\s*-\s*\[[xX]\]", re.M)


def _section(body: str, title: str) -> str:
    """`## 제목` 아래 다음 `##` 까지."""
    m = re.search(rf"^##+\s*{re.escape(title)}.*?$(.*?)(?=^##+\s|\Z)",
                  body, re.M | re.S)
    return m.group(1) if m else ""


def _strip_comments(body: str) -> str:
    """HTML 주석 제거. 템플릿 안내문이 내용으로 세지 않게 한다."""
    return re.sub(r"<!--.*?-->", "", body, flags=re.S)


def check(body: str) -> list[str]:
    body = _strip_comments(body or "")
    bad: list[str] = []

    if not body.strip():
        return ["PR 본문이 비어 있다. 템플릿을 채워라."]

    # ── 1 · 리뷰 지목 ──
    look = _section(body, "리뷰어가 볼 곳")
    if not look.strip():
        bad.append(
            "`## 리뷰어가 볼 곳` 절이 비어 있다.\n"
            "    파일 경로 하나를 적어라. 예) src/firelane/seg/width.py:212\n"
            "    지목이 없으면 리뷰어는 전부를 안 보고 승인한다.")
    elif DODGE.search(look):
        bad.append(
            "`리뷰어가 볼 곳` 에 회피 문구가 있다.\n"
            "    '전체 확인 부탁' 은 확인 안 한다는 뜻이다. 한 곳만 지목해라.")
    elif not PATHISH.search(look):
        bad.append(
            "`리뷰어가 볼 곳` 에 파일 경로가 없다.\n"
            "    `경로/파일.py:줄` 형태로 적는다.")

    # ── 2 · 산출물 ──
    out = _section(body, "산출물이 바뀌는가")
    if out and len(CHECKED.findall(out)) != 1:
        bad.append(
            "`산출물이 바뀌는가` 에서 정확히 하나를 고른다.\n"
            "    바뀌면 tools/golden.py lock 재잠금이 필요하다(R11).\n"
            "    안 고르면 지문이 낡은 채로 머지된다.")

    # ── 3 · 계약 ──
    con = _section(body, "계약을 건드리는가")
    if con and len(CHECKED.findall(con)) != 1:
        bad.append(
            "`계약을 건드리는가` 에서 정확히 하나를 고른다.\n"
            "    계약은 파트 간 유일한 접점이다. 말없이 바꾸면 남의 파트가 깨진다.")

    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--body-file", help="PR 본문 파일 (로컬 시험용)")
    a = ap.parse_args()

    if a.body_file:
        body = open(a.body_file, encoding="utf-8").read()
    else:
        ev = os.environ.get("GITHUB_EVENT_PATH")
        if not ev or not Path(ev).exists():
            print("PR 컨텍스트가 아니다 — 건너뛴다")
            return 0
        with open(ev, encoding="utf-8") as f:
            body = (json.load(f).get("pull_request") or {}).get("body") or ""

    bad = check(body)
    if not bad:
        print("PR 본문 OK")
        return 0

    print("PR 본문이 템플릿을 채우지 않았다.\n")
    for b in bad:
        print(f"  ✗ {b}\n")
    print("  고치는 법 — PR 화면에서 본문을 편집하면 검사가 다시 돈다.")
    print("  템플릿 정본: .github/pull_request_template.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())

