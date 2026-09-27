#!/usr/bin/env python3
"""
test_cost_inputs.py — 경로 비용 입력의 **결측·0 구분**과 **계수 0** 을 강제한다.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-25. 받아 두고 경로 비용에 못 닿던 자료를 엣지에 붙였다(PLAN §1 #2 · #31 · #60).
붙이면서 **되돌아올 결함 둘**이 보였고 둘 다 이 저장소가 이미 낸 형태다.

  ① **0 을 빼서 발행하기.** `publish_navi.py` 가 `if n:` 으로 `park` 이 0 인 구간의
     칸을 뺐다. 받는 쪽에서 결측과 0 이 같은 모습이 되고 화면이 둘을 「없음」 하나로
     찍었다 — **모르는 것을 없다고 말하는** 자리다. 크기를 아끼려다 뜻을 잃었다.
  ② **근거 없는 계수 켜기.** 압력 계수는 전부 0 이고 0 인 것이 요점이다 — 근거가
     없어서 비웠다. 누가 값을 넣으면 `avoidUncertain = 2.0` 과 같은 빚이 하나 더
     생긴다(PLAN §1 #2 · #70). 막지는 않는다. **적었는가**를 본다(가드 6).

★ 손으로 고친 것은 되돌아온다(`test_tools_are_wired` 머리말이 같은 것을 든다).
  그래서 도구를 만들고 그 도구를 여기서 **부른다** — 배선 없는 도구는 배선이 아니다.

── 무엇을 보는가 ───────────────────────────────────────────────
  ① `tools/cost_inputs.py` 가 초록인가 (결측·0 구분 · 자기신고 · 계수)
  ② 그 도구의 `--selftest` 가 무는가 — 빈 그물이면 ① 이 영원히 통과한다
  ③ 발행물이 `park` · `ecam` 을 **구간 전부에** 싣는가(0 을 빼지 않았다)
  ④ TS 쪽 압력 계수가 0 인가 — 켜졌으면 PLAN §1-27 에 이름이 서 있는가
  ⑤ `pressure.ts` 가 판정에 손대지 않는가 (`verdict` · `width_*` 를 안 쓴다)

IN    web/data/navi_graph.json · web/navi/src/domain/{pressure,vehicle}.ts · docs/PLAN.md
OUT   없음 (검사)
PARAM 없음
밖    **TS 함수가 실제로 1 을 내는가는 못 본다** — 파이썬은 `pressure.ts` 를 실행하지
      않는다. 그쪽은 `web/navi/test/pressure.test.ts` 가 든다(계수를 켜면 실제로
      비용이 는다까지 본다). 여기는 **발행물의 칸**과 **소스에 적힌 계수**만 본다.
      ★ 주변 사정(과속방지턱 · 보호구역)이 어느 구간에 붙는지도 못 본다 — 거리 문턱
      `NEAR_M` 은 TS 에 한 벌만 두기로 했다. 파이썬에 두 번째를 만들지 않는다.
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "web" / "data" / "navi_graph.json"
PRESSURE = ROOT / "web" / "navi" / "src" / "domain" / "pressure.ts"
VEHICLE = ROOT / "web" / "navi" / "src" / "domain" / "vehicle.ts"


def _tool():
    """`tools/cost_inputs.py` 를 모듈로 들인다 — 판정 함수를 직접 쓴다."""
    spec = importlib.util.spec_from_file_location("cost_inputs", ROOT / "tools" / "cost_inputs.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(mod)
    return mod


def _graph() -> dict:
    if not GRAPH.exists():
        pytest.skip("환경skip(산출물) — web/data/navi_graph.json 이 없다. "
                    "`python -m firelane.publish_navi` 가 낸다")
    return json.loads(GRAPH.read_text(encoding="utf-8"))


# ── ① · ② 도구를 부른다 ────────────────────────────────────────

def test_cost_inputs_tool_is_green():
    """결측·0 구분 · 자기신고 · 계수 — 도구가 판정한다."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "cost_inputs.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"tools/cost_inputs.py 가 빨갛다:\n{r.stdout}\n{r.stderr}"


def test_cost_inputs_selftest_bites():
    """판정기가 무는가. 빈 그물이면 위 검사가 영원히 통과한다."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "cost_inputs.py"), "--selftest"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, f"cost_inputs 자기검사가 헐겁다:\n{r.stdout}\n{r.stderr}"


# ── ③ 발행물이 0 을 빼지 않는가 ────────────────────────────────

def test_published_graph_separates_null_from_zero():
    """`park` · `ecam` 이 구간 **전부**에 있고, 0 과 `null` 이 다른 값으로 실린다."""
    g = _graph()
    edges = g["edges"]
    for field in ("park", "ecam"):
        missing = [e["seg_uid"] for e in edges if field not in e]
        assert not missing, (
            f"`{field}` 칸이 없는 구간 {len(missing)}개 — 0 을 빼서 발행했다.\n"
            f"  받는 쪽에서 결측과 0 이 같은 모습이 되고 「없음」 하나로 찍힌다.\n"
            f"  보기: {missing[:5]}")
        bad = [e["seg_uid"] for e in edges
               if not (e[field] is None or isinstance(e[field], int))]
        assert not bad, f"`{field}` 가 정수도 null 도 아닌 구간 — {bad[:5]}"
    # 0 인 구간이 실제로 있다. 없으면 「0 을 빼던 때」로 되돌아갔다는 뜻이다.
    assert any(e["park"] == 0 for e in edges), (
        "`park` 이 0 인 구간이 하나도 없다 — 0 을 빼서 발행하던 때로 돌아갔나")
    # 0 의 강도를 발행물이 스스로 든다.
    for key in ("park_unplaced_rows", "ecam_unplaced_sites"):
        assert g["counts"].get(key), (
            f"`counts.{key}` 가 없다 — 0 이 「없다」인지 「붙은 것 중에 없다」인지 못 읽는다")


def test_publish_navi_does_not_suppress_zero():
    """`publish_navi.py` 가 `if n:` 으로 0 을 빼던 자리로 안 돌아갔는가.

    ★ 발행물만 보면 다시 뺀 코드를 **발행 전에는** 못 잡는다. 소스도 본다.
    """
    src = (ROOT / "src" / "firelane" / "publish_navi.py").read_text(encoding="utf-8")
    m = re.search(r"for e, n(?:, c)? in zip\(edges.*?\n(?:.*\n){0,6}", src)
    assert m, "publish_navi.py 에서 park 배분 자리를 못 찾았다 — 이 검사가 보는 자리가 옮겼다"
    blk = m.group(0)
    assert "if n:" not in blk, (
        "`if n:` 이 돌아왔다 — 0 을 빼면 결측과 같은 모습이 된다.\n"
        f"  {blk.strip()}")
    assert 'e["park"] = n' in blk, "park 을 **항상** 싣지 않는다"


# ── ④ 계수가 근거 없이 켜지지 않았는가 ────────────────────────

def test_pressure_knobs_are_inert_or_declared():
    """압력 계수가 0 인가. 0 이 아니면 PLAN §1-27 에 그 이름이 서 있는가(가드 6).

    ★ **일찍 반환하지 않는다.** 계수가 전부 0 인 오늘은 `if not on: return` 이 곧
      「조용한 통과」다 — `tools/deadcheck.py ③` 이 그것을 문다. 단언을 조건 없이
      한 줄로 세워 **늘 재게** 한다.
    """
    mod = _tool()
    kn = mod.knobs(VEHICLE.read_text(encoding="utf-8"))
    assert set(kn) == set(mod.KNOBS), f"계수 목록이 갈렸다 — {sorted(kn)}"
    ledger = mod.ledger_text()
    assert ledger.strip(), "PLAN §1-27 측정 대장이 비었다 — 그러면 이 검사가 무조건 운다"
    undeclared = sorted(k for k, v in kn.items() if v != 0 and k not in ledger)
    assert not undeclared, (
        f"압력 계수 {undeclared} 를 켰는데 PLAN §1-27 측정 대장에 이름이 없다.\n"
        "  **재기 전에 적는다**(가드 6) — 무엇을 묻고 무엇이 나오면 어느 쪽으로\n"
        "  판정하는지 먼저 적어라. `avoidUncertain = 2.0` 이 그 빚이다(#2 · #70).")


def test_pressure_module_declares_its_emptiness():
    """`pressure.ts` 가 「계수가 비었다」를 **머리말에 적는가.**

    ★ 값이 없는 것은 실수가 아니라 판단이다. 적어 두지 않으면 다음 사람이
      「빠뜨렸다」고 읽고 근거 없는 수를 채운다 — 그것이 이 파일이 막는 것이다.
    """
    txt = PRESSURE.read_text(encoding="utf-8")
    assert "값보다 스키마가 먼저다" in txt, "규율을 적지 않았다"
    assert "§1-27" in txt, "켜기 전에 측정 대장에 행을 세운다는 조건을 안 적었다"


# ── ⑤ 판정을 안 만진다 ────────────────────────────────────────

def test_pressure_does_not_touch_verdict():
    """압력이 **판정에 손대지 않는가.** 곱하기만 해야 파이썬 대조가 그대로 맞는다."""
    txt = PRESSURE.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in txt.splitlines()
                     if not ln.lstrip().startswith(("*", "/*", "//", "*/")))
    for tok in ("width_min_m", "width_max_m", "requiredWidth", "edgeCost", "Infinity"):
        assert tok not in code, (
            f"`pressure.ts` 코드가 `{tok}` 를 든다 — 압력은 통행 가부와 폭에 관여하지 않는다.\n"
            "  곱하기만 하므로 `verifyAgainstPrecomputed`(파이썬 대조)가 맞는 것이다.")


def test_adjacency_applies_pressure_only_on_safe():
    """`buildAdjacency` 가 압력을 **안전 경로에만** 건다. 빠른 경로는 실거리가 정의다."""
    txt = (ROOT / "web" / "navi" / "src" / "domain" / "adjacency.ts").read_text(encoding="utf-8")
    assert "pressureFactor" in txt, "인접리스트가 압력을 아예 안 부른다 — 배선이 끊겼다"
    m = re.search(r"const press = ([^;]+);", txt)
    assert m, "`press` 를 정하는 자리를 못 찾았다"
    assert 'mode === "safe"' in m.group(1), f"압력이 모드를 안 가른다 — {m.group(1)}"
    assert re.search(r"penalized \* avoid \* press", txt), (
        "압력이 비용에 곱해지지 않는다 — 계산하고 버리는 코드가 됐다")
