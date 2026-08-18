"""
test_reproducibility.py — MASTER §18-5 재현성 규약 강제

R1~R7 은 2026-08-09 부터 문서에 있었고, 그 사이 규약 위반이 9건 쌓였다.
문서는 사람이 읽어야 작동하고 사람은 급하면 안 읽는다. 여기는 안 읽어도
작동한다.

이 파일이 강제하는 것:

    R1  스크립트 상단에 IN / OUT 선언
    R4  랜덤이 있으면 시드 고정
    R5  캐시 스킵은 입력 sha 를 본다 (`if out.exists(): return` 금지)

R2(파라미터 상수화)와 R3(상수 정본)은 여기서 안 본다. R2 는 매직넘버 탐지가
거짓 경보를 대량 생산하고, 거짓 경보가 나면 아무도 검사를 안 믿는다.
R3 는 `test_seg_geom.py::test_params_are_not_redefined_in_segments` 가 본다.

★ 새 규칙을 MASTER 에 적을 때는 강제자를 같이 만들어라. 못 만들겠으면 그
  규칙은 규약이 아니라 권고다. 권고라고 적어라(§18-5 머리말).
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ETL = ROOT / "src" / "etl"

# 파이프라인 단계로 실제로 실행되는 스크립트. 라이브러리 모듈은 제외한다
# (seg/ 는 segments.py 가 부르는 부품이지 스스로 도는 단계가 아니다).
STAGE_SCRIPTS = [
    "ingest.py", "segments.py", "streetlight.py",
    "terrain.py", "ortho.py", "publish_web.py",
]


def _doc(name: str) -> str:
    return ast.get_docstring(ast.parse((ETL / name).read_text(encoding="utf-8"))) or ""


# ── R1 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", STAGE_SCRIPTS)
def test_r1_declares_in_and_out(name):
    """
    ★ R1. 스크립트는 입력과 출력을 상단에 선언한다.

    선언이 없으면 "이 단계가 무엇을 읽는가"를 알려면 본문을 다 읽어야 한다.
    2026-08-13 에 기기를 옮겼더니 `ngii1k_5186.gpkg` 없이 파이프라인이 돌아
    폭 주 소스가 실폭도로로 떨어졌고(clear 392 → 346) 원인을 찾는 데 시간을
    썼다. 어느 단계가 무엇을 요구하는지가 어디에도 적혀 있지 않았다.
    """
    d = _doc(name)
    assert re.search(r"^\s*(IN|입력)\b", d, re.M), f"{name}: IN 선언 없음"
    assert re.search(r"^\s*(OUT|산출|출력)\b", d, re.M), f"{name}: OUT 선언 없음"


# ── R4 ─────────────────────────────────────────────────────────
RANDOM_USE = re.compile(r"\b(random\.|np\.random|numpy\.random|\.sample\(|shuffle\()")
SEED_SET = re.compile(r"\bSEED\b|seed\s*\(|random_state\s*=")


@pytest.mark.parametrize("path", sorted(ETL.rglob("*.py")), ids=lambda p: p.name)
def test_r4_random_has_seed(path):
    """
    ★ R4. 랜덤이 들어가면 시드를 파일 상단에 고정한다.

    시드 없는 표본 설계는 표본 설계가 아니다. 실측 대상이 실행마다 바뀌면
    "이 구간을 왜 쟀나"에 답할 수 없다.
    """
    src = path.read_text(encoding="utf-8")
    if not RANDOM_USE.search(src):
        pytest.skip("랜덤 미사용")
    assert SEED_SET.search(src), f"{path.name}: 랜덤을 쓰는데 시드 고정이 없다"


# ── R5 ─────────────────────────────────────────────────────────
BARE_CACHE = re.compile(
    r"if\s+[\w.]*out[\w.]*\.exists\(\)\s*:\s*(\n\s+)?(return|continue)\b")


@pytest.mark.parametrize("path", sorted(ETL.rglob("*.py")), ids=lambda p: p.name)
def test_r5_no_bare_existence_cache(path):
    """
    ★ R5. 단계 스킵은 캐시로 하되 캐시 키에 입력 sha 를 넣는다.

    `if out.exists(): return` 은 금지다. 입력이 바뀌어도 안 돈다 — 즉 낡은
    산출물을 새것이라고 주장하게 된다. 08-17/18 두 무효 산출(1093 · 1091)이
    같은 종류의 착각이었다.
    """
    src = path.read_text(encoding="utf-8")
    m = BARE_CACHE.search(src)
    assert not m, (
        f"{path.name}: 존재만 보고 건너뛴다 — {m.group(0)[:60]!r}\n"
        "  입력 sha 를 캐시 키에 넣어라(MASTER §18-5 R5)")


# ── 규약과 강제자의 동기화 ─────────────────────────────────────
def test_master_rule_table_matches_reality():
    """
    ★ 강제자 표가 실제 파일을 가리켜야 한다.

    표에 적힌 강제자가 사라져도 아무도 모르면, 그 표 자체가 다음 사람을
    속이는 문서가 된다. 표에 나오는 테스트·모듈이 실재하는지만 본다.
    """
    m = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    tbl = re.search(r"\| 규칙 \| 강제자 \|(.+?)\n\n", m, re.S)
    assert tbl, "§18-5 강제자 표를 찾을 수 없다"
    missing = []
    for ref in re.findall(r"`([\w./]+\.py)(?:::[\w:]+)?`", tbl.group(1)):
        if not ((ROOT / "tests" / ref).exists() or (ETL / ref).exists()
                or (ROOT / ref).exists()):
            missing.append(ref)
    assert not missing, f"강제자로 적혔는데 없는 파일: {missing}"


def test_master_open_items_are_not_already_done():
    """
    ★ 끝난 일이 '남은 일'에 남아 있으면 다음 사람이 이미 있는 것을 또 만든다.

    §7 의 7·8번(ngii1k pipeline 편입 · streetlight ingest kind)은 08-17~18 에
    해소됐다. `ingest.py` 가 두 kind 를 모두 분기하고 ngii1k 를 직접 만든다.
    그런데 목록에는 아직 남은 일로 적혀 있었다. docnum_check 는 판정 숫자만
    보므로 이런 것을 못 잡는다.
    """
    ing = (ETL / "ingest.py").read_text(encoding="utf-8")
    m = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    # ★ 목록 자체(코드블록)만 본다. 해소 기록은 그 항목을 인용하므로
    #   절 전체를 보면 "끝났다고 적은 문장"을 위반으로 잡는다.
    sec = re.search(r"## 7\. 남은 일\s*\n+```(.*?)```", m, re.S)
    assert sec, "§7 목록 코드블록을 찾을 수 없다"
    sec = sec.group(1)

    if 'kind in ("ngii1k"' in ing or '"shp_dir"' in ing:
        assert "ngii1k 를 pipeline STEPS 에 편입" not in sec, (
            "ingest 가 이미 ngii1k 를 만드는데 §7 에 남은 일로 적혀 있다")
    if 'kind in ("csv_points", "csv_point")' in ing:
        assert "streetlight ingest kind 처리" not in sec, (
            "ingest 가 이미 csv_points 를 분기하는데 §7 에 남은 일로 적혀 있다")


# ── 문서 ↔ 저장소 동기화 ───────────────────────────────────────
def test_no_fifth_doc():
    """
    ★ 문서는 넷이다. 다섯 번째는 만들지 않는다.

    과거(DECISIONS) · 현재(MASTER) · 미래(PLAN) 세 시제가 다 찼다. 새 문서를
    만들고 싶으면 그것은 셋 중 하나의 절이다.

    이 규칙은 원래 "셋뿐이다" 였고 DECISIONS 가 그것을 어기고 생겼다.
    규칙을 고쳤으니 이제는 지킨다.
    """
    allowed = {"MASTER.md", "PLAN.md", "DECISIONS.md"}
    found = {p.name for p in (ROOT / "docs").glob("*.md")}
    extra = sorted(found - allowed)
    assert not extra, (
        f"다섯 번째 문서: {extra}\n"
        "  MASTER(현재) · PLAN(남은 일) · DECISIONS(왜 그렇게 됐나) 중\n"
        "  어디의 절인지 정해서 옮겨라.")


def test_readme_structure_lists_real_files():
    """
    ★ README 의 구조 목록이 실재하는 파일을 가리켜야 한다.

    2026-08-18 리팩으로 `seg/` 6모듈이 생기고 `tools/*_2026*.py` 8개가
    사라졌는데 README 는 옛 구조를 그대로 적고 있었다. 다음 사람이
    1,168줄짜리 `segments.py` 를 찾다가 429줄을 보고 "뭐가 사라졌지" 한다.
    """
    rd = (ROOT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"## 구조\s*\n+```(.*?)```", rd, re.S)
    assert block, "README 구조 블록을 찾을 수 없다"

    missing = []
    for line in block.group(1).splitlines():
        name = line.strip().split()[0] if line.strip() else ""
        if not name.endswith(".py"):
            continue
        if "*" in name:                      # 글롭 표기는 건너뛴다
            continue
        hits = list(ROOT.rglob(name.split("/")[-1]))
        if not any("__pycache__" not in str(h) for h in hits):
            missing.append(name)
    assert not missing, f"README 에 적혔는데 없는 파일: {missing}"


def test_readme_lists_the_seg_modules():
    """`seg/` 는 이제 계산의 본체다. README 구조에서 빠지면 안 된다."""
    rd = (ROOT / "README.md").read_text(encoding="utf-8")
    for mod in ("params.py", "graph.py", "width.py", "geom.py",
                "roadname.py", "report.py"):
        assert mod in rd, f"README 구조에 seg/{mod} 가 없다"


def test_open_questions_live_in_plan_not_master():
    """
    ★ 같은 미결정이 두 문서에 있으면 한쪽만 고치게 된다.

    그래프 방향성과 회전 반경(내륜차)은 `PLAN §5-7` 이 정본이다.
    MASTER 는 현재 상태를 적는 문서이므로 미결정 선택지를 나열하지 않는다.
    """
    m = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/PLAN.md").read_text(encoding="utf-8")
    assert "그래프 방향성" in plan, "PLAN 에서 그래프 방향성 미결정이 사라졌다"

    # MASTER 가 언급하는 것 자체는 옳다 — D-XX 대장은 MASTER 에 있다.
    # 다만 **선택지를 나열하지 말고 PLAN 을 가리켜야** 한다. 나열하면
    # 두 문서에 같은 내용이 살고, 한쪽만 고치는 날이 온다.
    for line in m.splitlines():
        if "그래프 방향성" not in line:
            continue
        assert "PLAN" in line, (
            f"MASTER 가 미결정을 정본 참조 없이 적었다:\n    {line.strip()}\n"
            "  선택지는 PLAN §5-7 에만 둔다. MASTER 는 가리키기만 한다.")
