#!/usr/bin/env python3
"""
docnum_check.py — 문서에 적힌 숫자가 산출물과 같은지 본다.

    uv run python tools/docnum_check.py

왜 필요한가
    2026-08-14 재실행으로 segments 1087 → 1102 가 됐다. `EXPECT` 와 MASTER §2
    표는 갱신됐으나 README · MASTER 산문 · PLAN 이 나흘간 옛 숫자를 말했다.
    계약 테스트 14종은 필드명과 `verdict` 어휘를 지키지만 숫자는 안 본다.
    사람이 문서를 고치는 것에 의존하면 같은 일이 반복된다.

★ 2026-08-18 확장 — 왜 이 도구가 1,087 을 놓쳤나
    이 도구는 "맞는 숫자가 **있는가**"만 봤다. 문자열 포함 검사라 문서에
    1101 과 1087 이 **둘 다** 있으면 통과한다. §2 표만 갱신하고 나머지를
    안 고쳐도 초록불이었다. 실제로 그랬다 — MASTER 에 1,087 이 10곳,
    1,093 이 1곳, 396 이 3곳, PLAN 에 1,087 1곳 · 396 2곳 남아 있었다.

    그래서 검사를 뒤집어 하나 더 붙인다 — **없어야 할 숫자가 있는가**(RETIRED).
    있는지 보는 검사는 추가 누락에 강하고, 없는지 보는 검사는 삭제 누락에
    강하다. 둘 다 있어야 한다.

    필드표 대조도 붙인다. MASTER §11 이 `n_sample` 등 7개를 웹 필드로
    적어놨는데 `publish_web.py` 는 내보내지 않는다. UI 담당이 그 표를 보고
    코드를 짜면 undefined 가 나온다. 숫자만큼 자주 어긋난다.

무엇을 보나
    1. PRESENT   산출물에서 센 값이 문서에 문자열로 존재하는가
    2. RETIRED   폐기된 옛 값이 현재형 서술에 남아 있는가              ← 신규
    3. FIELDS    MASTER §11 필드표 == web/data/segments.geojson 실제 키  ← 신규
    4. EXPECT    pipeline.EXPECT 자기모순

무엇을 안 보나
    §13~§16(데이터 이력 · 패치 · 기획서 반영 · 결정 사유)의 옛 숫자.
    작성 시점 기록이므로 옳다. `HIST` 로 줄 범위를 잘라낸다.

    현재형 영역 안에서도 옛 숫자를 **의도적으로** 인용하는 곳이 있다
    (§2 의 "1093 · 1091 은 무효다" 블록이 그렇다). 그 줄 끝에
    `<!--stale-ok-->` 를 붙인다. 마커를 다는 일 자체가 "이 옛 숫자는
    실수가 아니다"를 문서에 남기는 것이라, 주석이 곧 기록이 된다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ★ 선언 표 둘은 옆집에 산다 — 값만 있는 것은 값만 있는 파일에(§449-2).
from docnumtable import CONTEXT, RETIRED

from firelane.cli import no_args

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data/processed/segments.geojson"
WEB = ROOT / "web/data/segments.geojson"
#: 설명문의 **정본**. 산출물이 들고 다닌다(MASTER §11 · DECISIONS §449).
SCHEMA_WEB = WEB.parent / "segments.schema.json"
NFA = ROOT / "data/processed/nfa_compare.json"

ALLOW = "<!--stale-ok-->"

# ── 이력 절 ────────────────────────────────────────────────────
# 이 범위의 옛 숫자는 옳다. RETIRED 검사에서 뺀다.
# (시작 헤딩, 끝 헤딩). 끝 헤딩 줄은 포함하지 않는다.
HIST: dict[str, list[tuple[str, str]]] = {
    # ★ 2026-08-18 문서 형식 정리로 절 제목이 h1 → h2 가 됐다.
    #   앵커가 깨지면 이력 절이 검사 대상에 들어가 옛 숫자가 무더기로 뜬다.
    #   startswith 라 "## 13. " 처럼 뒤에 공백까지 넣어야 "## 13-1" 을 안 먹는다.
    # ★ 2026-08-25. MASTER 에서 이력 절을 걷어냈다(DECISIONS §64).
    #   예외 구간이 없어야 문서 전 구간이 대조 대상이 된다.
    "docs/MASTER.md": [],
    "docs/PLAN.md": [],
    "README.md": [],
}

# ── 폐기된 값 ──────────────────────────────────────────────────
# ★ 산출값이 바뀌면 옛 값을 여기 한 줄 추가한다. 이 도구의 유지보수는
#   그것이 전부다. 추가를 잊으면 다음 사람이 옛 숫자를 그대로 믿는다.
def retired_clashes(cur: dict[str, int], retired: dict[str, list[str]]) -> list[str]:
    """폐기목록이 **지금 값**을 폐기라고 적고 있는가. 같은 축 · 다른 축 둘 다.

    ★ 2026-09-30 (DECISIONS §330). 종전 검사는 **같은 축 안에서만** 봤다.
      그래서 `clear` 의 폐기값 `400` 이 측정 배치로 `unknown` 의 **현재값**이
      된 순간을 못 봤고, 판정 넷을 한 줄에 적는 `README` 가 그 줄 때문에
      빨개졌다 — **맞는 문서가 빨간불이 되는** 병이고, 이 파일이 2026-08-24 에
      같은 병을 같은 축 안에서 겪고 주석으로 적어 둔 그것이다.
      §320 의 소화전 157 도 축을 가로질렀다. **두 번 났으면 축 사이를 본다.**

    ★ 순수 함수다 — 문서도 산출물도 안 읽는다. 그래서 `--selftest` 가 부른다.
    """
    out: list[str] = []
    live = {str(v): k for k, v in cur.items()}
    for label, old in retired.items():
        if label in cur and str(cur[label]) in old:
            out.append(f"RETIRED[{label!r}] 에 현재값 {cur[label]} 이 있다 — 목록을 고쳐라")
            continue
        for x in sorted(set(old) & set(live)):
            out.append(f"RETIRED[{label!r}] 의 {x} 가 **다른 축의 현재값**이다 "
                       f"({live[x]}) — 그 줄을 쓴 문서가 빨개진다")
    return out


def verdicts() -> dict[str, int]:
    """판정 네 수 + 구간 수. **산출물에서 직접 센다.**

    ★ 2026-09-30 (§319). `tools/docgen.py` 가 이 함수를 부른다 — 같은 수를
      거기서 또 세면 두 집이 되고, 판정이 움직이는 날 한쪽만 움직인다(2족).
      좁게 떼어 둔 이유는 `counts()` 가 대장·실물까지 읽어 **레이크 없는
      기계에서 죽기** 때문이다. 문서 블록을 채우는 데 레이크는 필요 없다.
    """
    import verdict_tally
    t = verdict_tally.tally(SEG)
    # ★ 모르는 어휘가 있으면 그 도구가 `★` 칸으로 낸다. 여기서 버리면
    #   **네 수의 합이 구간 수와 다른 채로** 문서에 실린다.
    if any(k.startswith("★") for k in t):
        raise SystemExit(f"! 발행 어휘 밖의 판정이 있다 — {t}")
    return t


#: 「사유는 **다섯** 가지」 — 수사를 한글로 적는 자리. 열까지만 든다.
#: ★ 2026-10-09 (§444 · #142). 이 한 낱말이 2026-10-09 에 거짓이 됐다 —
#:   `ledger_disputes` 가 다섯째 사유로 섰는데 문장은 「네 가지」였다. 수는
#:   `docnum_check` 가 보고 **낱말은 아무도 안 봤다.** 수사도 수다.
NUMWORD = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯",
           6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열"}
#: 그 문장의 닻. 수사 자리만 빼고 그대로 문다.
GRAY_KINDS = re.compile(r"GRAY\s*[\d,]+구간의 사유는\s*(\S+?)\s*가지")


def gray_kind_faults(txt: str, n: int) -> list[str]:
    """회색 사유의 **가짓수 낱말**이 실물과 같은가. 순수 함수다.

    ★ 닻이 없으면 운다. 문장을 지우면 이 축이 **조용히** 사라지고, 그러면
      다음 사유가 생겨도 아무 데서도 안 운다(1족 · 무음 통과).
    """
    want = NUMWORD.get(n, str(n))
    got = GRAY_KINDS.findall(txt)
    if not got:
        return ["회색 사유 가짓수 — 그 문장을 못 찾았다. 닻이 낡았거나 문장이 지워졌다 "
                "(`GRAY N구간의 사유는 … 가지`)"]
    return [f"회색 사유 가짓수 `{g}` → **{want}** (실물 {n}종)"
            for g in got if g != want]


#: 판정 지문. **회색 사유의 정본은 여기다.**
#: ★ 2026-10-09 (DECISIONS §444-5). 처음 판은 `SEG`(`data/processed/segments.geojson`)
#:   를 세었다. 그 파일은 **재생성물인데 우연히 추적돼 있고** 마지막 커밋이
#:   §308~§320 판이다 — 즉 CI 가 읽는 것은 **두 판 묵은 사진**이고, 그 사이
#:   §436 이 다섯째 사유를 만들었다. 수가 우연히 안 바뀐 축들은 그 사실을
#:   숨겼고, 사유별로 세는 순간 드러났다.
#: ★ `golden` 은 **측정 배치마다 다시 잠긴다**(`golden.py lock` · 재잠금 사슬).
#:   판정 수의 정본이 거기라는 것은 MASTER §0-3 이 든다 — 같은 자리에서 읽는다.
GOLDEN_FP = ROOT / "data" / "golden" / "segments.fingerprint.json"


def _reasons() -> dict[str, int]:
    """회색 사유 → 구간 수. **판정 지문에서 읽는다.**

    ★ 지문이 없거나 그 칸이 없으면 **빈 표가 아니라 죽는다** — 빈 표를 내면
      「사유가 0종」이 되고 기획서의 「다섯 가지」가 조용히 통과한다(1족).
    """
    if not GOLDEN_FP.is_file():
        raise SystemExit(f"★ {GOLDEN_FP} 가 없다 — 판정 지문을 먼저 잠가라"
                         " (uv run python tools/golden.py lock)")
    ur = json.loads(GOLDEN_FP.read_text(encoding="utf-8")).get("L1", {}).get(
        "unknown_reason")
    if not ur:
        raise SystemExit("★ 판정 지문에 `unknown_reason` 칸이 없다 —"
                         " 옛 판 지문이다. 다시 잠가라")
    return {str(k): int(v) for k, v in ur.items()}


def counts() -> dict[str, int]:
    P = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    return {
        **verdicts(),
        "in_emd": sum(1 for p in P if p["in_emd"]),
        # ★ 2026-09-16. `(d or 9e9)` 는 거리 **0.0** 을 결손으로 읽었다 — 카메라 바로 옆 2구간이
        #   유효범위 밖으로 세어져 451 을 449 로 냈다(DECISIONS §170-5). 결손은 None 뿐이다.
        "cctv_in": sum(1 for p in P if p["cctv_dist_m"] is not None and p["cctv_dist_m"] <= 25),
        "nfa": sum(1 for p in P if p.get("nfa_designated")),
        # ★ 2026-10-09 (DECISIONS §444 · PLAN #142). **회색의 사유별 수.**
        #   종전에 이 다섯을 보던 것은 `docx_check` 의 ⑤ 정방향(= `docx_fix`
        #   규칙)뿐이었고, 그것은 `docs/proposal.docx` 를 읽었다 — 정본이 md 로
        #   옮겨진 뒤로 **정본의 그 문장은 아무도 안 봤다.** 2026-10-09 에
        #   `ledger_disputes` 가 다섯째 사유로 서면서 그 문장이 「네 가지」로
        #   거짓이 됐고, 그것을 운 것은 사본을 보던 검사였다.
        #   ★ 사유 어휘의 정본은 `segments.py` 다. 여기서 이름을 안 적고
        #     **실물에 있는 것을 센다** — 새 사유가 생기면 칸이 저절로 생긴다.
        **{f"ur_{k}": v for k, v in _reasons().items()},
        # 채택 소스가 구간의 절반도 못 덮은 것. D-25 실측 1순위이고
        # MASTER §7 과 PLAN §1 #65 가 같은 숫자를 말해야 한다.
        "cov_thin": sum(1 for p in P
                        if p.get("width_cov") is not None and p["width_cov"] < 0.5),
        **ledger_counts(),
    }


def ledger_counts() -> dict[str, int]:
    """대장·계층·실물에서 센 값.

    ★ 2026-08-31 신설. 종전에는 `segments.geojson` 하나만 셌다.
      `golden` 이 같은 파일만 읽는 것과 같은 사각지대이고, 그래서
      **대장과 문서의 숫자는 아무도 안 봤다.**

      그날 손으로 센 숫자가 여섯 개 틀렸다 — 대장 `what` 의 소화전
      431+157=588(실물은 418+171=589. 덧셈까지 안 맞았다), PLAN #23 의
      "8종"(실제 22종), #41 의 "20여건"(실제 54건), 핸드오프의 룰셋 승인
      수와 PR 상태, norm 이관 건수. **코드가 센 숫자는 한 번도 안 틀렸다.**

      ★ 소화전은 **실물 CSV 에서 센다.** 대장도 MASTER 도 사람이 쓰지만
        집계표는 아니다. 사람이 안 쓰는 유일한 출처가 정본이어야 한다.
    """
    import csv
    import io

    import yaml

    from firelane import paths, prep

    y = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    out = {
        "ds": len(y.get("datasets") or {}),
        "retired": len(y.get("retired") or {}),
        "migrated": len(prep.migrated()),
    }
    # ★ 마운트가 끊기면 `rglob` 이 예외를 던진다(DECISIONS §104).
    #   소화전 수치는 raw 에서만 나오므로 대장 종수만 돌려준다.
    if not paths.alive(paths.RAW):
        return out
    hits = sorted(paths.RAW.rglob("*hydrant_summary*"))
    if hits:
        rows = list(csv.reader(io.StringIO(
            hits[0].read_text(encoding="cp949", errors="replace"))))
        n = {r[0].strip(): int(r[1]) for r in rows[1:] if len(r) > 1 and r[1].isdigit()}
        up, dn = n.get("지상식소화전", 0), n.get("지하식소화전", 0)
        out |= {"hyd_up": up, "hyd_dn": dn, "hyd_sum": up + dn,
                "water": up + dn + n.get("저수조", 0) + n.get("급수탑", 0)
                         + n.get("비상소화장치", 0)}
    return out


def fmt(n: int) -> tuple[str, ...]:
    """1101 을 문서가 쓰는 두 표기로 — `1101` 과 `1,101`."""
    return (str(n), f"{n:,}")


def live_lines(rel: str, text: str) -> list[tuple[int, str]]:
    """현재형 서술 줄만 (줄번호, 내용). 이력 절과 allow 줄은 뺀다."""
    lines = text.splitlines()
    cut: set[int] = set()
    for start, end in HIST.get(rel, []):
        a = next((i for i, s in enumerate(lines) if s.startswith(start)), None)
        if a is None:
            print(f"! {rel:16s} 이력 절 앵커 없음 — {start!r}. HIST 를 고쳐라")
            continue
        b = next((i for i, s in enumerate(lines) if i > a and s.startswith(end)),
                 len(lines))
        cut.update(range(a, b))
    return [(i + 1, s) for i, s in enumerate(lines)
            if i not in cut and ALLOW not in s]


#: **뒤집힘** 표. (정본에 있는 말, 표에 쓰면 안 되는 말, 왜)
#: ★ 짧아진 것은 안 센다 — 표는 **짧은 풀이**이고 그것이 그 표의 일이다
#:   (MASTER §11). 세는 것은 **반대로 적은 것** 하나다. 글자 수나 비율로 재면
#:   줄일 때마다 울고, 고치면 우는 자는 사람이 끈다(§446-2).
#: ★ **한 줄뿐이다.** 실제로 갈렸던 자리 하나다 — 지어낸 규칙은 안 넣는다.
#:   지어낸 규칙은 오탐을 내고, 오탐이 본문을 덮으면 사람이 이 문을 끈다(§18-13).
#:   새 뒤집힘을 **발견하면** 그때 한 줄과 사유를 같이 적는다(§69).
CONTRADICT: list[tuple[str, str, str]] = [
    ("불변이 아니다", "불변", "정본이 「밀린다」고 적은 키를 표가 「불변」이라 부르면 "
                            "UI 가 그것을 외부 참조로 쓴다 — 2026-10-08 에 실제로 갈려 있었다"),
]


def doc_pairs(text: str) -> list[tuple[str, str]]:
    """MASTER §11 표의 (필드, 설명) 쌍. 이름만 보는 `doc_fields` 의 짝이다."""
    m = re.search(r"^### 데이터 필드\s*$", text, re.M)
    if not m:
        return []
    out: list[tuple[str, str]] = []
    started = False
    for ln in text[m.end():].splitlines():
        if ln.startswith("#"):
            break
        if ln.startswith("|"):
            started = True
            cols = ln.split("|")
            if len(cols) < 4:
                continue
            names = re.findall(r"`([a-z_0-9]+)`", cols[1])
            if names:
                out.append((names[0], cols[2].strip()))
        elif started and not ln.strip():
            break
    return out


def contradiction_faults(pairs: list[tuple[str, str]], fields: dict[str, str],
                         rules: list[tuple[str, str, str]] | None = None) -> list[str]:
    """표가 정본을 **뒤집어** 적은 자리. 순수 함수다.

    ★ 2026-10-10 (DECISIONS §449 · PLAN #101 닫힘). 설명문이 세 곳에 살았고
      이미 갈려 있었다 — `seg_id` 가 정본에서는 「실행 내 표시용 · 불변이
      아니다」인데 표에서는 「런 내 **불변**」이었다. 정본을 하나로 적고
      (산출물이 들고 다니는 스키마) 표는 **짧은 풀이**로 두되, 뒤집힘만 센다.

    밖    **짧아진 것은 안 본다.** 「노면폭(하한)」을 「최소 폭」으로 줄이는 것은
          이 표의 일이고 결함이 아니다.
    """
    rules = CONTRADICT if rules is None else rules
    flat = lambda s: re.sub(r"[\s*`.·]", "", s)
    bad = []
    for f, desc in pairs:
        src = flat(fields.get(f, ""))
        if not src:
            continue
        for canon, wrong, why in rules:
            if flat(canon) in src and flat(wrong) in flat(desc) and flat(canon) not in flat(desc):
                bad.append(f"`{f}` — 정본은 「{canon}」인데 표가 「{wrong}」이라 적는다. {why}")
    return bad


def doc_fields(text: str) -> set[str]:
    """MASTER §11 `### 데이터 필드` 표의 필드명."""
    m = re.search(r"^### 데이터 필드\s*$", text, re.M)
    if not m:
        return set()
    out: set[str] = set()
    started = False
    for ln in text[m.end():].splitlines():
        if ln.startswith("#"):
            break
        if ln.startswith("|"):
            started = True
            for f in re.findall(r"`([a-z_0-9]+)`", ln.split("|")[1]):
                out.add(f)
        elif started and not ln.strip():
            break
    return out


def selftest() -> int:
    """판별식은 **옆집**에 산다 — `tools/docnumtest.py`(§449-2)."""
    from docnumtest import selftest as _s  # noqa: PLC0415  맞물림을 끊는다
    return _s()


def main() -> int:
    if not SEG.exists():
        print(f"! {SEG} 없음 — pipeline 을 먼저 돌려라")
        return 1
    c = counts()
    bad = 0
    cache: dict[str, str] = {}

    def read(rel: str) -> str:
        return cache.setdefault(rel, (ROOT / rel).read_text(encoding="utf-8"))

    # ── 1. PRESENT ────────────────────────────────────────────
    RULES = [
        ("README.md", c["n"], "세그먼트 수"),
        ("README.md", c["clear"], "clear"),
        ("README.md", c["needs_cv"], "needs_cv"),
        ("README.md", c["blocked"], "blocked"),
        ("README.md", c["unknown"], "unknown"),
        ("README.md", c["in_emd"], "동명동 구간"),
        ("docs/MASTER.md", c["n"], "세그먼트 수"),
        ("docs/MASTER.md", c["clear"], "clear"),
        ("docs/MASTER.md", c["needs_cv"], "needs_cv"),
        ("docs/MASTER.md", c["blocked"], "blocked"),
        ("docs/MASTER.md", c["unknown"], "unknown"),
        ("docs/MASTER.md", c["cctv_in"], "CCTV 유효범위 안"),
        ("docs/MASTER.md", c["nfa"], "소방청 지정 기준 충족"),
        # ★ 2026-10-09 (DECISIONS §440 · PLAN #142). **기획서를 여기 넣었다.**
        #   종전에는 `tools/docx_check.py` 가 `docs/proposal.docx` 를 읽어 같은
        #   축을 봤다. 정본이 `.md` 로 옮겨진 뒤로 그 도구는 **사본을 검사하고
        #   있었다** — 정본이 틀려도 사본이 맞으면 초록이다. 기획서는 문서 넷 중
        #   **유일하게 외부가 읽는 것**이라 어긋나면 비용이 가장 크다.
        ("docs/proposal.md", c["n"], "세그먼트 수"),
        ("docs/proposal.md", c["clear"], "clear"),
        ("docs/proposal.md", c["needs_cv"], "needs_cv"),
        ("docs/proposal.md", c["blocked"], "blocked"),
        ("docs/proposal.md", c["unknown"], "unknown"),
        # ★ 2026-10-09 (DECISIONS §444 · PLAN #142). 회색 **사유별** 수 — 실물에
        #   있는 사유마다 한 줄이 저절로 선다. 기획서가 그 다섯을 한 문장에
        #   나열하므로 하나만 낡아도 그 문장 전체가 거짓이 된다.
        *[("docs/proposal.md", v, f"회색 사유 {k[3:]}")
          for k, v in sorted(c.items()) if k.startswith("ur_")],
        # ★ PLAN 도 본다. 08-18 에 PLAN 만 1,087 로 남아 있었다.
        ("docs/PLAN.md", c["n"], "세그먼트 수"),
        ("docs/PLAN.md", c["unknown"], "unknown"),
        # ★ 2026-08-31. 대장·실물 계열. 위 판정 수와 달리 **사람이 손으로
        #   적던 자리**이고 그래서 실제로 여러 번 틀렸다.
        ("docs/MASTER.md", c.get("hyd_up", 0), "소화전 지상식"),
        ("docs/MASTER.md", c.get("hyd_dn", 0), "소화전 지하식"),
        ("docs/MASTER.md", c.get("hyd_sum", 0), "소화전 합"),
        ("docs/MASTER.md", c.get("water", 0), "소방용수시설 총계"),
        ("sources.yaml", c.get("hyd_up", 0), "소화전 지상식"),
        ("sources.yaml", c.get("hyd_dn", 0), "소화전 지하식"),
        ("sources.yaml", c.get("hyd_sum", 0), "소화전 합"),
        # ★ 2026-08-31. 대장 규모. MASTER 가 세 곳에서 낡아 있었다 —
        #   `datasets 36종 · retired 8종`(실제 41 · 10) · `대장 36종`.
        #   사람이 손으로 세는 숫자는 반드시 낡는다.
        ("docs/MASTER.md", c.get("ds", 0), "대장 datasets 종수"),
        ("docs/MASTER.md", c.get("retired", 0), "대장 retired 종수"),
        ("docs/MASTER.md", c.get("migrated", 0), "norm 이관 종수"),
        # ★ 2026-09-02. README 가 빠져 있었다. 저장소를 clone 한 사람이
        #   **처음 보는 파일**인데 `대장 36종`(실물 43)이 살아 있었다.
        #   README 도 `\`datasets\` N종` 서식으로 맞췄으므로 같은 문맥
        #   패턴이 그대로 걸린다.
        ("README.md", c.get("ds", 0), "대장 datasets 종수"),
        ("README.md", c.get("retired", 0), "대장 retired 종수"),
    ]
    # ★ 2026-09-02. 종전에는 **정답이 파일 어딘가에 있나**만 봤다.
    #   그래서 라벨 옆에 오답이 붙어 있어도 통과했다 — MASTER 가
    #   `datasets 41종`(실물 43)인 채로 초록불이었고, 그 절은 바로 위에
    #   "이 세 숫자는 docnum_check 가 대장에서 세어 대조한다 — 손으로
    #   적으면 낡는다" 고 적고 있었다. `docx_check` 의 `1,102` 와 같은
    #   형태다(DECISIONS §95).
    #
    #   라벨 옆의 수를 직접 읽어 비교한다. 문맥 패턴이 없는 항목은
    #   종전대로 존재 대조로 둔다 — 넓히다 오탐이 나면 사람이 검사를 끈다.
    # 라벨 → 그 수가 실제로 적히는 자리. 여기 있는 것만 문맥 대조한다.
    # ★ 2026-10-08 (DECISIONS §435). 「norm 이관 종수」가 여기 **없었다.** 라벨은
    #   `RULES` 에 9월부터 있었는데 문맥 패턴이 없어 존재 대조로 떨어졌고,
    #   MASTER 어디든 `14` 라는 수가 있으면 통과했다 — `datasets 41종` 이 초록불로
    #   살아 있던 바로 그 꼴이다(위 ★). 문맥 패턴 없는 라벨은 **검사하는 척**한다.
    #   세 자리(§18 계층 표 · 레이크 절 · 대장 규모 절)가 전부 「텍스트 N종 이관」
    #   서식이라 패턴 하나가 셋을 다 읽는다.
    CONTEXT_PAT = {
        "대장 datasets 종수": r"`datasets` (\d+)종",
        "대장 retired 종수": r"`retired` (\d+)종",
        "norm 이관 종수": r"텍스트 \*{0,2}(\d+)종 이관",
        # ★ 2026-10-09 (§444 · #142). `no_cctv_band 183(…` 꼴. 사유 이름이
        #   앵커라 **산문 어디든** 걸리고, 수만 다르면 운다.
        **{f"회색 사유 {k[3:]}": rf"{k[3:]}\s+(\d[\d,]*)"
           for k in c if k.startswith("ur_")},
    }

    for rel, want, label in RULES:
        pat = CONTEXT_PAT.get(label)
        txt = read(rel)
        if pat:
            got = [int(g.replace(",", "")) for g in re.findall(pat, txt)]
            wrong = [g for g in got if g != want]
            if wrong:
                print(f"! {rel:16s} {label} {wrong} → {want}")
                bad += 1
                continue
            if not got:
                print(f"! {rel:16s} {label} 서술을 못 찾았다 — 패턴이 낡았다")
                bad += 1
            continue
        if not any(t in read(rel) for t in fmt(want)):
            print(f"! {rel:16s} {label} {want} 없음")
            bad += 1

    # ── 2. RETIRED ────────────────────────────────────────────
    cur = {"세그먼트 수": c["n"], "unknown(회색)": c["unknown"],
           "clear": c["clear"], "needs_cv": c["needs_cv"],
           "blocked": c["blocked"], "소방청 지정": c["nfa"],
           "width_cov 0.5 미만": c["cov_thin"],
           "소화전 지상식": c.get("hyd_up", 0),
           "소화전 지하식": c.get("hyd_dn", 0),
           "소화전 합": c.get("hyd_sum", 0)}
    # ── 1b. 회색 사유의 가짓수 **낱말** ────────────────────────
    nkind = sum(1 for k in c if k.startswith("ur_"))
    for m in gray_kind_faults(read("docs/proposal.md"), nkind):
        print(f"! docs/proposal.md {m}")
        bad += 1

    for m in retired_clashes(cur, RETIRED):
        print(f"! {m}")
        bad += 1

    # ★ 2026-08-24. 뒤에 `%` 나 `m` 이 붙으면 판정 건수가 아니다.
    #   `도달 가능 687(62%)` 의 62 를 옛 blocked 값으로 잡았다.
    #   앞에 `(` 가 오는 경우도 같다 — 괄호 안 백분율이다.
    #   **검사가 문맥 없이 숫자만 보면 새 사실을 쓸 수 없게 만든다.**
    pats = {label: re.compile(r"(?<![\d,.])(" + "|".join(map(re.escape, old))
                              + r")(?![\d,.]|\s*[%％]|\s*[mM]\b|\s*분\b|\s*초\b)")
            for label, old in RETIRED.items()}
    for rel in ("README.md", "docs/MASTER.md", "docs/PLAN.md"):
        for no, ln in live_lines(rel, read(rel)):
            for label, pat in pats.items():
                if label in CONTEXT and not any(w in ln for w in CONTEXT[label]):
                    continue
                for hit in pat.findall(ln):
                    print(f"! {rel:16s}:{no:<5d} 폐기값 {hit} ({label}) — 현재 {cur.get(label, '?')}")
                    print(f"    {ln.strip()[:88]}")
                    bad += 1

    # ── 3. FIELDS ─────────────────────────────────────────────
    if WEB.exists():
        real = set(json.loads(WEB.read_text(encoding="utf-8"))["features"][0]["properties"])
        doc = doc_fields(read("docs/MASTER.md"))
        if not doc:
            print("! docs/MASTER.md  §11 `### 데이터 필드` 표를 못 찾았다")
            bad += 1
        for f in sorted(doc - real):
            print(f"! MASTER §11      {f} 를 웹 필드로 적었으나 산출물에 없다")
            bad += 1
        for f in sorted(real - doc):
            print(f"! MASTER §11      {f} 가 산출물에 있으나 표에 없다")
            bad += 1
        # ── 3b. 표가 정본을 **뒤집어** 적었나 (§449 · PLAN #101 닫힘) ──
        # ★ 이름까지만 보던 자리다. 설명문이 세 곳에 살았고 `seg_id` 가 실제로
        #   갈려 있었다 — 정본은 「불변이 아니다」인데 표는 「런 내 불변」.
        #   짧아진 것은 안 센다(표의 일이다). **반대로 적은 것만** 센다.
        _sp = SCHEMA_WEB if SCHEMA_WEB.exists() else None
        if _sp is not None:
            # ★ `or {}` 를 안 쓴다 — `fields` 가 빈 사전이면 **조용히 통과**하고
            #   그것은 「없다」와 구별이 안 된다(`tests/test_k3.py` 가 그 족을 든다).
            _doc = json.loads(_sp.read_text(encoding="utf-8"))
            _flds = _doc["fields"] if "fields" in _doc else {}
            for msg in contradiction_faults(doc_pairs(read("docs/MASTER.md")), _flds):
                print(f"! MASTER §11      {msg}")
                bad += 1

    # ── 2b. 대장도 본다 ──────────────────────────────────────
    # ★ 2026-08-31 신설. 종전에는 `.md` 셋만 돌았다. 대장은 사람이 손으로
    #   쓰는 문서인데 아무도 안 봤고, 범위를 넓히자마자 넷이 나왔다 —
    #   `hydrant_summary` 의 431+157=588(실물 418+171=589. 덧셈까지 안 맞았다),
    #   `ngii1k` 의 옛 구간 수 1,091.
    #
    #   ★ **원문 줄을 그대로 본다.** `yaml.dump()` 로 다시 뽑으면 긴
    #     문자열이 재접힘돼 줄 번호가 어긋나고, `<!--stale-ok-->` 마커가
    #     엉뚱한 줄에 걸린다. 실제로 그렇게 두 건이 안 먹었다.
    #   ★ `retired:` 블록은 뺀다. 거기 옛 숫자는 폐기 기록이다(§18-3c).
    _src = read("sources.yaml").splitlines()
    _in_ret = False
    for _no, _ln in enumerate(_src, 1):
        if re.match(r"^\w", _ln):
            _in_ret = _ln.startswith("retired:")
        if _in_ret or ALLOW in _ln:
            continue
        for label, pat in pats.items():
            if label in CONTEXT and not any(w in _ln for w in CONTEXT[label]):
                continue
            for hit in pat.findall(_ln):
                print(f"! sources.yaml   :{_no:<5d} 폐기값 {hit} ({label})"
                      f" — 현재 {cur.get(label, '?')}")
                print(f"    {_ln.strip()[:88]}")
                bad += 1

    # ── 4. (삭제) EXPECT 자기모순 ─────────────────────────────
    # 2026-08-18. pipeline.EXPECT 를 없앴다. 판정의 정본은 golden 지문
    # 하나이고 pipeline 은 거기서 읽는다. 동기화할 대상이 사라졌으므로
    # 검사도 사라진다. tests/test_guards.py::test_expect_is_not_hardcoded
    # 가 되돌아오는 것을 막는다.

    # ── 5. 참고 ───────────────────────────────────────────────
    # 절대편차 합은 자동 검사하지 않는다. §4 에는 7.24 를 "옛 적합값"으로
    # 의도적으로 인용한 줄과 현재값으로 잘못 쓴 줄이 섞여 있어 문자열
    # 검사로 못 가른다. 값만 띄우고 판단은 사람이 한다.
    if NFA.exists():
        d = json.loads(NFA.read_text(encoding="utf-8"))
        print(f"\n· 소방서 대조 절대편차 합 {d['abs_dev_sum_m']}m ({d['n_road']}구간)"
              f" — MASTER §4 서술과 대조할 것")

    if bad:
        print(f"\n★ {bad}건. 산출물이 정본이다. 문서를 고쳐라.")
        print("  의도적으로 옛 숫자를 인용한 줄이면 줄 끝에 <!--stale-ok--> 를 붙인다.")
        return 1
    print(f"문서·EXPECT 일치. segments {c['n']} · clear {c['clear']} · "
          f"needs_cv {c['needs_cv']} · blocked {c['blocked']} · unknown {c['unknown']}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    no_args(__doc__)          # 모르는 깃발을 조용히 무시하지 않는다 (§283-2)
    sys.exit(main())
