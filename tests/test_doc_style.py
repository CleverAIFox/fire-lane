#!/usr/bin/env python3
"""
test_doc_style.py — 문서의 문체·절 번호·어휘를 강제한다.

── 왜 생겼나 ───────────────────────────────────────────────────
MASTER §0 이 2026-08-18 에 서술 규약을 선언했다. 평어체 3인칭 · 절마다
번호. 그리고 같은 절이 이렇게 적었다 —
*"전면 개편은 하지 않는다. 손대는 절부터 이 규약을 적용한다."*

그 방침이 결과적으로 문서를 손상시켰다. §11 은 경어체로 특정 담당자에게
보내는 문서였는데, 이후 누군가 어미만 치환하면서 활용이 깨졌다.

    ★ **높이로 표현하지 않다.**                        (§11-2)
    소화전 실물이 0.9m 라 실제 치수로는 안 보이다.      (§11)
    동명동은 2.8km 에 기복 42m 라 완만한다.             (§11)

DECISIONS 는 절 번호가 네 체계로 갈렸고, 그중 셋이 동일한 문자열
`## 2608-18-` 이라 외부에서 인용할 수 없다. `## 4` 와 `## 5` 는 각각 두
곳을 가리킨다.

`test_reproducibility.py` 의 R15~R18 은 문서의 **존재와 소속**만 검사하며
내용의 형식은 검사 대상이 아니었다.

── 탈출구 ──────────────────────────────────────────────────────
의도적 인용은 줄 끝에 `<!--voice-ok-->` 를 붙인다. `docnum_check` 의
`<!--stale-ok-->` 와 같은 방식이다.

IN    docs/*.md · README.md · data/golden/segments.fingerprint.json
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = [ROOT / "README.md", ROOT / "docs/MASTER.md",
        ROOT / "docs/PLAN.md", ROOT / "docs/DECISIONS.md"]
NUMBERED_DOCS = [p for p in DOCS if p.name != "README.md"]
ALLOW = "<!--voice-ok-->"


def _lines(p: Path) -> list[tuple[int, str]]:
    """산문 줄만. 코드 펜스와 4칸 들여쓰기 블록은 제외한다.

    ★ 들여쓴 블록을 제외하는 이유. DECISIONS 는 폐기한 문장을 증거로
      인용한다. 인용을 위반으로 세면 회고를 쓸 수 없게 되고, 그러면
      사람이 검사를 끈다.
    """
    out, fence = [], False
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or ALLOW in line:
            continue
        if line.startswith("    ") and line.strip():
            continue
        out.append((i, line))
    return out


# ★ 2026-08-24. `|` 를 더한다. 표 행의 셀 끝(`… 씁니다 |`)이 종결 위치인데
#   종전 패턴이 이를 인식하지 못했다. MASTER §11 필드표 두 곳이 통과했다.
_END = r"(?=[.·|]|\*\*|$|\s*<)"
VOICE = {
    "경어체": re.compile(
        r"(?:습니다|입니다|ㅂ니다|십시오|하세요|주세요|보세요|어요)" + _END),
    # ★ 1인칭 단수만 검사한다. "우리"는 허용한다 — 이 문서의 화자는
    #   개인이 아니라 프로젝트이고, "우리 산출값 대 소방서 기록" 같은
    #   대조에서 3인칭으로 바꾸면 주체가 불분명해진다. §0 의 1인칭 금지는
    #   서신 문체를 배제하려는 것이므로 그 범위로 한정한다.
    "1인칭 단수": re.compile(r"(?<![가-힣])(제가|저는|저희|내가 )"),
    # ★ 경어체를 평어체로 기계 치환한 흔적. 형용사에 동사 어미가 붙어
    #   활용이 깨진 자리다. 문체 위반보다 무겁다 — 사람이 문장을 다시
    #   써야 한다.
    "깨진 활용": re.compile(
        r"(?:안 보이다|보이다|표현하지 않다|완만한다)" + _END),
}


def test_docs_are_plain_third_person():
    bad: list[str] = []
    for p in DOCS:
        for n, line in _lines(p):
            for tag, rx in VOICE.items():
                if m := rx.search(line):
                    bad.append(f"  {p.name}:{n}  [{tag}] "
                               f"…{line.strip()[:60]}…  ← {m.group(0)!r}")
    assert not bad, (
        "MASTER §0 — 평어체 3인칭. 경어·명령형·1인칭을 쓰지 않는다.\n"
        f"위반 {len(bad)}건\n" + "\n".join(bad[:40])
        + ("\n  …" if len(bad) > 40 else "")
        + f"\n\n의도적 인용이면 줄 끝에 {ALLOW} 를 붙인다.")


# 18-3b 처럼 하위 절에 글자를 붙이는 표기를 허용한다(§18-1a · §18-2a).
H2 = re.compile(r"^## +(.*)$")
NUMBERED = re.compile(r"^(\d+)(?:-(\d+)[a-z]?)?\.")
DATEISH = re.compile(r"^\d{2,4}-\d{2}-")


def _h2(p: Path) -> list[tuple[int, str]]:
    return [(n, m.group(1).strip()) for n, line in _lines(p)
            if (m := H2.match(line))]


def test_h2_headings_are_numbered_and_unique():
    bad: list[str] = []
    for p in NUMBERED_DOCS:
        seen: dict[str, int] = {}
        for n, title in _h2(p):
            m = NUMBERED.match(title)
            if not m:
                kind = "날짜가 절 제목" if DATEISH.match(title) else "번호 없음"
                bad.append(f"  {p.name}:{n}  [{kind}] ## {title[:56]}")
                continue
            key = m.group(0)
            if key in seen:
                bad.append(f"  {p.name}:{n}  [번호 중복 {key}] "
                           f"## {title[:40]}  (앞: {seen[key]}줄)")
            seen[key] = n
    assert not bad, (
        "절 번호는 유일해야 한다. 같은 번호가 두 곳을 가리키면 인용이\n"
        "성립하지 않는다(PLAN §0-0).\n"
        f"위반 {len(bad)}건\n" + "\n".join(bad[:40])
        + ("\n  …" if len(bad) > 40 else ""))


def test_h2_numbers_are_contiguous():
    """번호가 건너뛰면 삭제된 절이 있다는 뜻이다. 삭제했으면 다시 매긴다."""
    bad: list[str] = []
    for p in NUMBERED_DOCS:
        tops = []
        for n, title in _h2(p):
            if (m := NUMBERED.match(title)) and not m.group(2):
                tops.append((int(m.group(1)), n, title))
        for (a, _, _), (b, n2, t2) in zip(tops, tops[1:], strict=False):
            if b not in (a, a + 1):
                bad.append(f"  {p.name}:{n2}  {a} → {b} 건너뜀  ## {t2[:40]}")
    assert not bad, ("절 번호가 연속하지 않는다.\n" + "\n".join(bad[:20]))


GOLDEN = ROOT / "data/golden/segments.fingerprint.json"


def test_doc_enum_vocabulary_matches_golden():
    """산출물의 enum 값과 문서 어휘가 일치하는가.

    ★ docnum_check 는 숫자(PRESENT/RETIRED)와 필드명(FIELDS)을 검사하며
      **어휘 값**은 검사 대상이 아니었다. 2026-08-23 에 unknown_reason 을
      넷으로 분리했으나 MASTER 는 `no_cctv | null` 로 기술하고 있었다.
      UI 담당이 그 표를 기준으로 구현하면 매칭이 성립하지 않는다
      (DECISIONS §67 — 마커 아키텍처 리팩).
    """
    if not GOLDEN.exists():
        return
    L1 = json.loads(GOLDEN.read_text(encoding="utf-8"))["L1"]
    master = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    bad: list[str] = []
    for field in ("verdict", "unknown_reason"):
        for v in sorted(L1.get(field, {})):
            if f"`{v}`" not in master:
                bad.append(f"  MASTER.md  {field} 값 {v!r} 이 없다")
    # 폐기된 값이 현재형으로 남아 있는지 — 반대 방향 검사
    for field, olds in {"unknown_reason": ["no_cctv"]}.items():
        if field in L1 and "no_cctv" not in L1[field]:
            for p in DOCS:
                for n, line in _lines(p):
                    for old in olds:
                        if re.search(rf"`{old}`(?![_a-z])", line):
                            bad.append(f"  {p.name}:{n}  폐기된 {field} 값 "
                                       f"`{old}` 가 현재형으로 남아 있다")
    assert not bad, (
        "산출물의 어휘와 문서가 어긋난다. golden 지문이 정본이다.\n"
        f"위반 {len(bad)}건\n" + "\n".join(bad[:30]))


# ── DECISIONS 항목 형식 (2026-08-24) ──────────────────────────
DECISIONS = ROOT / "docs/DECISIONS.md"
# ★ 소급 적용하지 않는다. §0~§59 를 전부 채우는 것은 별도 작업이고,
#   그것을 요구하면 이 검사가 처음부터 꺼진 채로 시작된다.
#   이 날짜 이후 기록되는 항목부터 형식을 요구한다.
TEMPLATE_FROM = "2026-08-24"


def _decision_blocks() -> list[tuple[int, str, list[str]]]:
    """(줄번호, 제목, 본문줄) 목록. `##` 절 단위로 자른다."""
    lines = DECISIONS.read_text(encoding="utf-8").splitlines()
    out, cur = [], None
    for i, line in enumerate(lines, 1):
        if m := H2.match(line):
            if cur:
                out.append(cur)
            cur = (i, m.group(1).strip(), [])
        elif cur:
            cur[2].append(line)
    if cur:
        out.append(cur)
    return out


def test_decisions_entries_carry_a_date():
    """각 절이 본문 첫 줄에 `> 날짜` 를 갖는가.

    날짜를 절 제목에 쓰면 번호 체계가 깨진다(PLAN §0-0). 본문에 적는다.
    2026-08-24 재매김 이전에는 네 체계가 섞여 있었고, 그중 셋이 동일한
    문자열 `## 2608-18-` 이라 외부에서 인용할 수 없었다.
    """
    bad = []
    for n, title, body in _decision_blocks():
        # ★ §0 은 문서 자체의 머리말이지 결정 항목이 아니다.
        if title.startswith("0."):
            continue
        head = "\n".join(body[:5])
        if not re.search(r"^> \d{4}-\d{2}-\d{2}", head, re.M):
            bad.append(f"  DECISIONS.md:{n}  ## {title[:56]}")
    assert not bad, (
        f"절 본문 첫 5줄에 `> 날짜` 가 없다. {len(bad)}건\n"
        + "\n".join(bad[:20]))


def test_recent_decisions_name_their_enforcer():
    """각 결정이 '누가 이것을 지키는가' 를 밝히는가.

    이 저장소에서 반복된 사고는 하나의 형태를 갖는다 — 규약은 주석이나
    문서에 존재하고 이를 강제하는 검사가 없다. 2026-08-24 하루 동안
    확인된 것만 열둘이다.

        KFS 규칙 대문자 · 폐기 등재분 재편입 · 계층 미선언 ·
        pre-commit 훅 미설정 · CI 의존성 손목록 · web 스탬프 주입 ·
        CODEOWNERS 누락 6건 · verdict 가 시도표본을 받음 · …

    결정을 기록할 때 강제자를 함께 적으면 이 형태가 구조적으로 줄어든다.
    강제자가 없으면 '강제자 없음' 이라고 적는다 — **없다는 사실 자체가
    기록이어야 한다.** 비워 두면 보이지 않는다.
    """
    bad = []
    for n, title, body in _decision_blocks():
        text = "\n".join(body)
        m = re.search(r"^> (\d{4}-\d{2}-\d{2})", text, re.M)
        if not m or m.group(1) < TEMPLATE_FROM:
            continue
        if "강제자" not in text:
            bad.append(f"  DECISIONS.md:{n}  ## {title[:56]}")
    assert not bad, (
        f"{TEMPLATE_FROM} 이후 항목에 `강제자` 기술이 없다. {len(bad)}건\n"
        + "\n".join(bad[:20])
        + "\n\n  형식:\n"
        "    강제자  tests/test_xxx.py::test_yyy\n"
        "    또는\n"
        "    강제자 없음 — 사유: …")
