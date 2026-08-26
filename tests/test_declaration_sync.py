"""선언 ↔ 실물 역방향 정합.

`test_reproducibility.py` 는 **문서가 가리키는 것이 실재하는가**를 본다.
이 파일은 반대다 — **실재하는 것이 선언돼 있는가**를 본다.

한 방향만 검사하면 드리프트가 조용히 쌓인다. 2026-08-26 전수 대조에서
같은 형태의 구멍이 다섯 나왔다.

    CI            `test_doc_style` 이 MASTER §0-1 의 강제자로 지목돼 있는데
                  워크플로가 파일을 열거해 부르느라 빠져 있었다
    verdict_rule  스키마가 규칙 7개 중 6개만 적었다. 빠진 것은
                  `정규표본 1개 -> clear 보류`(DM02825 방어)
    config.js     "임계값은 반드시 같아야 한다"고 선언하고 끝났다
    README §7     CI 가 직접 부르는 도구 다섯이 목록에 없었다
    PLAN §1       행 번호 26·27 결번, 22 가 맨 끝. 본문이 번호로
                  서로를 가리키므로(24행이 "23번") 순서가 곧 의미다

★ 규칙을 고칠 때는 정본을 고친다. 여기 값을 맞추는 것이 아니다.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PLAN = ROOT / "docs" / "PLAN.md"


def _const(rel: str, names: set[str]) -> dict[str, object]:
    """모듈을 임포트하지 않고 최상위 상수를 읽는다. GIS 의존 없이 돈다."""
    out: dict[str, object] = {}
    for node in ast.parse((ROOT / rel).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") in names:
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def _params() -> dict[str, float]:
    p = _const("src/firelane/seg/params.py", {"TRUCK", "PARK", "CCTV_RANGE"})
    missing = {"TRUCK", "PARK", "CCTV_RANGE"} - set(p)
    assert not missing, f"seg/params.py 에서 {sorted(missing)} 를 읽지 못했다"
    return {k: float(v) for k, v in p.items()}  # type: ignore[arg-type]


def _verdict_rule() -> list[str]:
    r = _const("src/firelane/seg/geom.py", {"VERDICT_RULE"}).get("VERDICT_RULE")
    assert r, "seg/geom.py 에 VERDICT_RULE 이 없다"
    return list(r)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────
# 1. 자동화가 부르는 도구가 README 에 있는가
# ─────────────────────────────────────────────────────────────

CALLERS = (".github/workflows/contract.yml", ".github/workflows/pages.yml",
           "tools/verify.sh", "tools/ship.py")


def test_readme_lists_tools_the_automation_calls():
    """CI · verify · ship 이 부르는 도구는 README 에서 이름으로 찾을 수 있어야 한다.

    ★ README §7 은 전수 색인이 아니라 요약이다. 그래서 **모든** 파일을
      요구하지 않는다. 다만 자동화가 의존하는 것은 다르다 — 빨간불이
      떴을 때 다음 사람이 그 도구가 무엇인지 알아야 한다.
      `test_seg_*.py` 같은 글롭 표기는 그대로 인정한다.
    """
    txt = "".join((ROOT / c).read_text(encoding="utf-8")
                  for c in CALLERS if (ROOT / c).exists())
    called = sorted(set(re.findall(r"tools/([A-Za-z0-9_]+\.(?:py|mjs|sh))", txt)))
    assert called, "자동화 정의에서 도구 호출을 찾지 못했다"

    rd = README.read_text(encoding="utf-8")
    globs = [t for t in re.findall(r"[A-Za-z0-9_*./-]+\.(?:py|mjs|sh)", rd) if "*" in t]
    missing = [c for c in called
               if c not in rd and not any(fnmatch.fnmatch(c, g) for g in globs)]
    assert not missing, (
        f"자동화가 부르는데 README 에 없는 도구 {len(missing)}개\n  "
        + "\n  ".join(missing))


def test_readme_globs_still_match_something():
    """글롭 표기가 아무것도 안 가리키게 되면 목록이 거짓이 된다."""
    rd = README.read_text(encoding="utf-8")
    dead = []
    for g in {t for t in re.findall(r"[A-Za-z0-9_*./-]+\.(?:py|mjs|sh)", rd) if "*" in t}:
        if not any(fnmatch.fnmatch(p.name, g) for p in ROOT.rglob("*")
                   if p.is_file() and "__pycache__" not in str(p)):
            dead.append(g)
    assert not dead, f"실재 파일을 가리키지 않는 글롭 표기: {dead}"


# ─────────────────────────────────────────────────────────────
# 2. 산출물 스키마가 코드 정본과 같은가
# ─────────────────────────────────────────────────────────────

SCHEMAS = ("data/processed/segments.schema.json", "web/data/segments.schema.json")


@pytest.mark.parametrize("rel", SCHEMAS)
def test_schema_verdict_rule_matches_code(rel: str):
    """스키마는 산출물과 함께 배포된다. 규칙이 빠지면 외부 재현이 어긋난다.

    ★ 정본은 `seg/geom.py::VERDICT_RULE` 이다. 어긋나면 파이프라인을
      다시 돌려 스키마를 재생성한다. 손으로 JSON 을 고치지 않는다.
    """
    path = ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} 없음")
    got = json.loads(path.read_text(encoding="utf-8")).get("verdict_rule")
    assert got == _verdict_rule(), (
        f"{rel} 의 verdict_rule 이 seg/geom.py 와 다르다\n"
        f"  스키마 {len(got or [])}줄 · 정본 {len(_verdict_rule())}줄")


@pytest.mark.parametrize("rel", SCHEMAS)
def test_schema_params_match_params_module(rel: str):
    """스키마 `params` 블록도 `seg/params.py` 가 정본이다."""
    path = ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} 없음")
    p = _params()
    got = json.loads(path.read_text(encoding="utf-8")).get("params", {})
    for key, name in (("truck_width_m", "TRUCK"), ("park_occupancy_m", "PARK"),
                      ("cctv_range_m", "CCTV_RANGE")):
        if key in got:
            assert float(got[key]) == p[name], (
                f"{rel} — {key} 가 {got[key]}, params.py 는 {p[name]}")


# ─────────────────────────────────────────────────────────────
# 3. UI 임계값이 파이프라인 정본과 같은가
# ─────────────────────────────────────────────────────────────

def test_config_js_thresholds_match_params():
    """`web/config.js` 머리말이 "반드시 같아야 한다"고 선언한다. 그걸 검사한다.

    UI 는 표시용 사본이라 자동 생성하지 않는다. 대신 임계값이 문면에
    그대로 박혀 있으므로, 정본에서 만든 문자열이 파일에 있는지 본다.
    임계값을 바꾸면 이 테스트가 UI 갱신을 강제한다.
    """
    cfg = (ROOT / "web" / "config.js").read_text(encoding="utf-8")
    p = _params()
    truck, clear_at, rng = p["TRUCK"], p["TRUCK"] + 2 * p["PARK"], p["CCTV_RANGE"]

    want = {
        f"임계값({truck:.1f} / {clear_at:.1f} / {rng:.1f})": "머리말 선언",
        f"{truck:.1f}m 미만": "blocked 설명",
        f"{clear_at:.1f}m 이상": "clear 설명",
        f"radius:{rng:g}": "CCTV 커버리지 원",
    }
    missing = [f"{s!r} ({why})" for s, why in want.items() if s not in cfg]
    assert not missing, (
        "web/config.js 가 params.py 임계값과 어긋난다\n  " + "\n  ".join(missing)
        + f"\n\n  정본 — TRUCK={truck} PARK={p['PARK']} CCTV_RANGE={rng}")


# ─────────────────────────────────────────────────────────────
# 4. PLAN 이 스스로를 정확히 가리키는가
# ─────────────────────────────────────────────────────────────

def _plan_rows() -> list[int]:
    lines = PLAN.read_text(encoding="utf-8").splitlines()
    start = next(k for k, x in enumerate(lines) if x.startswith("## 1. 남은 일"))
    stop = next(k for k in range(start + 1, len(lines)) if lines[k].startswith("### "))
    return [int(m.group(1)) for x in lines[start:stop]
            if (m := re.match(r"\| (\d+) \|", x))]


def test_plan_row_numbers_are_contiguous_and_sorted():
    """`§1` 표의 번호는 본문이 서로를 가리키는 데 쓰인다(24행이 "23번").

    결번이 생기면 지운 것인지 아직 안 쓴 것인지 갈리지 않고, 순서가
    어긋나면 표를 눈으로 훑을 수 없다.
    """
    nums = _plan_rows()
    assert nums, "PLAN §1 에서 표 행을 찾지 못했다"
    assert nums == sorted(nums), f"번호가 오름차순이 아니다: {nums}"
    gaps = sorted(set(range(1, max(nums) + 1)) - set(nums))
    assert not gaps, f"결번: {gaps}. 항목을 지웠으면 뒤 번호를 당기지 말고 슬롯을 채운다"
    dup = sorted({n for n in nums if nums.count(n) > 1})
    assert not dup, f"중복 번호: {dup}"


def test_plan_section_refs_resolve():
    """`§N` · `§N-M` 참조가 이 문서 안에 실재해야 한다.

    다른 문서를 가리킬 때는 `MASTER §16-1` 처럼 소속을 앞에 적는다.
    2026-08-26 에 `§13-9` 가 실체 없이 남아 있었고 실제로는 `§8-1` 이었다.
    """
    text = PLAN.read_text(encoding="utf-8")
    h2 = set(re.findall(r"^## (\d+)\.", text, re.M))
    h3 = set(re.findall(r"^### (\d+-[0-9a-z]+)\.", text, re.M))

    bad = set()
    for m in re.finditer(r"§(\d+)(?:-([0-9a-z]+))?", text):
        # 다른 문서를 가리키면 바로 앞에 소속이 붙는다 — `MASTER §16-1`.
        # 앞에 조사나 여는 괄호가 붙어도(`잡는다(MASTER §16-1`) 인정한다.
        before = text[max(0, m.start() - 12):m.start()]
        if re.search(r"(MASTER|DECISIONS|README)\s*$", before):
            continue
        top, sub = m.group(1), m.group(2)
        if sub:
            if f"{top}-{sub}" not in h3 and top not in h2:
                bad.add(f"§{top}-{sub}")
        elif top not in h2:
            bad.add(f"§{top}")
    assert not bad, (
        f"PLAN 안에 실체가 없는 절 참조: {sorted(bad)}\n"
        "  다른 문서를 가리키는 것이면 `MASTER §N` 처럼 소속을 적는다.")


def test_plan_unreferenced_sources_count_is_current():
    """`§1` 이 참조 0곳인 소스를 항목으로 든다. 그 수가 실제와 같아야 한다.

    소스를 코드에 붙이고 PLAN 을 안 고치면 항목이 낡는다.
    """
    yaml = pytest.importorskip("yaml")
    ledger = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    code = "".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "tools").glob("*.py"))
    )
    zero = sorted(k for k in ledger.get("datasets", {}) if k not in code)

    plan = PLAN.read_text(encoding="utf-8")
    m = re.search(r"참조 0곳인 소스 (\d+)종", plan)
    assert m, "PLAN §1 에 `참조 0곳인 소스 N종` 항목이 없다"
    assert int(m.group(1)) == len(zero), (
        f"PLAN 은 {m.group(1)}종, 실제는 {len(zero)}종이다: {zero}")
