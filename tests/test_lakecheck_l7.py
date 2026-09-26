"""`lakecheck L7` 의 판별식이 **대장의 선언 면적을 전부 보는지** 잰다.  (§258 · PLAN #134)

★ 왜 이 파일이 따로 있나 (2026-09-25). L7 은 「20MB 넘는 원본인데 대장이
  모른다」를 센다. 실기 전수 verify 에서 두 건이 울었고 **둘 다 거짓 양성**이었다 —

    ① raw/vworld/vworld_map1k_jngj-donggu_20260307.zip
       `ngii1k` 이 복수형 stem 목록과 `files` 글롭으로 적었는데 단수 `stem` 이
       없다. L7 은 단수 칸과 대장 키만 봤다.
    ② landing/202608_상세주소DB_전체분.zip
       착륙 처분 블록에 사유까지 적혀 판단이 끝났는데 L7 이 그 블록을 안 봤다.

  L7 머리말이 잡는 족이 **「범위가 이름보다 좁고 그것이 선언돼 있지 않았다」**
  (W3-8) 인데 **판별식 자신이 그 족이었다.** 거짓 양성은 거짓 초록만큼 비싸다 —
  영구 빨간불은 사람이 검사를 끄게 만든다(§69).

IN    tools/lakecheck.py · 대장 (마지막 시험 하나만)
OUT   없음
밖    L7 이 쓰는 20MB 문턱이나 구역 목록(raw·landing·interim)은 여기서 판단하지
      않는다. 여기 잠그는 것은 **선언을 읽는 면적**과 그 반대편(안 적힌 것은
      여전히 운다)뿐이다.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIG = 21 << 20  # 20MB 문턱을 넘는 크기. 희소 파일로 만든다 — 21MB 를 실제로 쓰지 않는다
SRC = ROOT / "tools" / "lakecheck.py"
ZIP = "vworld/vworld_map1k_jngj-donggu_20260307.zip"


@pytest.fixture
def lc():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)."""
    spec = importlib.util.spec_from_file_location("lakecheck_l7t", SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    m.HITS.clear()
    return m


def _lake(tmp: pathlib.Path, zone: str, rel: str) -> pathlib.Path:
    f = tmp / zone / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("wb") as fh:          # 희소 파일 — st_size 만 크다
        fh.truncate(BIG)
    return f


# ★ 2026-09-25. **`datasets` 가 비면 L7 은 조기 반환한다**("대장을 못 읽었다").
#   처음 쓴 착륙 사례 둘이 그래서 「조용해서 초록」이었다 — 판별식을 재는 대신
#   조기 반환을 재고 있었다. 자리 채우기 데이터셋을 항상 넣어 막는다. 그 조기
#   반환 자체는 맨 아래에서 따로 잰다.
def _led(**blocks) -> dict:
    led: dict = {"datasets": {"_자리": {"stem": "이_이름은_아무것도_안_맞는다"}}}
    for k, v in blocks.items():
        if k == "datasets":
            led["datasets"].update(v)
        else:
            led[k] = v
    return led


def _l7(lc, tmp: pathlib.Path, led: dict) -> list[str]:
    lc.HITS.clear()
    lc.l7(tmp, led)
    return [h["what"] for h in lc.HITS if "대장이 모른다" in h["what"]]


# ── ① 네 가지 선언 형태를 전부 본다 ──────────────────────────────
@pytest.mark.parametrize(
    ("led", "shape"),
    [
        (_led(datasets={"x": {"stem": "vworld_map1k"}}), "단수 stem"),
        (_led(datasets={"x": {"stems": ["other", "vworld_map1k"]}}), "복수 stem 목록"),
        (_led(datasets={"x": {"files": ["vworld/vworld_map1k*_jngj-donggu_*.zip"]}}), "files 글롭"),
        (_led(landing_disposition={"items": [
            {"file": "vworld_map1k*.zip", "why": "시험용 사유"}]}), "착륙 처분"),
    ],
)
def test_every_declaration_shape_silences_l7(lc, tmp_path, led, shape):
    """네 형태 중 **어느 하나로 적혀 있으면** 「대장이 모른다」가 아니다.

    ★ 복수 stem 목록과 `files` 글롭이 빠져 있던 것이 2026-09-25 의 거짓 양성이다.
    """
    _lake(tmp_path, "raw", ZIP)
    assert _l7(lc, tmp_path, led) == [], f"{shape} 선언을 L7 이 못 본다"


def test_an_undeclared_file_still_rings(lc, tmp_path):
    """★ 위가 초록인 이유가 「아무것도 안 잡는다」여서는 안 된다.

    판별식을 넓혔으니 **넓혀서 진짜 누락을 놓치지 않는다**는 반대편을 잰다.
    """
    _lake(tmp_path, "raw", "somebody_elses/mystery_blob_20260307.zip")
    hits = _l7(lc, tmp_path, _led(datasets={"x": {"stem": "vworld_map1k"}}))
    assert len(hits) == 1 and "mystery_blob" in hits[0]


def test_a_glob_does_not_swallow_the_whole_lake(lc, tmp_path):
    """글롭은 **파일명으로** 맞춘다 — 폴더만 맞아도 통과하면 선언 하나가 구역
    전체를 덮는다. `files` 의 한 줄은 그 폴더의 다른 파일을 변호하지 않는다."""
    _lake(tmp_path, "raw", ZIP)
    _lake(tmp_path, "raw", "vworld/완전히_다른것_20260307.zip")
    hits = _l7(lc, tmp_path, _led(datasets={"x": {"files": ["vworld/vworld_map1k*.zip"]}}))
    assert len(hits) == 1 and "완전히_다른것" in hits[0]


# ── ② 착륙 처분은 사유가 있어야 처분이다 ─────────────────────────
def test_a_disposition_without_a_reason_is_not_a_declaration(lc, tmp_path):
    """★ `disposed()` 의 규칙이 L7 에도 살아 있는지 잰다. 사유 없는 한 줄로 이
    검사 전체를 끌 수 있으면 안 된다."""
    _lake(tmp_path, "landing", "202608_상세주소DB_전체분.zip")
    item = {"file": "202608_상세주소DB*.zip"}
    led = _led(landing_disposition={"items": [item]})
    assert _l7(lc, tmp_path, led), "사유 없는 처분이 L7 의 입을 막았다"
    item["why"] = "승인 계열 · 우선순위 낮음"
    assert _l7(lc, tmp_path, led) == []


def test_l7_reads_the_landing_block_through_one_door(lc):
    """★ 착륙 처분을 **`disposed()` 로** 읽는다. 손으로 다시 읽으면 「사유가
    없으면 처분이 아니다」 규칙이 두 벌이 되고 한 쪽만 고쳐진다 — 위 시험이
    초록인데도 L3 과 L7 의 판단이 갈린다."""
    src = SRC.read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "l7")
    calls = {n.func.id for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "disposed" in calls, "L7 이 착륙 처분을 `disposed()` 로 읽지 않는다"
    body = ast.get_source_segment(src, fn) or ""
    code = "\n".join(ln for ln in body.splitlines() if not ln.lstrip().startswith("#"))
    assert "landing_dis" not in code, "L7 이 착륙 블록을 직접 파고든다 — 사본이다"


# ── ③ 프로브가 조용히 통과하지 않는다 ────────────────────────────
def test_an_empty_lake_is_a_failure_not_a_pass(lc, tmp_path):
    """`deadcheck` 프로브 ③ 「조용한 통과」. 20MB 넘는 원본이 0건이면 레이크를
    못 보고 있다는 뜻이고, 그것은 0건이 아니라 실패다."""
    (tmp_path / "raw").mkdir()
    lc.HITS.clear()
    lc.l7(tmp_path, _led())
    assert any("0건" in h["what"] for h in lc.HITS)


def test_an_unreadable_ledger_is_a_failure_not_a_pass(lc, tmp_path):
    _lake(tmp_path, "raw", ZIP)
    lc.HITS.clear()
    lc.l7(tmp_path, {})
    assert any("프로브를 의심하라" in h["what"] for h in lc.HITS)
    assert not any("대장이 모른다" in h["what"] for h in lc.HITS), (
        "대장을 못 읽은 채로 전량을 「모른다」로 세면 안 된다")


# ── ④ 실제 대장으로 두 건이 조용해지는지 ─────────────────────────
def test_the_two_real_findings_are_declarations_in_the_real_ledger(lc, tmp_path):
    """★ 합성 대장이 아니라 **이 저장소의 대장**으로 잰다. 2026-09-25 실기에서
    울었던 그 두 파일이 선언돼 있음을 증명한다. 레이크는 없어도 된다 — 파일을
    흉내내 놓는다."""
    from firelane import ledger

    real = ledger.load_sources()
    _lake(tmp_path, "raw", ZIP)
    _lake(tmp_path, "landing", "202608_상세주소DB_전체분.zip")
    assert _l7(lc, tmp_path, real) == [], "실기에서 울었던 두 건이 아직 「모른다」다"
