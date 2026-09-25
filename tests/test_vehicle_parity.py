#!/usr/bin/env python3
"""
test_vehicle_parity.py — **차량 통과 규칙 두 판이 같은 답을 내는가** (차분 시험).

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-25 (PLAN §1 #126). 차량 통과 규칙이 **두 언어로 이중 구현**돼 있다 —

    src/firelane/seg/vehicle.py        offtracking · required_width · can_turn
    web/navi/src/domain/vehicle.ts     offtracking · requiredWidth · canTurn

그런데 **알고리즘 동치를 아무도 안 봤다.** 지금 강제자가 보는 것은
`tests/test_sources_of_truth.py` 의 `offtrack_min` 한 줄이고, 그것은
`OFFTRACK_MIN = 0.05` 이라는 **글자가 TS 에 있는가**만 본다. 상수가 같아도
식이 갈리면 그 검사는 초록이다 — 한쪽에서 `√(R²−L²)` 를 1차 근사
`L²/(2R)` 로 되돌려도 아무도 안 운다. 그 차이는 R=8 · L=4 에서 7cm 이고,
7cm 는 3.0m 임계 근처에서 「이 골목으로 갈 수 있나」를 가른다.

`domain/vehicle.ts` 머리말이 이미 대조 수단을 하나 든다 —
`verifyAgainstPrecomputed()` 다. 그것은 **실제 발행물의 통행 가부**만 본다:
`radius_m=null` 고정 · 폭은 그래프에 있는 값뿐 · 비교는 불리언 하나.
즉 내륜차 식도, 회전가부도, 임계 경계도 그 그물에 안 걸린다. 여기서는
반대쪽에서 본다 — **경계값 격자**를 두 판에 같이 먹여 수까지 견준다.

── 어떻게 돌리나 ───────────────────────────────────────────────
격자는 **파이썬이 만든다.** 두 벌로 두면 그 둘이 갈리는 날이 오고, 그러면
이 시험이 제가 막으려는 결함을 제 몸에 갖는다. TS 쪽은
`web/navi/test/vehicleParity.ts` 의 순수 함수 하나(`runCases`)가 격자를
먹고 결과를 돌려주며, 표준입출력 배선은 이 파일이 만드는 glue 가 든다
(`node` 가 `.ts` 를 그대로 먹는다 — 22.18+ 는 무플래그, 그 아래는
`--experimental-strip-types`. 둘 다 시도한다).

격자는 18,228칸이다(제원 9 × 반경 226 × 셋 = 678 · 비용 17,550). 경계는
임계 바로 위/아래를 `1e-9` 로 집고, 결측(`None`) · 0 · 음수 · 검증 플래그
네 조합을 다 든다. `test_grid_has_the_boundaries_it_claims` 가 그 목록이
조용히 줄지 않게 잡는다 — **빈 그물은 초록으로 위장한다.**

★ **레이크도 발행물도 안 본다.** 제원은 사례마다 격자가 들고 `sources.yaml`
  값은 격자의 한 줄로만 들어간다 — `web/data/*.json` 이 없는 기계에서도 돈다.

── 허용오차 ────────────────────────────────────────────────────
TOL = 1e-12 m. 근거 셋 —

    ① 두 판이 쓰는 연산은 `+ − × ÷ √` 뿐이고 IEEE-754 binary64 에서 그
       다섯은 **정확히 반올림**이 규격이다. 같은 순서로 같은 값을 넣으면
       비트까지 같다 — 실측 최대 차이도 0.0 이다(2026-09-25).
    ② 그래서 실제 예산은 JSON 십진 왕복 하나뿐이다. CPython `repr` 과
       V8 `JSON.stringify` 는 둘 다 최단 왕복 표기라 지금은 무손실이고,
       TOL 은 어느 한쪽 직렬화가 바뀔 때를 위한 여유다.
    ③ 이 값은 **차이를 덮을 수 없다.** 도메인이 가르는 가장 작은 양은
       내륜차 문턱 0.05m 이고, 알려진 식 차이(1차 근사)는 0.07m 다.
       1e-12 는 그보다 열 자리 아래다 — 늘릴 이유가 생기면 그것은
       허용오차 문제가 아니라 불일치다.

폭 · 반경 · 비용의 **경계 판정**(`<` · `>=` · 무한)은 허용오차가 없다.
그쪽은 한 비트만 갈려도 통행 가부가 뒤집히므로 정확히 같아야 한다.

★ **불일치를 고치지 않는다.** 이 시험은 차이를 보이는 자리이고 어느 쪽이
  옳은지는 사람이 정한다(PLAN §1 #126 은 「파트 간 합의」로 적혀 있다).

IN    src/firelane/seg/vehicle.py · web/navi/src/domain/vehicle.ts
      (경유: web/navi/test/vehicleParity.ts)
OUT   없음 (검사)
PARAM SPECS · TOL
밖    **비용 계수의 출처는 안 본다.** `TUNING` 의 2.5 · 1.2 · 1.8 이 파이썬
      리터럴과 같은가는 견주지만 그 값이 옳은가는 이 검사의 물음이 아니다
      (근거 없는 값이라고 두 머리말이 이미 적는다).
      `TUNING.avoidUncertain` 도 안 본다 — `edgeCost` 가 안 쓰고 파이썬에
      대응물이 없다(`domain/graph.ts` 소관).
      `edge_cost` 밖의 파이썬 전용 자리(`spec()` · `__getattr__` ·
      `SpecMissing`)도 안 본다. TS 에 대응물이 없다 — 대장을 읽는 쪽은
      `publish_web.py` 이고 TS 는 그 산출을 먹는다.
      **호출부도 안 본다.** 두 판이 같은 답을 내도 그것을 부르는 쪽이
      다른 인자를 넣으면 화면과 판정이 갈린다.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from firelane.seg import vehicle as V
from firelane.seg.params import OFFTRACK_MIN

ROOT = Path(__file__).resolve().parents[1]
NAVI = ROOT / "web" / "navi"
RUNNER = NAVI / "test" / "vehicleParity.ts"       # 격자를 먹는 순수 함수
IMPL = NAVI / "src" / "domain" / "vehicle.ts"     # 대조 대상 — TS 판 규칙

# ── 허용오차. 근거는 머리말 ── 허용오차 절 ─────────────────────
TOL = 1e-12

# ── 제원 격자 ──────────────────────────────────────────────────
# ★ 플래그 조합이 규칙을 **가른다.** `wheelbase_verified` 가 false 면 내륜차가
#   0 이고 `turn_radius_verified` 가 false 면 회전가부가 늘 참이다. 그래서
#   네 조합을 다 넣는다 — 지금 대장은 둘 다 false 라서, 조합을 안 넣으면
#   격자가 식의 절반(내륜차 · 회전 임계)을 **한 번도 안 부른다.**
SPECS: list[dict] = [
    # ① 지금 대장 값 그대로(sources.yaml vehicle_spec · 둘 다 미검증)
    {"id": "대장값", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": 4.0, "turn_radius_m": 12.0,
     "wheelbase_verified": False, "turn_radius_verified": False},
    # ② 발행 꼴. 미검증이면 publish_web 이 null 로 낸다(types.ts 주석)
    {"id": "발행꼴", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": None, "turn_radius_m": None,
     "wheelbase_verified": False, "turn_radius_verified": False},
    # ③④ 한쪽만 켠 것 — 두 플래그가 서로 새는지 본다
    {"id": "축거만검증", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": 4.0, "turn_radius_m": 12.0,
     "wheelbase_verified": True, "turn_radius_verified": False},
    {"id": "반경만검증", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": 4.0, "turn_radius_m": 12.0,
     "wheelbase_verified": False, "turn_radius_verified": True},
    # ⑤ 둘 다 켠 것 — 켜는 날의 판정이 이 줄이다
    {"id": "둘다검증", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": 4.0, "turn_radius_m": 12.0,
     "wheelbase_verified": True, "turn_radius_verified": True},
    # ⑥⑦ 다른 차종. 필요폭이 3.0 이 아닌 자리를 만든다(KFS-1-0073 §3.3 표)
    {"id": "소형", "width_m": 2.2, "clearance_m": 0.5,
     "wheelbase_m": 3.6, "turn_radius_m": 9.5,
     "wheelbase_verified": True, "turn_radius_verified": True},
    {"id": "경형", "width_m": 1.9, "clearance_m": 0.3,
     "wheelbase_m": 3.0, "turn_radius_m": 8.0,
     "wheelbase_verified": True, "turn_radius_verified": True},
    # ⑧ 축거 0 — 문턱 `wb²/(2·OFFTRACK_MIN)` 이 0 으로 내려앉는 자리.
    #    두 판의 **비교 순서**가 갈리면 여기서 0 과 wb 가 갈린다
    {"id": "축거0", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": 0.0, "turn_radius_m": 12.0,
     "wheelbase_verified": True, "turn_radius_verified": True},
    # ⑨ 극초장축 구쎈(5.83m · sources.yaml 섀시 참고표의 최대)
    {"id": "극초장축", "width_m": 2.5, "clearance_m": 0.5,
     "wheelbase_m": 5.83, "turn_radius_m": 12.0,
     "wheelbase_verified": True, "turn_radius_verified": True},
]

# `edge_cost` 격자는 제원 전부를 돌리지 않는다 — 규칙의 **다른 가지**를 내는
# 넷만 쓴다(내륜차 0 · 내륜차 활성 · 필요폭이 3.0 이 아닌 것 · 큰 내륜차).
COST_SPECS = ("대장값", "둘다검증", "경형", "극초장축")

VERDICTS: list[str | None] = [None, "clear", "blocked", "needs_cv", "unknown"]

# 판정 가지를 다 밟는 최소 길이 집합. None · 0 · 음수는 `inf` 가지다
LENGTHS: list[float | None] = [None, -1.0, 0.0, 1e-9, 137.5]


def _dedup(xs: list[float | None]) -> list[float | None]:
    """`None` 을 앞에 한 번, 나머지는 첫 등장 순서대로."""
    out: list[float | None] = [None]
    seen: set[float] = set()
    for x in xs:
        if x is None:
            continue
        f = float(x)
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _radii(s: dict) -> list[float | None]:
    """제원 하나에 먹일 회전반경 격자 — **임계 바로 위/아래를 반드시 넣는다.**

    ★ `1e-9` 는 `float` 로 표현되는 만큼 작은 차이다. 임계에서 한 비트만
      갈려도 통행 가부가 뒤집히는 자리라 여기가 이 격자의 값어치다.
    """
    xs: list[float | None] = [
        None,           # 결측 — 직선으로 본다
        -1.0, 0.0,      # 비양수 가지
        1e-9, 0.5, 3.0, 6.0, 8.0, 11.2, 20.0, 50.0, 1e6,
    ]
    wb = s.get("wheelbase_m")
    if wb is not None:
        # 내륜차가 무시 문턱 아래로 내려가는 반경. 이름은 `vehicle.STRAIGHT_R`
        straight = wb * wb / (2 * OFFTRACK_MIN)
        for b in (float(wb), straight):
            xs += [b - 1e-9, b, b + 1e-9, b - 0.01, b + 0.01]
        xs += [float(wb) / 2]
    tr = s.get("turn_radius_m")
    if tr is not None:
        for b in (float(tr),):
            xs += [b - 1e-9, b, b + 1e-9, b - 0.01, b + 0.01]
    return _dedup(xs)


def _cost_radii(s: dict) -> set[float | None]:
    """비용 격자가 쓰는 반경 — **규칙의 가지를 내는 자리만.**

    폭 · 판정 · lenient · 길이까지 곱하면 반경을 다 돌릴 수 없다. 그래서
    직선(None) · 비양수 · 내륜차 활성 · 회전 임계 · 내륜차 문턱만 남긴다.
    나머지 반경은 `offtracking` 격자가 전수로 본다.
    """
    keep: set[float | None] = {None, 0.0, 8.0, 20.0}
    wb = s.get("wheelbase_m")
    if wb is not None:
        keep |= {float(wb), wb * wb / (2 * OFFTRACK_MIN)}
    tr = s.get("turn_radius_m")
    if tr is not None:
        keep.add(float(tr))
    return keep


def _widths(need: float) -> list[float | None]:
    """필요폭 기준 폭 격자.

    ★ 기준을 **파이썬이 낸 필요폭**으로 잡는다. 두 판의 필요폭이 1비트만
      갈려도 `width < need` 가 뒤집혀 유한/무한으로 나오므로, 수 차이가
      **가부 차이로 증폭돼** 보인다. 허용오차로 덮일 수 없는 자리다.
    """
    return [
        None, 0.0, -1.0,
        need - 1e-9, need, need + 1e-9,                       # 통과 하한
        need + 0.4999, need + 0.5 - 1e-9, need + 0.5,         # 서행 경계
        need + 0.5 + 1e-9, need + 2.0,
        3.0, 4.0,                                             # 고정 — params.TRUCK 과 흔한 골목
    ]


# ── 부호화. TS `enc()` 와 같은 글자를 쓴다 ─────────────────────
def _enc(x: object) -> object:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        f = float(x)
        if math.isnan(f):
            return "nan"
        if f == math.inf:
            return "inf"
        if f == -math.inf:
            return "-inf"
        return 0.0 if f == 0 else f
    return x


def _py_one(c: dict) -> object:
    """파이썬 판 한 사례. 던지는 것도 결과다 — 삼키면 차이가 안 보인다."""
    try:
        if c["fn"] == "offtracking":
            return _enc(V.offtracking(c["radius_m"]))
        if c["fn"] == "requiredWidth":
            return _enc(V.required_width(c["radius_m"]))
        if c["fn"] == "canTurn":
            return _enc(V.can_turn(c["radius_m"]))
        return _enc(V.edge_cost(c["length_m"], c["width_m"], c["verdict"],
                                c["radius_m"], lenient=c["lenient"]))
    except Exception as e:                      # noqa: BLE001 — 예외 종류가 결과다
        return f"throw:{type(e).__name__}"


# ── 격자 ──────────────────────────────────────────────────────
def _case(fn: str, si: int, **kw) -> dict:
    c = {"fn": fn, "spec": si, "radius_m": None, "length_m": None,
         "width_m": None, "verdict": None, "lenient": False}
    c.update(kw)
    return c


def _grid() -> list[dict]:
    """전체 격자. 순서가 곧 두 판의 대조 짝이다."""
    cases: list[dict] = []
    for si, s in enumerate(SPECS):
        V._S = s
        for r in _radii(s):
            for fn in ("offtracking", "requiredWidth", "canTurn"):
                cases.append(_case(fn, si, radius_m=r))
            if s["id"] not in COST_SPECS or r not in _cost_radii(s):
                continue
            need = V.required_width(r)
            for w in _widths(need):
                for verdict in VERDICTS:
                    for lenient in (False, True):
                        for length in LENGTHS:
                            cases.append(_case(
                                "edgeCost", si, radius_m=r, width_m=w,
                                verdict=verdict, lenient=lenient, length_m=length))
    V._S = None
    return cases


# ── TS 판 호출 ────────────────────────────────────────────────
# ★ `.ts` 확장자를 **여기서** 붙인다. node 는 확장자 없는 명세를 못 찾고(그것은
#   번들러의 일이다), TS 소스에 `.ts` 를 쓰면 tsconfig 을 건드려야 한다.
#   그래서 구현을 이 glue 가 넣어 준다 — `vehicleParity.ts` 는 타입만 import 한다.
_GLUE = """
import { readFileSync } from "node:fs";
const vehicle = await import(%s);
const { runCases } = await import(%s);
const payload = JSON.parse(readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(runCases(vehicle, payload)));
"""


def _ts(payload: dict) -> list:
    """`node` 로 TS 판을 부른다. 표준입력으로 격자, 표준출력으로 결과."""
    code = _GLUE % (json.dumps(IMPL.as_uri()), json.dumps(RUNNER.as_uri()))
    body = json.dumps(payload, allow_nan=False)
    last = None
    # 22.18+ 는 무플래그로 `.ts` 를 먹는다. 그 아래는 플래그가 필요하다
    for extra in ([], ["--experimental-strip-types"]):
        last = subprocess.run(                             # noqa: S603
            ["node", *extra, "--input-type=module", "-e", code],
            cwd=NAVI, input=body, capture_output=True, text=True, timeout=300)
        if last.returncode == 0:
            return json.loads(last.stdout)
    raise AssertionError(
        "TS 판을 부를 수 없다. **skip 하지 않는다** — 부를 수 없으면 대조가 없고,\n"
        "  대조 없는 초록은 이 시험이 막으려는 것 그 자체다.\n"
        f"  rc={last.returncode}\n{last.stderr[-2000:]}")


_BOTH: tuple[list[dict], list, list] | None = None


def _run() -> tuple[list[dict], list, list]:
    """격자를 만들어 두 판에 먹인다. 한 번만 돈다(node 실행이 비싸다)."""
    global _BOTH
    if _BOTH is None:
        cases = _grid()
        ts = _ts({"specs": SPECS, "cases": cases})
        py: list[object] = []
        for c in cases:
            V._S = SPECS[c["spec"]]
            py.append(_py_one(c))
        V._S = None
        assert len(ts) == len(cases), (
            f"TS 가 {len(ts)}개를 냈는데 격자는 {len(cases)}개다 — 짝이 안 맞으면 대조가 거짓이다")
        _BOTH = (cases, py, ts)
    return _BOTH


@pytest.fixture(autouse=True)
def _restore_spec():
    """`V._S` 를 격자용으로 갈아끼우므로 시험마다 되돌린다."""
    yield
    V._S = None


@pytest.fixture(autouse=True, scope="module")
def _need_node():
    if shutil.which("node") is None:
        pytest.skip("환경skip(도구) — node 가 없다. TS 판을 부를 수 없다")
    for p in (RUNNER, IMPL):
        assert p.exists(), f"{p} 가 없다 — 대조 상대가 사라졌다"


def _diff(a: object, b: object) -> str | None:
    """같으면 None, 다르면 사유. 불리언 · 무한 · 예외는 허용오차가 없다."""
    if isinstance(a, bool) or isinstance(b, bool):
        return None if a is b else f"py={a} ts={b}"
    if isinstance(a, str) or isinstance(b, str):
        return None if a == b else f"py={a!r} ts={b!r}"
    d = abs(float(a) - float(b))                    # type: ignore[arg-type]
    return None if d <= TOL else f"py={a!r} ts={b!r} 차이={d:.3e}"


def _label(c: dict) -> str:
    s = SPECS[c["spec"]]["id"]
    if c["fn"] == "edgeCost":
        return (f"{c['fn']}[{s}] R={c['radius_m']} L={c['length_m']} "
                f"W={c['width_m']} v={c['verdict']} lenient={c['lenient']}")
    return f"{c['fn']}[{s}] R={c['radius_m']}"


def _compare(fns: tuple[str, ...]) -> None:
    cases, py, ts = _run()
    bad: list[str] = []
    n = 0
    worst = 0.0
    for c, a, b in zip(cases, py, ts, strict=True):
        if c["fn"] not in fns:
            continue
        n += 1
        if not isinstance(a, (str, bool)) and not isinstance(b, (str, bool)):
            worst = max(worst, abs(float(a) - float(b)))
        if (why := _diff(a, b)) is not None:
            bad.append(f"  {_label(c)}  →  {why}")
    assert n >= 100, f"{fns} 사례가 {n}개뿐이다 — 격자가 말라붙었다. 빈 그물은 초록으로 위장한다"
    assert not bad, (
        f"두 판이 갈렸다 — {len(bad)}/{n} 사례.\n"
        "★ **고치지 마라.** 어느 쪽이 옳은지는 사람이 정한다(PLAN §1 #126 · 파트 간 합의).\n"
        "  허용오차를 늘려 덮는 것은 이 시험을 없애는 것과 같다.\n"
        + "\n".join(bad[:40])
        + (f"\n  … {len(bad) - 40}건 더" if len(bad) > 40 else ""))
    print(f"\n{fns} — {n}개 일치. 수 차이 최대 {worst:.3e} (허용 {TOL:.0e})")


# ── 검사 ──────────────────────────────────────────────────────
def test_runner_actually_runs_the_ts_side():
    """**대조가 실제로 일어났는가.** 빈 그물이 초록으로 위장하는 것을 막는다.

    ★ 값을 손으로 적는다. glue 가 조용히 `[]` 를 내거나 격자가 비면 위
      `_compare` 들이 통과하므로, 여기서 **아는 답 하나**를 못 박는다 —
      R=8 · L=4 의 내륜차는 `1.0717967697244912` 다(두 머리말이 든 7cm 예).
    """
    ts = _ts({"specs": [SPECS[4]], "cases": [
        _case("offtracking", 0, radius_m=8.0),
        _case("canTurn", 0, radius_m=11.2),
        _case("edgeCost", 0, radius_m=8.0, length_m=100.0, width_m=3.0),
    ]})
    assert ts[0] == pytest.approx(8.0 - math.sqrt(64 - 16), abs=TOL), ts
    assert ts[0] == pytest.approx(1.0717967697244912, abs=TOL), ts
    assert ts[1] is False, f"R=11.2 를 12.0 차가 돈다고 했다: {ts}"
    assert ts[2] == "inf", f"필요폭 4.07m 자리에 3.0m 를 통과시켰다: {ts}"


def test_grid_has_the_boundaries_it_claims():
    """격자가 **경계값을 실제로 든다.** 격자가 조용히 줄면 여기가 운다."""
    cases = _grid()
    assert len(cases) >= 2000, f"격자 {len(cases)}칸 — 너무 작다"
    rs = {c["radius_m"] for c in cases}
    ws = {c["width_m"] for c in cases}
    assert None in rs and None in ws, "결측을 안 넣었다"
    for r in (0.0, -1.0, 1e-9, 4.0, 4.0 - 1e-9, 4.0 + 1e-9,   # 축거 임계
              12.0, 12.0 - 1e-9, 12.0 + 1e-9,                 # 회전 임계
              160.0, 160.0 - 1e-9, 160.0 + 1e-9):             # 내륜차 문턱(wb=4)
        assert r in rs, f"반경 경계 {r!r} 이 격자에 없다"
    for w in (0.0, -1.0, 3.0, 3.0 - 1e-9, 3.0 + 1e-9, 3.5, 3.5 - 1e-9):
        assert w in ws, f"폭 경계 {w!r} 이 격자에 없다"
    flags = {(bool(SPECS[c["spec"]].get("wheelbase_verified")),
              bool(SPECS[c["spec"]].get("turn_radius_verified"))) for c in cases}
    assert len(flags) == 4, f"검증 플래그 조합 {flags} — 넷을 다 안 넣었다"


def test_offtracking_and_required_width_and_can_turn_are_the_same():
    """PLAN §1 #126 이 드는 셋 — 내륜차 · 필요폭 · 회전가부."""
    _compare(("offtracking", "requiredWidth", "canTurn"))


def test_a_verified_flag_without_its_value_is_where_the_two_split():
    """★ **찾은 불일치. 고치지 않고 못 박는다**(PLAN §1 #126 은 「파트 간 합의」다).

    「검증 플래그는 켜졌는데 그 값이 제원에 없다」 — 이 한 꼴에서 두 판이 갈린다.

        py   `float(s["wheelbase_m"])` 로 **죽는다**(KeyError · 값이 null 이면 TypeError)
        ts   값이 없으면 플래그를 무시하고 내륜차 0 · 회전가부 참 — **막지 않는 쪽**

    ★ **이것은 이론이 아니다.** 오늘 `web/data/vehicle_spec.json` 이 정확히 그
      꼴이다 — `publish_web.py` 의 `_keep` 화이트리스트가 `wheelbase_m` ·
      `turn_radius_m` 을 **안 싣는다**(미검증 값을 화면에 안 보내려는 것이고,
      그 자체는 옳다). `useFleet` 도 `fleet.json` 에서 축거를 채워 넣지 않는다.
      즉 지금 TS 판은 플래그와 무관하게 **늘 내륜차 0 · 늘 회전 가능**이다.
      두 판이 오늘 같은 답을 내는 이유는 식이 같아서가 아니라
      **대장의 플래그 둘이 다 false 라서**다.

      대장에서 `wheelbase_verified: true` 를 올리는 날, 파이썬은 R=8m 코너에
      필요폭 4.07m 를 요구하고 TS 는 3.00m 를 요구한다. 1.07m 차이다.
      `test_sources_of_truth` 는 상수만 보므로 그때도 초록이다.

    아래 둘째 단언이 그날의 **덫**이다 — 값을 안 실은 채 플래그만 올리면 운다.
    """
    published = {"width_m": 2.5, "clearance_m": 0.5,          # 발행물이 싣는 것
                 "wheelbase_verified": True, "turn_radius_verified": True}
    cases = [_case("offtracking", 0, radius_m=8.0), _case("canTurn", 0, radius_m=11.2)]
    ts = _ts({"specs": [published], "cases": cases})
    V._S = published
    py = [_py_one(c) for c in cases]
    assert (ts, py) == ([0, True], ["throw:KeyError", "throw:KeyError"]), (
        "두 판의 「플래그만 켜진 제원」 반응이 여기 적힌 것과 달라졌다.\n"
        f"  ts={ts}  py={py}\n"
        "  ★ 한쪽을 고쳤으면 이 시험의 머리말도 같이 고쳐라 — 이것이 그 불일치의 기록이다.")

    # ── 덫. 값 없이 플래그만 올리는 날 여기서 운다 ──────────────
    led = V._spec()                       # 대장 원본. 캐시를 안 건드린다
    pub = ROOT / "web" / "data" / "vehicle_spec.json"
    # ★ 2026-09-25. 종전에는 `if not pub.exists(): return` 이었고 `deadcheck ③`
    #   (조용한 통과)이 그것을 물었다 — **대상을 못 찾으면 실패가 아니라 통과**다.
    #   이 파일은 커밋 대상이므로 없으면 그것 자체가 사고다.
    assert pub.exists(), (
        f"{pub.relative_to(ROOT)} 가 없다 — 이 파일은 커밋 대상이다.\n"
        "  없으면 아래 덫이 통째로 안 돈다. 없어도 되는 파일이면 이 덫을 지워라.")
    got = json.loads(pub.read_text(encoding="utf-8"))
    for flag, value in (("wheelbase_verified", "wheelbase_m"),
                        ("turn_radius_verified", "turn_radius_m")):
        if not led.get(flag):
            continue
        assert got.get(value) is not None, (
            f"대장에서 `{flag}` 를 올렸는데 발행물 `vehicle_spec.json` 에 `{value}` 가 없다.\n"
            f"  → 파이썬은 대장 값으로 판정하고 TS 는 값이 없어 **그 규칙을 통째로 건너뛴다.**\n"
            f"  → `publish_web.py` 의 `_keep` 에 `{value}` 를 더하고 `golden.py lock` 을 다시 잠가라.\n"
            f"  → 값을 안 보낼 이유가 있다면 TS 쪽이 「모른다」를 어떻게 다룰지 먼저 정하라"
            " (PLAN §1 #126 · 파트 간 합의).")


def test_edge_cost_is_the_same():
    """통행 비용까지 같은가. 임계 넷(필요폭 · 여유 0.5 · 회전 · blocked)이 여기 모인다.

    ★ 두 판의 계수 출처가 다르다 — 파이썬은 리터럴, TS 는 `TUNING` 객체다.
      한쪽만 갈아끼우면 통행 가부는 같은데 비용이 달라지고, 그때 경로가
      갈린다. 그 자리는 수까지 견뎌야 잡힌다.
    """
    _compare(("edgeCost",))
