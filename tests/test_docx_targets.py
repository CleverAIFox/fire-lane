#!/usr/bin/env python3
"""
test_docx_targets.py — `PLAN §12` 가 지목한 것이 기획서에 실재하는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-31. `PLAN §12`(기획서 갱신 대상)의 남은 다섯 건을 처리하려고
문서를 뒤졌더니 **셋이 문서에 없는 것을 고치라고 적고 있었다** —
소방서 대조를 "검증" 으로 쓴 자리(`검증` 33회 중 소방서 문맥 0회),
소화전 "동명동 1개"(0회), CCTV 낡은 값(집계 범위가 다른 것이었다).

`docx_check.py` 는 **문서에 있는 숫자**를 산출물과 대조한다. 없는 것은
못 센다. 그래서 이 표가 낡아도 조용하다 — 강제자가 한 방향만 보면
반대 방향이 사각지대가 된다(DECISIONS §78 · R23).

★ 이 저장소가 이미 같은 것을 배웠다. `docnum_check` 는 `PRESENT`(있는가)와
  `RETIRED`(없는가)를 짝으로 갖는다. 그 원리를 §12 표에 적용한다.

── 무엇을 보는가 ───────────────────────────────────────────────
`§12` 표의 **남은** 행에서 백틱 안 문자열을 뽑아 docx 평문에 있는지 본다.
없으면 "고칠 대상이 없다" 는 뜻이고 그 행은 ⬛ 로 내려야 한다.

★ ⬛ 행은 보지 않는다. 이미 처리됐고, 고친 뒤에는 옛 문자열이 없는 것이
  정상이다. 그것까지 검사하면 정반대로 운다.

IN    docs/PLAN.md §12 · docs/proposal.docx
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs/PLAN.md"
DOCX = ROOT / "docs/proposal.docx"

# 지목이 아니라 **참조**인 것. 문서 안에 있을 이유가 없다.
# ★ 도구·필드·파일 이름이 여기 들어온다. `#2` 가 처리 수단으로 적은
#   `docx_fix` 를 "기획서에 없다" 로 잡은 것이 이 목록이 생긴 이유다.
SKIP = re.compile(
    r"^(MASTER|PLAN|DECISIONS|docs/|src/|tools/|tests/|\.github/|#\d)"
    r"|^[a-z][a-z0-9_]*(\.py)?$"          # docx_fix · segments.geojson 류
    r"|^[a-z_]+/[a-z_./]+$")


def _docx_text() -> str:
    xml = zipfile.ZipFile(DOCX).read("word/document.xml").decode("utf-8")
    return re.sub(r"<[^>]+>", "", xml)


def _open_rows() -> list[tuple[str, str]]:
    """`§12` 표의 ⬛ 가 아닌 행 → (번호, 본문)."""
    t = PLAN.read_text(encoding="utf-8")
    i = t.find("## 12. 기획서 갱신 대상")
    if i < 0:
        return []
    body = t[i:]
    out = []
    for line in body.splitlines():
        m = re.match(r"^\| ([0-9]+[a-z]?) \| (.*)$", line)
        # ★ ⬛ 뿐 아니라 "완료" 도 처리된 것으로 본다. `#2` `#7` 이
        #   `| 완료 `docx_fix` |` 형식이라 ⬛ 만 보면 남은 행으로 잡힌다.
        if m and "⬛" not in line and "완료" not in line:
            out.append((m.group(1), m.group(2)))
    return out


def test_plan12_targets_exist_in_docx():
    """§12 가 지목한 문자열이 기획서에 있는가.

    ★ 방향이 `docx_check` 와 반대다. 그것은 "문서의 숫자가 산출물과 같은가",
      이것은 "표가 가리키는 것이 문서에 있는가" 를 본다. 둘 다 있어야
      표와 문서가 같이 낡지 않는다.
    """
    if not DOCX.exists():
        pytest.skip("기획서가 없다")
    rows = _open_rows()
    if not rows:
        pytest.skip("§12 에 남은 행이 없다")

    txt = _docx_text()
    bad = []
    for num, body in rows:
        quoted = [q for q in re.findall(r"`([^`]+)`", body)
                  if not SKIP.match(q) and len(q) >= 3]
        if not quoted:
            continue
        missing = [q for q in quoted if q not in txt]
        if len(missing) == len(quoted):
            bad.append(f"  #{num}  지목 {quoted} 가 기획서에 하나도 없다")

    assert not bad, (
        "PLAN §12 가 문서에 없는 것을 고치라고 적는다:\n" + "\n".join(bad) +
        "\n\n  고칠 대상이 없으면 그 행을 ⬛ '해당 없음' 으로 내려라.\n"
        "  08-31 에 다섯 건 중 셋이 이 상태였다 — 표가 문서보다 먼저 낡았다.")
