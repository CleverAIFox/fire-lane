#!/usr/bin/env python3
"""
docgen.py — 문서가 **흐르는 숫자**를 글자로 들지 않는다. 도구가 채운다.

    uv run python tools/docgen.py            생성 블록을 실물 값으로 채운다
    uv run python tools/docgen.py --check    대조만 — 어긋나면 rc≠0 (verify.sh · 시험)
    uv run python tools/docgen.py --list     축 · 실물 값 · 블록이 몇 곳인가

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-25 (DECISIONS §246). 축은 섰는데 **울기만 하고 고쳐주지 않았다.**
  하루 사이에 사람이 손으로 맞춘 것 —

      전수 절 수      1,004 → 1,017 → 1,030 → 1,033 → 1,036   (하루 네 번)
      봉인 소스 종수   64 → 71
      PLAN §1 행수     114 → 108

  §246-1 이 「숫자를 고치는 것은 처방이 아니다」라고 적고 축을 박았다. 그
  다음 칸이 비어 있었다 — **축이 아는 값을 문서에 넣어주는 자리.** 검사는
  사람을 부르고 사람은 매번 같은 줄을 고친다. 고치는 일이 사람에게 남아
  있으면 그 일은 갈린다 — 문서가 숫자를 **들지 않게** 하는 것이 처방이다.

★ **정본은 실물이다.** 이 도구는 문서를 문서로 대조하지 않는다. 대장은
  `ledger.load()`, 절은 `dms.scan()`, PLAN §1 행은 `plan_renumber` 가 낸다 —
  판별식을 여기서 다시 쓰지 않는다(R3). 같은 이유로 `tests/test_repo_numbers.py`
  가 `AXES` · `truth()` 를 **여기서 받아 간다**. 축의 집은 이 파일 하나다.

★ **정본이 없는 값은 블록으로 만들지 않는다.** §246-2 가 봉인 시점 절 수를
  문서에서 뺐다 — 다음 봉인이 덮어쓰므로 정본이 될 수 없다. 같은 판단을
  둘에 더 했다(아래 `밖` ③④).

── 블록 문법 ──────────────────────────────────────────────────
    <!--gen: 축 축 …-->
    … 생성 줄 …
    <!--/gen-->

★ 마크다운에서 **안 보인다** — `<!--stale-ok-->` · `<!--voice-ok-->` 와 같은
  자리다(MASTER §0-3). 블록 안에서 그 축의 표기를 찾아 **수만** 갈아 넣는다.
  표기 자체는 안 건드리므로 `docnum_check` · `test_repo_numbers` 의 정규식이
  계속 문다. 값을 지우고 자리표를 넣는 판을 쓰지 않은 이유가 그것이다 —
  문서는 사람이 읽는 것이고, 자리표는 읽히지 않는다.

★ 여는 줄이 **제목 밖**에 있다. 제목에 주석을 붙이면
  `test_declaration_sync::test_plan_section1_count_agrees` 의 `\\s*$` 가 깨진다 —
  생성물 문법이 기존 강제자를 깨면 그것은 문법이 틀린 것이다.

── 판정 ──────────────────────────────────────────────────────
    블록 값이 실물과 다르다              실패(`--check`) · 인자 없이 돌면 채운다
    블록이 그 축의 표기를 0곳 찾았다      실패 — 표기가 바뀌었다
    축이 어느 블록에도 안 걸렸다          실패 — **0건은 통과가 아니다**
    정본이 죽었다(대장 0종 · 절 0개)      실패 — 값이 0이면 블록이 통째로 거짓이다

★ 셋째가 `deadcheck` ③ 과 같은 물음이다. 블록을 하나도 못 찾은 초록은
  「깨끗하다」가 아니라 **「안 봤다」**다.

IN    docs/MASTER.md · docs/PLAN.md · README.md · `ledger.load()` · `dms.scan()`
OUT   위 문서 셋(인자 없이 돌 때) · 표준출력
PARAM AXES · DOCS · `--root`
밖    ① **블록 밖의 같은 표기는 안 고친다.** 문서 어디에 적힌 수든 찾는 일은
         `tests/test_repo_numbers.py` 가 한다 — 이 도구는 블록만 연다. 둘은
         일부러 갈랐다: 고치는 자리는 좁아야 하고 보는 자리는 넓어야 한다.
      ② **`docs/DECISIONS.md` 는 안 연다.** append-only 역사라 그때의 수가
         옳다. 회고를 고치면 회고가 아니다.
      ③ **PLAN §13-3 건수는 축이 아니다.** 판별식 정본이
         `tests/test_declaration_sync.py::_ledger_rows` 안에만 있어 여기서
         다시 쓰면 정본이 둘이 된다(R3). 문 하나가 먼저 나야 한다.
      ④ **`retired` 종수는 축이 아니다.** 세려면 대장의 폐기 블록을 직접
         읽어야 하고 그것은 `test_lake.py::test_file_owners_are_resolved_in_one_place`
         래칫이 세는 사본이다(§246 밖 ②). 축 하나를 위해 다른 강제자를
         깨지 않는다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

import dms
import docnum_check
import plan_renumber
import planclose

from firelane import ledger

ROOT = Path(__file__).resolve().parents[1]

#: 블록이 사는 문서. **`DECISIONS` 는 없다**(머리말 `밖` ②).
DOCS = ("docs/MASTER.md", "docs/PLAN.md", "README.md")


class Axis(NamedTuple):
    """한 축 — 표기를 찾는 정규식과 사람이 읽을 뜻."""

    pat: re.Pattern[str]
    what: str


#: 축 이름 → (정규식, 뜻). **정규식은 그 수 하나만** 잡는다.
#:
#: ★ 앵커를 정본 이름(`datasets` · `inherit`)이나 `raw` 로 잡는다. 넓게 잡으면
#:   「소스 21종」 같은 부분집합이 걸리고, 한 번 오탐이 나면 사람이 검사를
#:   끈다(§246-1). `1` 번 그룹이 **수 하나**여야 한다 — 이 도구가 그 그룹의
#:   자리만 갈아 넣는다.
AXES: dict[str, Axis] = {
    "datasets": Axis(re.compile(r"`datasets`\s+([\d,]+)\s*종"),
                     "대장 전체 — `ledger.load()` 의 `datasets` 종수"),
    "sealable": Axis(re.compile(r"소스\s+([\d,]+)\s*종의\s+raw"),
                     "봉인 대상 — 대장에서 `on_demand` 를 뺀 수"),
    "sections": Axis(re.compile(r"절\s+([\d,]+)\s*전수"),
                     "지금 세는 절 — `dms.scan()` 행 수"),
    "inherit": Axis(re.compile(r"물림\(inherit\)\s+([\d,]+)\s*절"),
                    "부모 칸을 물려받는 절 — `dms.inherit_split()` 합"),
    "blank": Axis(re.compile(r"분모\(blank\)\s+([\d,]+)\s*절"),
                  "제 칸도 부모 칸도 없는 절 — `dms.scan()` 의 `blank`"),
    "plan_open": Axis(re.compile(r"^## 1\. 남은 일 — ([\d,]+)행$", re.M),
                      "PLAN §1 표 행 수 — `plan_renumber` 가 세는 것"),
    # ★ 2026-10-25 (Zm39 · DECISIONS §580). PLAN §10-1b 의 **세 수 블록**. 그 절은 「손으로 세지 않는다」고 적어 두고 수를 손으로 적어
    #   세 번 낡았다(§520 · 533 · Zm39). 정본은 `tools/planclose.py::counts()` 하나이고 여기서 다시 세지 않는다 — 앵커는 줄머리 한글 라벨이다.
    "pc_open": Axis(re.compile(r"^열린 (\d+) − 못 닫는 \d+ = \d+", re.M),
                    "PLAN §1 열린 행 — `planclose.counts()` 의 `열린`"),
    "pc_cannot": Axis(re.compile(r"^열린 \d+ − 못 닫는 (\d+) = \d+", re.M),
                      "열린 행 중 물리적으로 못 닫는 행 — `planclose.counts()` 의 `못 닫는`"),
    "pc_gap": Axis(re.compile(r"^열린 \d+ − 못 닫는 \d+ = (\d+)", re.M),
                   "어느 판이든 들어야 하는 행 — 열린 − 못 닫는"),
    "pc_promised": Axis(re.compile(r"^무조건 닫는다\s+(\d+)", re.M),
                        "표식 없이 「닫는다」로 적힌 행 — `planclose.counts()` 의 `무조건 닫는다`"),
    "pc_decl": Axis(re.compile(r"^닫는 수 선언 합\s+(\d+)", re.M),
                    "배치 표 「닫는 수」 칸의 합 — `planclose.counts()` 의 `닫는 수 선언 합`"),
    # ★ 2026-09-25 (§258). 커버리지 래칫. 정본은 `tools/verify.sh` 의 `COV_MIN=`
    #   한 줄이고(`test_coverage_ratchet_has_one_home`), 문서가 그 수를 손으로
    #   들면 올릴 때마다 한쪽만 움직인다 — 2026-09-25 에 실제로 그랬다.
    #   ★ 앵커가 「로 걸려 있」이다. 맨 표기(`` `COV_MIN=28` ``)만 잡으면
    #     DECISIONS 의 **회고 인용**을 같이 잡고, 그러면 역사를 고치게 된다
    #     (다른 축들이 `종의 raw` · 줄머리 `## 1.` 로 앵커를 다는 것과 같다).
    "cov_min": Axis(re.compile(r"`COV_MIN=(\d+)` 로 걸려 있"),
                    "커버리지 래칫 — `tools/verify.sh` 의 `COV_MIN=` 선언"),
    # ★ 2026-09-30 (DECISIONS §319). 판정 네 수. 이것이 **가장 자주 낡는 수**이고
    #   그때마다 사람이 받아적었다 — 09-30 실기에서 그 받아적기 하나 때문에
    #   전수 verify 가 여덟 단계 빨갰다(문서 숫자 · 기획서 · 그림 · 평가지표).
    #
    # ★ 앵커는 **한글 라벨**이다. `clear` 같은 영문 토큰을 앵커로 쓰면
    #   산문 전체가 걸린다. 라벨 뒤에 수가 바로 오는 두 서식(산문 `통행 가능 465`
    #   와 표 칸 `통행 가능 | 465`)만 문다 — 실물을 보고 정했다.
    # ★ `차량 비용 통행 불가 474` 는 **다른 축**이다(폭이 아니라 차량 비용).
    #   **부정 후방탐색**으로 가른다 — 실물 세 줄이 그 꼴이었다.
    # ★ 2026-10-03 (DECISIONS §375). **앵커를 넓히려다 재고 접었다.**
    #   소급 전수 재검증에서 현재형 문서 여덟 자리가 옛 판정 수를 들고 있는 것을
    #   찾았다(`unknown` 399 ×3 · `needs_cv` 226 ×3 · `blocked` 191 중 둘).
    #   그 자리를 기계가 고치게 하려면 앵커에 `` `unknown` `` · `회색` · `주황` ·
    #   `` `blocked` `` 를 더해야 한다. MASTER · PLAN · README 에 돌려 **어긋남 0**
    #   을 확인했다 — 그래서 더할 수 있었다.
    #
    #   **안 더했다.** `tests/test_repo_numbers.py` 가 같은 `AXES` 를
    #   **DECISIONS 까지** 돌리고(그 파일 머리말: 「고치는 자리는 좁아야 하고 보는
    #   자리는 넓어야 한다」), 넓힌 앵커는 그 회고 **열다섯 줄**을 문다 —
    #   `` `blocked` 63 ``(§?) · `` 159 `` · `` 191 ``(×4) · `` 416 `` ·
    #   `` `unknown` 352구간 `` · `회색 399`(×3) 따위. 전부 **그날 그랬다**는
    #   기록이라 고칠 수 없고, 남은 길은 `stale-ok` 열다섯이다.
    #
    #   `tools/suppress.py` 머리말이 그 길을 이미 기각했다 — 「거기 붙일 사유는
    #   전부 같은 한 마디고, 같은 말을 마흔 몇 번 적는 것은 빚을 갚는 것이 아니라
    #   **빚을 예쁘게 적는 것**이다」. 그래서 여덟 자리는 `docnum_check.RETIRED`
    #   (폐기값 + `CONTEXT` 낱말)가 지킨다 — 그쪽은 **문맥을 보므로** 회고를
    #   안 문다. 재고 고른 길이고, 그 사유를 여기 남긴다.
    "v_clear": Axis(re.compile(r"통행 가능`?\s*\|?\s*(\d[\d,]*)"),
                    "판정 `clear` 구간 수 — 산출물 `segments.geojson`"),
    "v_needs_cv": Axis(re.compile(r"판정 보류`?\s*\|?\s*(\d[\d,]*)"),
                       "판정 `needs_cv` 구간 수"),
    "v_blocked": Axis(re.compile(r"(?<!차량 비용 )통행 불가`?\s*\|?\s*(\d[\d,]*)"),
                      "판정 `blocked` 구간 수"),
    "v_unknown": Axis(re.compile(r"영상판정 불가`?\s*\|?\s*(\d[\d,]*)"),
                      "판정 `unknown` 구간 수"),
    # ★ 2026-10-11 (DECISIONS §464 · PLAN #167 닫힘). **발행물에서 유도되는
    #   다섯.** 2026-10-11 재발행에서 손으로 고친 열세 자리 중 다섯이 어느 축에도
    #   없었다 — 판정 네 수와 회색 사유는 울었고 이 다섯은 조용했다. 같은 문단에서
    #   틀린 수와 맞는 수가 섞여 있었고, **조용한 것이 맞다는 뜻이 아니다.**
    #
    # ★ 앵커를 좁게 잡았다. 실측으로 확인한 것 —
    #     `CCTV 유효범위 안` + 공백 + 수   → §3-7 한 곳. 「유효범위 안이 **126**」
    #       (§7-2 · 폭 3~7m 대역)은 **조사가 붙어** 안 걸린다
    #     `골목의 N%` + `는`/`에`          → 제목 · ★ 줄 · §15-1. 「골목의 48.8%(625구간)」
    #       은 뒤에 `(` 가 와서 안 걸린다 — 그쪽은 **다른 축**(도면만으로 판정 불가)이다
    #     `전체 연장의 N%`                 → §3-7 한 곳. DECISIONS 의 E-3 회고는
    #       「연장 17,168m/58,309m (29.4%)」 꼴이라 이 앵커에 안 걸린다
    # ★ 백분율은 **소수 한 자리**로 쓴다. 정수로 반올림하면 64.8 과 65.4 가 같아지고,
    #   그 둘은 「골목의 65%」라는 한 문장에서 다른 사실이다.
    "cctv_in": Axis(re.compile(r"CCTV 유효범위 안\s+\**([\d,]+)"),
                    "CCTV 유효범위 안 구간 수 — 발행물의 `cv_feasible`"),
    "cctv_in_pct": Axis(re.compile(r"CCTV 유효범위 안[^\n]*\((\d+\.\d|\d+)%\)"),
                        "그 수가 구간 수에서 차지하는 몫 (%)"),
    "cctv_out_pct": Axis(re.compile(r"골목의\s*(\d+\.\d|\d+)%(?=[에는])"),
                         "CCTV 유효범위 **밖** 몫 (%) — 100 − 안"),
    "v_unknown_m": Axis(re.compile(r"영상판정 불가[^\n]*?·\s*([\d,]+)m"),
                        "판정 `unknown` 구간의 연장 (m)"),
    "v_unknown_m_pct": Axis(re.compile(r"전체 연장의\s*(\d+\.\d|\d+)%"),
                            "그 연장이 총연장에서 차지하는 몫 (%)"),
}

#: 백분율 축. **소수 한 자리로 쓰고 소수 한 자리로 읽는다.**
#: ★ 이 집합이 곧 「어느 축이 실수인가」의 정본이다 — `render` 와 `claims` 가
#:   같은 것을 본다. 양쪽에 따로 적으면 쓰는 꼴과 읽는 꼴이 갈린다.
FLOAT_AXES = frozenset({"cctv_in_pct", "cctv_out_pct", "v_unknown_m_pct"})

OPEN = re.compile(r"^<!--gen:\s*([\w ]+?)\s*-->$")
CLOSE = re.compile(r"^<!--/gen-->$")


# ── 실물 ────────────────────────────────────────────────────────
def _cov_min() -> int:
    """`tools/verify.sh` 의 `COV_MIN=` 한 줄. **정본은 거기다.**

    ★ 정규식을 여기서 또 쓰는 것이 R3 처럼 보이지만 아니다 —
      `tests/test_verify_citations.py` 는 「집이 하나인가」를 묻고 이 함수는
      「그 집의 값이 얼마인가」를 묻는다. 같은 줄을 다른 질문으로 읽는다.
    """
    m = re.search(r"^COV_MIN=(\d+)\s*$",
                  (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8"), re.M)
    return int(m.group(1)) if m else 0


def truth() -> dict[str, float]:
    """축마다의 **실물**. 문서를 한 줄도 안 읽는다 — PLAN §1 표만 예외다.

    ★ 대장은 `ledger.load()` 로 읽는다. yaml 로 직접 열면
      `test_lake.py::test_ledger_is_loaded_through_one_door` 래칫이 오른다
      (§246 이 이 실수를 실제로 두 번 했다). 강제자를 만드는 배치가 다른
      강제자를 깨는 것이 이 저장소가 반복한 형태다.

    ★ PLAN §1 행 수의 정본은 **그 표 자신**이다(`test_declaration_sync` 가
      「정본은 표다」라고 적는다). 세는 판별식은 `plan_renumber` 가 이미
      들고 있으므로 여기서 다시 쓰지 않는다 — 범위가 갈리면 도구와 검사가
      다른 것을 세고, 그러면 고쳐도 계속 운다(그 도구 `_span` 주석).
    """
    ds = ledger.load()["datasets"]
    rows = dms.scan()["rows"]
    said, mute = dms.inherit_split({"rows": rows})
    plan = (ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    return {
        "datasets": len(ds),
        "sealable": sum(1 for v in ds.values() if not (v or {}).get("on_demand")),
        "sections": len(rows),
        "inherit": len(said) + len(mute),
        "blank": sum(1 for r in rows if r["state"] == "blank"),
        # ★ 밑줄 이름을 그대로 부른다. 같은 범위를 세는 판별식이 이미 거기
        #   있고, 여기서 다시 쓰면 도구와 검사가 다른 것을 센다(R3).
        "plan_open": len(plan_renumber._rows(plan)),
        # ★ Zm39. 세 수 블록의 다섯 — 세는 집은 `planclose.counts()` 하나다(R3).
        **{k: v for k, v in zip(("pc_open", "pc_cannot", "pc_gap", "pc_promised", "pc_decl"),
                                (lambda c: (c["열린"], c["못 닫는"], c["열린"] - c["못 닫는"], c["무조건 닫는다"], c["닫는 수 선언 합"]))(planclose.counts()),
                                strict=True)},
        "cov_min": _cov_min(),
        # ★ `docnum_check` 를 부른다. 같은 수를 여기서 또 세면 두 집이 되고,
        #   판정이 움직이는 날 한쪽만 움직인다(2족 · §319).
        **{f"v_{k}": v for k, v in docnum_check.verdicts().items() if k != "n"},
        # ★ 2026-10-11 (§464). 발행물에서 **유도되는** 다섯. 같은 사유로 여기서
        #   다시 세지 않는다 — 집은 `docnum_check.shape()` 하나다.
        **docnum_check.shape(),
    }


def alive(want: dict[str, float]) -> list[str]:
    """정본이 살아 있는가. 비면 산다.

    ★ 값이 0이면 블록이 통째로 거짓이 되고, 그 거짓은 **조용하다** — 도구가
      0을 채우고 검사가 0을 통과시킨다. 그래서 여기서 죽인다.
      `tests/test_repo_numbers.py` 가 같은 함수를 부른다(정본은 하나다).
    """
    bad = []
    # ★ 2026-09-25. 축을 더하면서 이 함수가 `KeyError` 로 죽었다. **없는 축은
    #   에러가 아니라 결함이다** — 죽으면 「왜 우는가」가 안 보이고, 이 함수의
    #   일은 우는 것이다. 빠진 축을 먼저 낸다.
    if missing := [a for a in AXES if a not in want]:
        bad.append(f"축 {missing} 의 실물이 없다 — `truth()` 가 그 축을 안 센다")
    want = {a: want.get(a, 0) for a in AXES}
    if want["datasets"] <= 50:
        bad.append(f"대장 {want['datasets']}종 — 대장을 못 읽었다")
    if want["sections"] <= 500:
        bad.append(f"절 {want['sections']} — `dms.scan()` 이 죽었다")
    if want["plan_open"] <= 0:
        bad.append("PLAN §1 표 행이 0 — 표를 못 찾았다")
    if want["cov_min"] <= 0:
        bad.append("`COV_MIN` 을 못 읽었다 — `tools/verify.sh` 의 선언 한 줄이 사라졌다")
    # ★ 판정 네 수의 합이 구간 수여야 한다. 하나라도 0 이면 블록이 통째로
    #   거짓이 되고 그 거짓은 **조용하다** — 도구가 0 을 채우고 검사가 통과시킨다.
    # ★ 2026-10-11 (§464). 발행물에서 유도되는 **셈 둘**도 같은 사유로 든다.
    #   0 이면 「유효범위 안 0구간」 · 「회색 연장 0m」이 되고 그 둘은 이 저장소의
    #   어느 발행본에도 없는 값이다. 백분율은 안 든다 — 참으로 0 이 될 수 있는
    #   수에 0 문턱을 걸면 그 문이 거짓을 말하게 된다.
    for a in ("v_clear", "v_needs_cv", "v_blocked", "v_unknown",
              "cctv_in", "v_unknown_m"):
        if want.get(a, 0) <= 0:
            bad.append(f"`{a}` 가 0 — 산출물을 못 읽었거나 판정 어휘가 바뀌었다")
    if want["sealable"] > want["datasets"]:
        bad.append("봉인 대상이 대장보다 많다")
    if want["sealable"] >= want["datasets"]:
        bad.append("`on_demand` 소스가 0이다 — 970MB 인 `jijeok` 이 빠져 있어야 한다.\n"
                   "  정말 0이 됐으면 이 판별식을 고쳐라. 지금은 축이 낡았다는 신호다")
    return bad


def render(v: float, axis: str | None = None) -> str:
    """문서에 적히는 꼴. 천 단위 쉼표는 문서 관례다(`절 1,036 전수`).

    ★ 2026-10-11 (§464-3). 백분율 축은 **소수 한 자리**다. 정수로 쓰면
      64.8 과 65.4 가 같은 글자가 되고, 그 둘은 한 문장에서 다른 사실이다.
      어느 축이 실수인가의 정본은 `FLOAT_AXES` 하나다.
    """
    return f"{v:,.1f}" if axis in FLOAT_AXES else f"{int(v):,}"


def claims(axis: str, text: str) -> list[float]:
    """`axis` 표기가 이 문자열에서 말하는 수들. 시험과 이 도구가 같은 문을 쓴다.

    ★ 백분율 축은 실수로 돌려준다 — 정수로 깎으면 「29.5 라 적혀 있는데
      29 로 읽어 통과」가 된다. 그것이 이 축이 생긴 사유의 반대다.
    """
    got = [m.replace(",", "") for m in AXES[axis].pat.findall(text)]
    return [float(g) for g in got] if axis in FLOAT_AXES else [int(g) for g in got]


# ── 블록 ────────────────────────────────────────────────────────
class Result(NamedTuple):
    """채운 본문 · 값 어긋남 · 구조 결함 · 축별 치환 건수."""

    texts: dict[str, str]
    drift: list[str]
    broken: list[str]
    seen: dict[str, int]


def _swap(pat: re.Pattern[str], line: str, want: str) -> tuple[str, int, list[str]]:
    """그 줄에서 `pat` 의 1번 그룹 자리만 `want` 로 갈아 넣는다.

    ★ **표기를 안 건드린다.** 앵커까지 새로 쓰면 이 도구가 문서의 문장을
      쓰게 되고, 그러면 사람이 쓴 산문이 배치마다 되돌려진다.
    """
    out: list[str] = []
    pos, hits, stale = 0, 0, []
    for m in pat.finditer(line):
        hits += 1
        if m.group(1) != want:
            stale.append(m.group(1))
        out.append(line[pos:m.start(1)])
        out.append(want)
        pos = m.end(1)
    out.append(line[pos:])
    return "".join(out), hits, stale


def apply_all(texts: dict[str, str], want: dict[str, float]) -> Result:
    """블록을 채운다. **순수 함수**다 — 시험이 합성 문서로 직접 부른다."""
    out: dict[str, str] = {}
    drift: list[str] = []
    broken: list[str] = []
    seen = dict.fromkeys(AXES, 0)
    for rel, text in texts.items():
        lines = text.split("\n")
        new = list(lines)
        i = 0
        while i < len(lines):
            mo = OPEN.match(lines[i])
            if mo is None:
                i += 1
                continue
            axes = mo.group(1).split()
            j = i + 1
            while j < len(lines) and CLOSE.match(lines[j]) is None:
                j += 1
            if j >= len(lines):
                broken.append(f"{rel}:{i + 1}  `<!--gen:-->` 가 안 닫혔다 "
                              "— `<!--/gen-->` 를 붙여라")
                break
            for a in axes:
                if a not in AXES:
                    broken.append(f"{rel}:{i + 1}  모르는 축 `{a}` — `AXES` 에 없다")
                    continue
                v = render(want[a], a)
                hits = 0
                for k in range(i + 1, j):
                    new[k], n, stale = _swap(AXES[a].pat, new[k], v)
                    hits += n
                    drift += [f"{rel}:{k + 1}  `{a}` {g} → 실물 {v}" for g in stale]
                if hits == 0:
                    broken.append(
                        f"{rel}:{i + 1}  블록이 `{a}` 표기를 0곳 찾았다 — 표기가"
                        f" 바뀌었다({AXES[a].what}).\n"
                        "    **0건은 통과가 아니다** — 블록을 지우거나 표기를 맞춰라")
                seen[a] += hits
            i = j + 1
        out[rel] = "\n".join(new)
    dead = sorted(a for a, n in seen.items() if n == 0)
    if dead:
        broken.append(
            f"이 축에 생성 블록이 **한 곳도 없다**: {dead}\n"
            "    잡힌 곳: " + " · ".join(f"{a} {n}" for a, n in sorted(seen.items())) + "\n"
            "    축을 내리거나 블록을 세워라. **0건은 통과가 아니다**(deadcheck ③)")
    return Result(out, drift, broken, seen)


def read_docs(root: Path = ROOT) -> dict[str, str]:
    return {rel: (root / rel).read_text(encoding="utf-8") for rel in DOCS}


# ── 출력 ────────────────────────────────────────────────────────
def _say(res: Result) -> None:
    for b in res.broken:
        print(f"    ✗ {b}")
    for d in res.drift:
        print(f"    ✗ {d}")


def selftest() -> int:
    """★ 판별식이 살아 있나. **합성 문서로만 민다** — 실물을 안 건드린다.

    ★ 2026-10-10 (DECISIONS §445-2 와 같은 자리). 이 도구가 **과녁에 새로
      들어왔다** — `#166` 이 지문 범위를 넓히며 「선언을 옆집에서 함수 안으로
      끌어오는 꼴」을 보게 됐고, 이 도구가 바로 그 꼴이었다. 그런데 자기검사가
      없어 **흔들어도 못 재는 과녁**(`UNCATCHABLE`)이 됐다. 재는 자리가 없는
      강제자는 §445 가 내내 적은 그 병이라 여기서 끊는다.

    밖    **실물 수가 옳은가는 안 본다** — 그것은 `truth()` 와 `alive()` 가
          실물에서 들고 `tests/test_repo_numbers.py` 가 같이 묻는다.
    """
    bad: list[str] = []
    doc = "<!--gen: plan_open -->\n## 1. 남은 일 — 3행\n<!--/gen-->\n"
    want = {a: 1 for a in AXES} | {"plan_open": 7}

    # ★ 정상 입력 — 블록을 채운다. **구조 결함은 증분으로 본다** — 합성 문서는
    #   축 하나만 들므로 「이 축에 블록이 한 곳도 없다」가 늘 따라온다. 그 바탕을
    #   빼고 **늘어난 것**만 결함으로 센다.
    res = apply_all({"a.md": doc}, want)
    base = len(res.broken)
    if "## 1. 남은 일 — 7행" not in res.texts["a.md"]:
        bad.append("블록을 안 채운다")
    if res.seen.get("plan_open") != 1:
        bad.append("채운 건수를 안 센다")
    # ★ 합성 결함 ① 낡은 값이면 **운다**
    if not res.drift:
        bad.append("낡은 값을 안 운다 — 3행이 7행으로 바뀌었는데 조용하다")
    # ★ 합성 결함 ② 이미 맞으면 **안 운다**(그래야 「고칠 것이 없다」가 참이다)
    if apply_all({"a.md": res.texts["a.md"]}, want).drift:
        bad.append("이미 맞는데 운다 — 매 배치 문서가 더러워진다")
    # ★ 합성 결함 ③ 안 닫은 블록은 **구조 결함**이다
    if len(apply_all({"a.md": "<!--gen: plan_open -->\n## 1. 남은 일 — 3행\n"},
                     want).broken) <= base:
        bad.append("안 닫은 블록을 안 운다 — 그 뒤 문서 전체가 블록 안이 된다")
    # ★ 합성 결함 ④ 모르는 축 이름
    if len(apply_all({"a.md": doc + "<!--gen: 없는축 -->\n<!--/gen-->\n"},
                     want).broken) <= base:
        bad.append("없는 축 이름을 안 운다")
    # ★ 읽는 쪽 — 시험과 같은 문을 쓴다
    if claims("plan_open", "## 1. 남은 일 — 1,234행") != [1234]:
        bad.append("천 단위 쉼표를 못 읽는다")
    if render(1234) != "1,234":
        bad.append("천 단위 쉼표를 안 적는다")
    # ★ 2026-10-11 (§464-3). **백분율 축은 소수 한 자리로 쓰고 소수 한 자리로
    #   읽는다.** 한쪽만 고치면 쓰는 꼴과 읽는 꼴이 갈려 매 배치 되돌려진다.
    pct = next(iter(FLOAT_AXES))
    if render(64.8, pct) != "64.8":
        bad.append(f"백분율을 정수로 적는다 — {render(64.8, pct)}")
    if render(64.0, pct) != "64.0":
        bad.append("소수 자리가 0 이면 떼 버린다 — 64 와 64.0 은 다른 주장이다")
    if claims("cctv_out_pct", "골목의 64.8%는") != [64.8]:
        bad.append("백분율을 실수로 안 읽는다 — 29.5 를 29 로 읽으면 통과한다")
    if claims("cctv_out_pct", "골목의 65%는") != [65.0]:
        bad.append("소수점 없는 백분율을 못 읽는다")
    # ★ 울타리 — **조사가 붙거나 괄호가 오면 안 문다.** 실물에 그런 자리가 있다
    #   (「유효범위 안이 **126**」은 §7-2 의 다른 축 · 「골목의 48.8%(625구간)」는
    #   도면만으로 판정 불가). 한 번 오탐이 나면 사람이 검사를 끈다.
    for axis, prose in (("cctv_in", "그중 유효범위 안이 **126**이다"),
                        ("cctv_out_pct", "골목의 48.8%(625구간)는 도면만으로"),
                        ("v_unknown_m", "E-3 영상판정 불가 399/1,281 · 연장 17,168m/58,309m"),
                        ("v_unknown_m_pct", "연장 17,168m/58,309m (29.4%)")):
        if claims(axis, prose):
            bad.append(f"{axis} 가 다른 축을 문다 — {prose!r} → {claims(axis, prose)}")
    # ★ 정본이 살아 있나 — **양방향**
    ok = {a: 9_999 for a in AXES} | {"datasets": 80, "sealable": 79}
    if alive(ok):
        bad.append(f"멀쩡한 축에 운다 — {alive(ok)}")
    if not alive({a: 0 for a in AXES}):
        bad.append("전부 0 인데 안 운다 — 조용한 거짓이 그대로 문서에 들어간다")
    # ★ 경계를 못 박는다. 문이 `<= 0` 인지 `<= 1` 인지를 **1 로** 가른다 —
    #   안 박으면 그 자리를 흔들어도 안 죽고, 경계가 조용히 한 칸 올라간다.
    one = ok | dict.fromkeys(
        ("plan_open", "cov_min", "v_clear", "v_needs_cv", "v_blocked", "v_unknown",
         "cctv_in", "v_unknown_m"), 1)
    if alive(one):
        bad.append(f"1 인데 운다 — 경계가 0 이 아니라 1 에 걸렸다: {alive(one)}")
    # ★ 2026-10-11 (§464). **바닥이 있는 축의 경계도 못 박는다.** `datasets` 50 ·
    #   `sections` 500 두 자리는 자기검사가 「0」과 「충분히 큼」만 봤고, 그래서
    #   그 수를 한 칸 미는 돌연변이가 살아 있었다(§445-9 가 같은 자리를 0/1 에서
    #   막았다). 문턱은 **그 수에서 울고 그 수+1 에서 안 우는가**로 묶는다.
    #   ★ `datasets` 를 내릴 때 `sealable` 도 같이 내린다 — 안 내리면 「봉인
    #     대상이 대장보다 많다」가 먼저 울어 이 문이 무엇을 봤는지 못 가른다.
    for axis, floor in (("datasets", 50), ("sections", 500)):
        pin = {"sealable": floor - 1} if axis == "datasets" else {}
        if not alive(ok | {axis: floor} | pin):
            bad.append(f"{axis} {floor} 인데 안 운다 — 문턱이 위로 밀렸다")
        if alive(ok | {axis: floor + 1} | pin):
            bad.append(f"{axis} {floor + 1} 인데 운다 — 문턱이 아래로 밀렸다")
    if not alive({}):
        bad.append("축이 통째로 없는데 안 운다")

    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 — 채움 · 낡음 · 멱등 · 구조 · 읽기(백분율 포함) · 울타리 · 정본 아홉")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="문서 생성 블록 ↔ 실물")
    ap.add_argument("--check", action="store_true", help="대조만 — 고치지 않는다")
    ap.add_argument("--selftest", action="store_true", help="★ 판별식이 살아 있나")
    ap.add_argument("--list", action="store_true", help="축 · 실물 값 · 블록 수")
    # ★ **문서를 어디서 읽나만 바꾼다.** 실물(대장 · `dms.scan()`)은 언제나 이
    #   저장소다 — 그래서 복사한 트리에 틀린 값을 심어 「이 도구가 무는가」를
    #   물을 수 있다(`tests/test_docgen.py`). 추적 파일을 흔들지 않고 묻는
    #   길이 없으면 그 물음은 결국 안 묻게 된다.
    ap.add_argument("--root", type=Path, default=ROOT,
                    help="문서를 읽고 쓸 트리 (기본: 이 저장소)")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    want = truth()
    dead = alive(want)
    if dead:
        print("✗ 정본이 죽었다 — 블록을 채우면 거짓이 박힌다")
        for d in dead:
            print(f"    {d}")
        return 1

    res = apply_all(read_docs(a.root), want)

    if a.list:
        print(f"{'축':10} {'실물':>8}  {'블록':>4}  뜻")
        for name, ax in AXES.items():
            print(f"{name:10} {render(want[name], name):>8}  {res.seen[name]:>4}  {ax.what}")
        _say(res)
        return 0

    if a.check:
        if res.broken or res.drift:
            print(f"✗ 생성 블록 {len(res.broken) + len(res.drift)}건")
            _say(res)
            print("  ★ 손으로 고치지 마라 — `uv run python tools/docgen.py` 가 채운다.")
            return 1
        print(f"✓ 생성 블록 {sum(res.seen.values())}곳이 실물과 같다 · "
              + " · ".join(f"{k} {render(v, k)}" for k, v in want.items()))
        return 0

    for rel, text in res.texts.items():
        p = a.root / rel
        if p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8")
            print(f"  채움 {rel}")
    if res.drift:
        print(f"✓ {len(res.drift)}곳을 실물로 채웠다")
        for d in res.drift:
            print(f"    {d}")
    else:
        print("✓ 고칠 것이 없다 — 블록이 이미 실물과 같다")
    if res.broken:
        print(f"✗ 구조 결함 {len(res.broken)}건 — 값만으로는 못 고친다")
        for b in res.broken:
            print(f"    {b}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
