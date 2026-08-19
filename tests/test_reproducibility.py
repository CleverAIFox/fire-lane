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


def test_open_work_lives_only_in_plan():
    """
    ★ 문서 셋은 병렬 축이 아니라 한 항목의 **생애주기**다.

        PLAN(미래)  →  도래  →  MASTER(현재)  →  회고  →  DECISIONS(과거)

    한 항목은 한 문서에만 산다. 두 곳에 있으면 생애주기 단계가 둘인 셈이고,
    한쪽만 고치는 날이 온다. 2026-08-18 에 실제로 그랬다 — 08-17~18 에 끝난
    두 항목(ngii1k pipeline 편입 · streetlight ingest kind)이 MASTER §7 에
    남은 일로 그대로 남아 있었다.

    그래서 MASTER 에는 남은 일 **목록**을 두지 않는다. §7 은 "현재 산출물의
    한계"(알려진 근사 · 미검증)만 적는다. 그것은 남은 일이 아니라 현재 상태다.
    """
    m = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/PLAN.md").read_text(encoding="utf-8")

    assert not re.search(r"^##+\s*\d*\.?\s*남은 일\s*$", m, re.M), (
        "MASTER 에 '남은 일' 절이 있다 — 정본은 PLAN §1 이다.\n"
        "  MASTER 는 현재 무엇이 어떤 값인지만 적는다.")
    assert re.search(r"^#{1,2}\s*1\.\s*남은 일\s*$", plan, re.M), (
        "PLAN §1 남은 일이 사라졌다 — 남은 일의 정본이 없어졌다")


def test_finished_work_is_not_listed_as_open():
    """
    ★ 끝난 일이 PLAN 에 남아 있으면 다음 사람이 이미 있는 것을 또 만든다.

    코드를 근거로 판정한다. `docnum_check` 는 판정 숫자만 보므로 이런
    어긋남을 못 잡는다.
    """
    ing = (ETL / "ingest.py").read_text(encoding="utf-8")
    plan = (ROOT / "docs/PLAN.md").read_text(encoding="utf-8")
    sec = re.search(r"#{1,2}\s*1\.\s*남은 일(.*?)\n#{1,2}\s", plan, re.S)
    assert sec, "PLAN §1 을 찾을 수 없다"
    sec = sec.group(1)

    if '"shp_dir"' in ing:
        assert "pipeline STEPS 에 편입" not in sec, (
            "ingest 가 이미 ngii1k 를 만드는데 PLAN §1 에 남은 일로 적혀 있다")
    if 'kind in ("csv_points", "csv_point")' in ing:
        assert "streetlight ingest kind" not in sec, (
            "ingest 가 이미 csv_points 를 분기하는데 PLAN §1 에 남아 있다")


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


def test_every_doc_declares_the_same_lifecycle():
    """
    ★ 문서 축 설명이 세 곳에 흩어져 있다. 셋이 같은 말을 해야 한다.

    2026-08-18, 이 규칙을 도입하면서 README 와 MASTER 는 갱신했는데
    PLAN 머리의 문서표만 옛 3축(DECISIONS 없음)으로 남았다. 테스트 154개가
    전부 통과했다 — `test_no_fifth_doc` 은 문서 **개수**만 세고, 각 문서가
    자기 축을 옳게 적었는지는 아무도 안 봤기 때문이다.

    설명이 여러 곳에 사는 것 자체가 냄새다. 없앨 수 없다면(README 는 첫 인상,
    PLAN 머리는 그 문서를 여는 사람의 첫 화면) 최소한 어긋남은 잡는다.
    """
    for rel in ("README.md", "docs/PLAN.md", "docs/MASTER.md"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        if "docs/PLAN.md" not in txt and "PLAN.md" not in txt:
            continue
        # 문서 축을 설명하는 문서라면 셋을 다 언급해야 한다
        if "MASTER" in txt and "PLAN" in txt and "문서" in txt:
            assert "DECISIONS" in txt, (
                f"{rel} 이 문서 축을 설명하면서 DECISIONS 를 빠뜨렸다 — "
                "옛 3축 표가 남아 있다")


def test_doc_axis_tables_are_consistent():
    """문서표를 가진 곳은 전부 생애주기 표기를 쓴다."""
    for rel in ("README.md", "docs/PLAN.md"):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        if "| 문서 |" not in txt:
            continue
        assert "생애주기" in txt, (
            f"{rel} 의 문서표가 생애주기 표기가 아니다 — 옛 병렬 축 표다")


# ── 문서 형식 (2026-08-18) ────────────────────────────────────
def _body_lines(rel: str) -> list[tuple[int, str]]:
    """코드블록 밖의 줄만. ``` 안의 `## 작업` 은 셸 주석이지 절이 아니다."""
    out, fence = [], False
    for i, s in enumerate((ROOT / rel).read_text(encoding="utf-8").splitlines(), 1):
        if s.lstrip().startswith("```"):
            fence = not fence
            continue
        if not fence:
            out.append((i, s))
    return out


def test_master_headings_are_numbered():
    """
    ★ 번호 없는 절은 외부에서 인용할 수 없다.

    MASTER 는 46회 인용되는 문서인데 2026-08-18 까지 번호 없는 `##` 절이
    11개였다(`## 순서` · `## 확인` · `## raw` …). 같은 제목이 여러 곳에
    있어 "MASTER 의 순서 절"이 어디를 가리키는지 정해지지 않았다.

    §0 서술 규약이 이것을 정한다. 이 테스트가 지킨다.
    """
    bad = [f"{rel}:{no}  {s}"
           for rel in ("docs/MASTER.md",)
           for no, s in _body_lines(rel)
           if s.startswith("## ") and not s[3:4].isdigit()]
    assert not bad, ("번호 없는 절:\n  " + "\n  ".join(bad) +
                     "\n  §0 서술 규약 — 모든 절에 번호를 붙인다.")


def test_master_has_one_h1():
    """
    ★ 문서 제목만 `#`. 절은 `##`.

    2026-08-18 까지 §1~§9 는 `##`, §10~§18 은 `#` 이었다. 목차 도구와
    앵커 검사가 두 층위를 다르게 읽는다. `docnum_check` 의 이력 절
    앵커도 이 수준에 의존한다.
    """
    h1 = [s for _, s in _body_lines("docs/MASTER.md") if s.startswith("# ")]
    assert len(h1) == 1, f"h1 이 {len(h1)}개다: {h1}"


def test_master_is_not_a_letter():
    """
    ★ MASTER 는 특정 사람에게 보내는 편지가 아니다.

    2026-08-18 까지 §11 은 경어체였고 사과문(`어제 충돌은 제 잘못입니다`)과
    개인 호칭이 들어 있었다. 문서가 작업 로그에서 승격되며 문체를 안 바꾼
    결과다. 회고와 사과는 DECISIONS 소관이다(R14).
    """
    body = "\n".join(s for _, s in _body_lines("docs/MASTER.md"))
    hits = [w for w in ("습니다", "합니다", "제 잘못", "드립니다") if w in body]
    assert not hits, (f"경어·사과 표현이 남아 있다: {hits}\n"
                      "  §0 서술 규약 — 평어체 3인칭.")


def test_plan_headings_are_numbered_and_unique():
    """
    ★ 같은 번호가 두 곳을 가리키면 인용이 성립하지 않는다.

    2026-08-18 까지 PLAN 에는 `# 13. 2026-08-12 추가` 와
    `# 13. 2026-08-13 신규 미결` 이 함께 있었고 §13-1~13-5 가 두 벌이었다.
    날짜를 절 제목으로 쓴 결과다 — 그날 나온 것을 그날 절로 만들면
    번호가 날짜만큼 늘어난다. 절은 주제로 나누고 날짜는 본문에 적는다.

    `## 7-5. 호모그래피 기준점 실측` 은 통째로 두 벌이었다. 삽입 스크립트가
    멱등하지 않아 두 번 들어갔고, 앵커 검사는 앵커가 하나라 통과했다.
    """
    import re
    seen, dup, unnum, fence = {}, [], [], False
    for no, s in enumerate(
            (ROOT / "docs/PLAN.md").read_text(encoding="utf-8").splitlines(), 1):
        if s.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        if s.startswith("## ") and not s[3:4].isdigit():
            unnum.append(f"{no} {s}")
        m = re.match(r"^#{2,3} ([\d-]+)\.", s)
        if not m:
            continue
        if m.group(1) in seen:
            dup.append(f"§{m.group(1)}  {no} 과 {seen[m.group(1)]}")
        seen[m.group(1)] = no
    assert not dup, "중복 절 번호:\n  " + "\n  ".join(dup)
    assert not unnum, "번호 없는 절:\n  " + "\n  ".join(unnum)
