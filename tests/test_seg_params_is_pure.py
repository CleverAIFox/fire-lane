"""판정 파라미터 정본이 **순수한가** — 그리고 옮긴 스위치가 살아 있는가.

★ 2026-09-25 (PLAN §1 #121 · #123 · DECISIONS §249). `seg/params.py` 는
  임계값의 유일한 정본인데(MASTER §18-5 R3) 진단 스위치 다섯을 담느라
  `firelane.paths` 를 import 했고, `paths` 는 **모듈 적재 시점에 `.env` 를
  읽는다**(`paths.py:65`). 즉 「폭 3.0m」를 알고 싶어 이 모듈을 import 하는
  것만으로 디스크가 열렸다. 순수 도메인이 아니었다.

  같은 파일에 가변 전역 `_DBG = {"on": False}` 도 있었고 `segments.py` 가
  그것을 켰다 껐다 했다 — 도메인 모듈에 **실행 상태**가 살았다.

      FIRE_LANE_NO_MERGE   → segments.main() 지역변수
      FIRE_LANE_DEBUG_SEG  → segments.main() 지역변수
      FIRE_LANE_DEBUG_XY   → segments.main() 지역변수
      FIRE_LANE_MIX_SRC    → WidthEngine(mix_src=...)
      FIRE_LANE_OLD_SNAP   → WidthEngine(old_snap=...) · diagnostics(old_snap=...)
      _DBG["on"]           → WidthEngine.debug

★ **이 검사의 절반은 「스위치가 죽지 않았는가」다.** 배선을 옮길 때 가장 흔한
  사고는 값이 틀리는 것이 아니라 **아무 데도 안 닿는 것**이다. 스위치가 죽으면
  판정은 그대로라 게이트가 안 울고, 진단 스위치는 쓸 일이 드물어 몇 달 뒤에야
  드러난다. 그래서 여기서 **켠 것과 끈 것이 다른 답을 내는지**를 직접 본다.

IN    src/firelane/seg/params.py · seg/width.py · segments.py (읽기)
OUT   없음
PARAM 없음
밖    스위치를 켰을 때의 답이 **옳은지**는 안 본다 — 다섯 다 「종전 동작으로
      되돌리는」 진단용이고, 옳은 쪽은 기본값(꺼짐)이다. 여기서 보는 것은
      「켜면 달라지는가」뿐이다.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from firelane.seg.width import WidthEngine

ROOT = Path(__file__).resolve().parent.parent
PARAMS = ROOT / "src/firelane/seg/params.py"

#: 옮긴 스위치. 이름이 바뀌면 아래 검사들이 눈이 먼다.
SWITCHES = ("FIRE_LANE_NO_MERGE", "FIRE_LANE_DEBUG_SEG", "FIRE_LANE_DEBUG_XY",
            "FIRE_LANE_MIX_SRC", "FIRE_LANE_OLD_SNAP")


def _imports(p: Path) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            out.add("<relative>" if node.level else (node.module or ""))
    return out - {""}


# ── 순수한가 ────────────────────────────────────────────────────
def test_the_parameter_home_imports_nothing_at_all():
    """정본이 아무것도 import 하지 않는가. **숫자를 읽으려고 디스크를 열지 않는다.**"""
    got = _imports(PARAMS) - {"__future__"}
    assert not got, (
        f"`seg/params.py` 가 import 한다: {sorted(got)}\n"
        "  이 파일은 임계값의 정본이고 **상수만 있어야 한다**.\n"
        "  `firelane.paths` 는 모듈 적재 때 `.env` 를 읽는다 — import 하는\n"
        "  순간 순수 도메인이 디스크를 만진다(PLAN §1 #121).")


def test_no_mutable_state_lives_in_the_parameter_home():
    """모듈 전역에 **바뀌는 것**이 없는가. `_DBG = {"on": False}` 가 그 자리였다."""
    tree = ast.parse(PARAMS.read_text(encoding="utf-8"))
    bad = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        v = node.value
        if isinstance(v, (ast.Dict, ast.List, ast.Set)):
            names = ([t.id for t in node.targets if isinstance(t, ast.Name)]
                     if isinstance(node, ast.Assign)
                     else [node.target.id] if isinstance(node.target, ast.Name) else [])
            # STATIONS 는 읽기 전용 좌표표다. 쓰는 곳이 없다.
            bad += [n for n in names if n != "STATIONS"]
    assert not bad, (
        f"판정 파라미터 정본에 가변 전역이 있다: {bad}\n"
        "  실행 상태는 인스턴스가 든다 — `WidthEngine.debug` 가 그 자리다(#123).\n"
        "  모듈 전역을 켰다 껐다 하면 **같은 과정 안의 두 호출이 서로를 본다**.")


def test_the_environment_is_read_in_the_stage_layer():
    """스위치 다섯을 **단계층이** 읽는가. 도메인이 읽으면 도로 제자리다."""
    stage = (ROOT / "src/firelane/segments.py").read_text(encoding="utf-8")
    missing = [s for s in SWITCHES if s not in stage]
    assert not missing, (
        f"`segments.py` 가 이 스위치를 안 읽는다: {missing}\n"
        "  옮기다 만 것이거나 **배선이 끊긴 것**이다. 스위치가 죽으면 판정은\n"
        "  그대로라 게이트가 안 울고, 몇 달 뒤에야 드러난다.")
    for rel in ("src/firelane/seg/params.py", "src/firelane/seg/width.py",
                "src/firelane/seg/report.py"):
        body = (ROOT / rel).read_text(encoding="utf-8")
        # 주석·머리말에서 이름을 말하는 것은 괜찮다. 코드에서 읽으면 안 된다.
        code = "\n".join(ln.split("#", 1)[0] for ln in body.splitlines())
        hit = [s for s in SWITCHES if s in code]
        assert not hit, (
            f"`{rel}` 이 환경변수를 직접 읽는다: {hit}\n"
            "  도메인은 인자로 받는다. 읽는 자리는 `segments.main()` 하나다.")


# ── 스위치가 살아 있는가 ────────────────────────────────────────
@pytest.fixture
def engine_pair():
    """같은 소스에 스위치만 다른 엔진 둘. 형상은 폭이 소스마다 **다르게** 나오게 짰다."""
    def band(y0: float, y1: float) -> MultiPolygon:
        return MultiPolygon([Polygon([(0, y0), (100, y0), (100, y1), (0, y1)])])

    # 1:1,000 은 왼쪽 절반만 덮고(부분 커버), 실폭도로는 전 구간을 좁게 덮는다.
    ngii1k = MultiPolygon([Polygon([(0, -3.0), (50, -3.0), (50, 3.0), (0, 3.0)])])
    ngii = band(-2.0, 2.0)
    rw = band(-0.9, 0.9)
    empty = MultiPolygon([])
    mk = lambda **kw: WidthEngine(ngii1k, ngii, rw, empty,  # noqa: E731
                                  unary_union([Point(1e6, 1e6)]), None, **kw)
    return mk


def test_the_mix_src_switch_still_changes_the_answer(engine_pair):
    """`MIX_SRC` 를 켜면 **다른 값**이 나오는가. 안 달라지면 배선이 끊긴 것이다."""
    from shapely.geometry import LineString

    s = LineString([(0, 0), (100, 0)])
    off = engine_pair(mix_src=False).widths(s)
    on = engine_pair(mix_src=True).widths(s)
    assert off != on, (
        "`mix_src` 를 켜도 답이 같다 — 스위치가 **아무 데도 안 닿는다.**\n"
        f"  꺼짐 {off}\n  켜짐 {on}\n"
        "  이 스위치는 구간 폭을 표본 혼합 집합의 최솟값으로 되돌린다.\n"
        "  값이 같아지려면 형상이 그렇게 생겨야 하는데 이 fixture 는 일부러\n"
        "  소스별로 다른 폭이 나오게 짰다.")


def test_the_debug_switch_is_per_instance_not_global(engine_pair, capsys):
    """`debug` 가 **인스턴스 것**인가. 전역이면 한쪽을 켜면 다른 쪽도 켜진다."""
    from shapely.geometry import LineString

    a, b = engine_pair(), engine_pair()
    a.debug = True
    s = LineString([(0, 0), (30, 0)])
    a.widths(s)
    noisy = capsys.readouterr().out
    b.widths(s)
    quiet = capsys.readouterr().out
    assert noisy, "`debug=True` 인데 아무것도 안 찍는다 — 덤프 배선이 끊겼다"
    assert not quiet, (
        "다른 인스턴스도 같이 떠든다 — `debug` 가 아직 전역이다.\n"
        "  `_DBG = {\"on\": ...}` 가 바로 그 형태였다(#123).")


def test_the_defaults_are_the_judgment_path():
    """인자를 안 넘기면 **판정 경로**로 도는가. 기본값이 곧 계약이다."""
    e = WidthEngine(None, None, None, None, None, None)
    assert (e.mix_src, e.old_snap, e.debug) == (False, False, False), (
        f"기본값이 {(e.mix_src, e.old_snap, e.debug)} 다 — 셋 다 꺼짐이어야 한다.\n"
        "  다섯 스위치는 전부 「종전 동작으로 되돌리는」 진단용이고,\n"
        "  판정 경로는 기본값 쪽이다. 기본이 바뀌면 산출물이 조용히 갈린다.")


def test_the_constants_did_not_move_while_the_switches_did():
    """카나리아 — 스위치를 옮기면서 **숫자를 건드리지 않았는가.**"""
    from firelane.seg import params as P

    assert (P.TRUCK, P.PARK, P.NFA_RUN_M, P.CCTV_RANGE) == (3.0, 2.0, 100.0, 25.0)
    assert (P.SNAP_TOL, P.SNAP_MAX, P.XSEC_EXCL, P.WMAX_CAP) == (0.5, 6.0, 5.0, 60.0)
    assert (P.MIN_SEG_LEN, P.COV_MIN, P.SNAP_TRUST) == (3.0, 0.5, 2.0)
    assert P.WIDTH_SRCS == ("ngii1k", "ngii", "silpok")
    assert P.OFFTRACK_MIN == 0.05
    assert not hasattr(P, "_DBG"), "가변 전역이 돌아왔다"
    for s in ("NO_MERGE", "DEBUG_SEG", "DEBUG_XY", "MIX_SRC", "OLD_SNAP"):
        assert not hasattr(P, s), f"`{s}` 가 정본으로 돌아왔다 — 단계층이 읽는다"
