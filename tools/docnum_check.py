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

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEG = ROOT / "data/processed/segments.geojson"
WEB = ROOT / "web/data/segments.geojson"
NFA = ROOT / "data/processed/nfa_compare.json"

ALLOW = "<!--stale-ok-->"

# ── 이력 절 ────────────────────────────────────────────────────
# 이 범위의 옛 숫자는 옳다. RETIRED 검사에서 뺀다.
# (시작 헤딩, 끝 헤딩). 끝 헤딩 줄은 포함하지 않는다.
HIST: dict[str, list[tuple[str, str]]] = {
    # ★ 2026-08-18 문서 형식 정리로 절 제목이 h1 → h2 가 됐다.
    #   앵커가 깨지면 이력 절이 검사 대상에 들어가 옛 숫자가 무더기로 뜬다.
    #   startswith 라 "## 13. " 처럼 뒤에 공백까지 넣어야 "## 13-1" 을 안 먹는다.
    "docs/MASTER.md": [("## 13. 데이터 이력", "## 17. 작업 원칙")],
    "docs/PLAN.md": [],
    "README.md": [],
}

# ── 폐기된 값 ──────────────────────────────────────────────────
# ★ 산출값이 바뀌면 옛 값을 여기 한 줄 추가한다. 이 도구의 유지보수는
#   그것이 전부다. 추가를 잊으면 다음 사람이 옛 숫자를 그대로 믿는다.
RETIRED: dict[str, list[str]] = {
    "세그먼트 수": ["1087", "1,087", "1091", "1,091", "1093", "1,093",
                 "1102", "1,102"],
    "unknown(회색)": ["396", "429"],
    "clear": ["392", "443", "386"],
    "needs_cv": ["191", "209"],
    "blocked": ["57", "62", "63"],
    # ★ 2026-08-23 추가. 실제 nfa_designated 는 158 인데 MASTER §10 이 139,
    #   PLAN §7-2-4 가 153 으로 적고 있었다. PRESENT 검사는 §2 표에 158 이
    #   있다는 이유로 통과했다 — "있는지" 만 보는 검사의 한계 그대로다.
    "소방청 지정": ["139", "153"],
    # ★ width_cov 0.5 미만은 실측 4 인데 PLAN 두 곳이 69 였다.
    "width_cov 0.5 미만": ["69"],
}

CONTEXT = {
    "unknown(회색)": ("unknown", "회색", "영상판정 불가"),
    "clear": ("clear", "통행 가능", "초록"),
    "needs_cv": ("needs_cv", "판정 보류", "주황"),
    "blocked": ("blocked", "통행 불가", "빨강"),
    # 문맥 없이 139·153·69 를 잡으면 무관한 숫자가 무더기로 걸린다.
    "소방청 지정": ("nfa_designated", "소방청 지정"),
    "width_cov 0.5 미만": ("width_cov",),
}


def counts() -> dict[str, int]:
    P = [f["properties"] for f in json.loads(SEG.read_text(encoding="utf-8"))["features"]]
    v = collections.Counter(p["verdict"] for p in P)
    return {
        "n": len(P),
        "clear": v["clear"],
        "needs_cv": v["needs_cv"],
        "blocked": v["blocked"],
        "unknown": v["unknown"],
        "in_emd": sum(1 for p in P if p["in_emd"]),
        "cctv_in": sum(1 for p in P if (p["cctv_dist_m"] or 9e9) <= 25),
        "nfa": sum(1 for p in P if p.get("nfa_designated")),
        # 채택 소스가 구간의 절반도 못 덮은 것. D-25 실측 1순위이고
        # MASTER §7 · PLAN §3-1 · §6-2 가 같은 숫자를 말해야 한다.
        "cov_thin": sum(1 for p in P
                        if p.get("width_cov") is not None and p["width_cov"] < 0.5),
    }


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
        # ★ PLAN 도 본다. 08-18 에 PLAN 만 1,087 로 남아 있었다.
        ("docs/PLAN.md", c["n"], "세그먼트 수"),
        ("docs/PLAN.md", c["unknown"], "unknown"),
    ]
    for rel, want, label in RULES:
        if not any(t in read(rel) for t in fmt(want)):
            print(f"! {rel:16s} {label} {want} 없음")
            bad += 1

    # ── 2. RETIRED ────────────────────────────────────────────
    cur = {"세그먼트 수": c["n"], "unknown(회색)": c["unknown"],
           "clear": c["clear"], "needs_cv": c["needs_cv"],
           "blocked": c["blocked"], "소방청 지정": c["nfa"],
           "width_cov 0.5 미만": c["cov_thin"]}
    for label, old in RETIRED.items():
        if label in cur and str(cur[label]) in old:
            print(f"! RETIRED[{label!r}] 에 현재값 {cur[label]} 이 있다 — 목록을 고쳐라")
            bad += 1

    pats = {label: re.compile(r"(?<![\d,.])(" + "|".join(map(re.escape, old)) + r")(?![\d,.])")
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
    sys.exit(main())
