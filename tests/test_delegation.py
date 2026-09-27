"""도구가 「저건 X 소관」이라고 넘길 때, **X 가 정말 그것을 드는가.**  (§262)

★ 2026-09-27. `tools/install_navi.py` 가 「web/navi/src 76파일 — 내용 대조는
  golden 소관」이라고 **출력하고 있었다.** `golden.judgment_files()` 는
  `code_closure("firelane.segments")` + `uv.lock` 이라 내비 파일을 하나도 안
  잠근다. 76파일이 변화감지 밖에 있는데 검사가 「저기서 본다」고 말했다.

  이것이 이 저장소가 반복해 데인 족이다 — 규약은 문서에 있고 강제자가 없다
  (MASTER §17), 강제자가 제 이름보다 좁다(§258-16), 강제자 칸이 지목한 검사가
  실재하지 않는다(커밋 `0987aab`, 죽은 참조 26건). **위임은 그 셋을 한 문장에
  모은다** — 넘긴 쪽은 안 보고, 받은 쪽은 받은 줄 모른다.

★ 두 층으로 묻는다. 물을 수 있는 것만 묻고 나머지는 `밖` 에 적는다.
    T1  넘긴 대상이 **실재하는가**            (24건 전부)
    T2  넘긴 대상이 그 주제를 **정말 덮는가**  (덮개를 기계로 낼 수 있는 것만)

  T2 가 좁은 것은 결함이 아니라 사실이다 — `ledger 소관` 처럼 덮개 목록이 없는
  대상은 기계로 물을 수 없다. 좁다는 것을 **여기 적어 두는 것**이 §258-16 에서
  배운 것이다(좁은 것 자체보다, 좁은 줄 모르는 것이 비쌌다).

IN    tools/**.py · src/firelane/**.py 의 「… 소관」 주장
OUT   없음
밖    덮개를 선언하지 않는 대상(`ledger` · `UI` · `datalog fsck`)은 T1 까지만
      본다. 산문의 뜻풀이도 안 한다 — 「무엇을 넘겼는가」를 사람 말로 읽지
      않고, **경로/이름이 실재하는가**만 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 「소관」 앞을 **글자 수로** 자른다. 정규식으로 「대상 이름」을 오려내려다 두 번
#: 빗나갔다 — 마지막 낱말만 집으면 `lakecheck L2` 가 `L2` 가 되고, 점을 못 넘게
#: 하면 `docnum_check.py` 가 `py` 가 된다. 이름의 모양을 맞히는 대신 **앞 70자와
#: 앞줄 꼬리**를 통째로 받아 그 안의 낱말 하나라도 실재하면 통과로 센다.
WINDOW = 70

#: 도구가 아닌 대상. **사유와 함께** 적는다 — 지우면 T1 이 운다.
NOT_A_TOOL = {
    "UI": "화면 담당 — 사람이다. 도구가 아니다",
    "datalog fsck": "외부 절차 — 이 저장소 밖이다",
    "fsck": "위 절차를 줄여 부른 것",
    "그 도구": "문맥이 가리키는 대상이라 이름이 아니다",
}


def _claims() -> list[tuple[Path, int, str]]:
    out = []
    for d in ("tools", "src"):
        for f in sorted((ROOT / d).rglob("*.py")):
            if "__pycache__" in f.parts:
                continue
            lines = f.read_text(encoding="utf-8").splitlines()
            for i, ln in enumerate(lines, 1):
                if "소관" not in ln or "「" in ln:      # 「…」 는 회고 인용이다
                    continue
                head = ln[:ln.index("소관")][-WINDOW:]
                # 줄을 넘겨 적힌 주장(`… `docnum_check.py`\n  소관이고`)을 위해 앞줄 꼬리도 본다
                if len(head.strip()) < 12 and i >= 2:
                    head = lines[i - 2][-WINDOW:] + " " + head
                out.append((f, i, head.strip()))
    return out


def _one(tok: str) -> bool:
    """낱말 하나가 이 저장소의 무엇인가를 가리키는가."""
    tok = tok.strip('`*·()[],\'"「」 ')
    if not tok:
        return False
    if (ROOT / tok).exists():                       # `web/` · `tools/x.py` 같은 경로
        return True
    p = tok if tok.endswith(".py") else f"{tok}.py"
    if any((ROOT / d / p).is_file() for d in (".", "tools", "src/firelane")):
        return True
    if tok.startswith("firelane."):                 # `firelane.guards` → src/firelane/guards.py
        return (ROOT / "src" / "firelane" / f"{tok.split('.', 1)[1]}.py").is_file()
    return False


def _resolves(phrase: str) -> bool:
    if phrase.strip() in NOT_A_TOOL or any(k in phrase for k in NOT_A_TOOL):
        return True
    # ★ 구 안의 **어느 낱말이든** 실재하면 통과다. `lakecheck L2` 는 `lakecheck`
    #   가, `tools/docx_figs.py --check`(그림 ↔ 정본) 은 그 경로가 든다.
    return any(_one(t) for t in re.split(r"[\s`()]+", phrase))


# ── T1 · 넘긴 대상이 실재하는가 ─────────────────────────────────
def test_every_delegation_names_something_that_exists():
    """★ 「저건 X 소관」의 X 가 사라지면 그 검사는 **아무도 안 한다.**

    지운 쪽은 자기가 누구의 변명이었는지 모르고, 넘긴 쪽은 여전히 넘긴다.
    """
    got = _claims()
    assert len(got) >= 15, f"위임 주장을 {len(got)}건밖에 못 찾았다 — 판별식을 의심하라"
    bad = [f"  {f.relative_to(ROOT)}:{i}  「{n} 소관」 — 그런 것이 없다"
           for f, i, n in got if not _resolves(n)]
    assert not bad, (
        f"실재하지 않는 곳으로 넘긴다 {len(bad)}건\n" + "\n".join(bad) + "\n\n"
        "  대상을 고치거나, 도구가 아니면 `NOT_A_TOOL` 에 **사유와 함께** 적어라.")


# ── T2 · 넘긴 대상이 정말 덮는가 ────────────────────────────────
def _golden() -> object:
    import importlib.util
    import sys
    spec = importlib.util.spec_from_file_location("golden_t2", ROOT / "tools" / "golden.py")
    assert spec and spec.loader
    g = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = g          # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(g)
    return g


def golden_violations(line: str, covered: set[str]) -> list[str]:
    """`golden 소관` 이라고 넘긴 줄에서 **golden 이 안 잠그는 주제**를 낸다.

    ★ 판단을 함수로 꺼낸 이유. 처음엔 이것을 시험 본문에 인라인으로 썼고,
      `_claims()` 가 이름 대신 구를 내도록 바꾸자 거르는 조건이 영영 거짓이
      되어 **오늘 그 결함을 다시 넣어도 안 울었다**(§258-10 과 같은 형태).
      그 다음 판은 실물에 거는 바람에, 결함을 고치고 나니 잴 것이 0건이라
      영구 빨간불이 됐다 — 그것은 사람이 검사를 끄게 만든다(§69).
      이제 **판단은 여기 있고**, 합성 사례가 이 함수를 재고 실물은 이 함수로 훑는다.
    """
    if "golden" not in line or "소관" not in line:
        return []
    out = []
    for path in re.findall(r"`?([\w.-]+/[\w./-]+)`?", line):
        if path.endswith((".py", ".sh")) and (ROOT / path).is_file():
            continue                      # 넘긴 **대상**의 이름이지 넘긴 주제가 아니다
        if path not in covered:
            out.append(path)
    return out


def test_the_golden_delegation_rule_catches_the_2026_09_27_defect():
    """★ 합성 사례로 **판별식 자체**를 잰다 — 실물이 깨끗해도 그물은 살아 있다."""
    covered = {"src/firelane/segments.py", "uv.lock"}
    got = golden_violations(
        "# `web/navi/src` 의 내용 대조는 `tools/golden.py` 소관이다", covered)
    assert got == ["web/navi/src"], f"오늘 그 거짓 주장을 못 잡는다: {got}"
    assert golden_violations(
        "# `src/firelane/segments.py` 는 `tools/golden.py` 소관이다", covered) == [], \
        "정말 golden 이 잠그는 것까지 결함으로 센다"
    assert golden_violations("# 그냥 주석이다", covered) == []
    assert golden_violations("# `web/navi/src` 는 vitest 가 든다", covered) == [], \
        "golden 과 무관한 위임까지 센다"


def test_no_tool_delegates_to_golden_what_golden_does_not_lock():
    """위 판별식을 **실물 전부**에 건다."""
    covered = set(_golden().judgment_files())
    assert covered, "golden 이 덮는 것이 0건이다 — 이 시험의 전제가 깨졌다"
    bad = []
    for f, i, _ph in _claims():
        line = f.read_text(encoding="utf-8").splitlines()[i - 1]
        bad += [f"  {f.relative_to(ROOT)}:{i}  `{q}` 를 golden 이 안 잠근다"
                for q in golden_violations(line, covered)]
    assert not bad, (
        f"golden 이 덮지 않는 것을 golden 에 넘긴다 {len(bad)}건\n" + "\n".join(bad) + "\n\n"
        "  golden 은 **판정 지문**이다 — `firelane.segments` 폐포 + `uv.lock` 뿐이다.\n"
        "  판정과 무관한 것을 거기 넣으면 UI 한 줄에도 재잠금이 걸린다(§262).")


def test_golden_does_not_silently_grow_to_cover_the_frontend():
    """★ 반대편. 위 시험을 「golden 을 넓혀서」 통과시키면 안 된다.

    그 길로 가면 내비 한 줄에 판정 재잠금이 걸리고, 재잠금은 20분 재빌드다.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("golden_t3", ROOT / "tools" / "golden.py")
    assert spec and spec.loader
    g = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = g
    spec.loader.exec_module(g)
    front = [p for p in g.judgment_files() if p.startswith("web/")]
    assert not front, (
        f"golden 이 프런트 파일을 잠근다 {front}\n"
        "  판정 지문에 화면이 들어가면 UI 수정마다 재잠금이다 — 다른 방법을 찾아라.")


def test_install_navi_names_guards_that_are_actually_wired():
    """★ 위임을 고친 자리가 **또 산문이 되지 않게** 한다.

    `install_navi.GUARDS` 가 「내비 내용은 이것들이 든다」라고 말한다.
    그 넷이 실제로 돌지 않으면 고치기 전과 같은 거짓말이다.
    """
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("inav", ROOT / "tools" / "install_navi.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)

    pkg = (ROOT / "web" / "navi" / "package.json").read_text(encoding="utf-8")
    verify = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    style = ROOT / "web" / "navi" / "test" / "style.test.ts"

    live = {
        "tsc": '"typecheck"' in pkg and "typecheck" in verify,
        "vitest": "vitest" in pkg and "npm run -s test" in verify.replace("npm test", "npm run -s test"),
        "style-spec 검증기": style.is_file() and "validateStyleMin" in style.read_text(encoding="utf-8"),
        "git": bool(list((ROOT / "web" / "navi" / "src").rglob("*.ts*"))),
    }
    assert set(m.GUARDS) == set(live), (
        f"`GUARDS` 가 이 시험이 아는 것과 다르다\n"
        f"  GUARDS  {m.GUARDS}\n  아는 것 {tuple(live)}\n"
        "  넷을 바꿨으면 여기 판별식도 같이 바꿔라 — 안 바꾸면 이름만 남는다.")
    dead = [k for k, v in live.items() if not v]
    assert not dead, (
        f"`GUARDS` 가 **안 도는 것**을 든다고 말한다: {dead}\n"
        "  고치기 전 「golden 소관」과 같은 거짓말이다(§262).")
