"""
test_remeasure.py — 측정 배치의 **막다른 길을 없앴는가.**
(DECISIONS §319 · `tools/remeasure.py` · `tools/verdict_tally.py`)

── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
`fl.sh` 4b 는 판정 **산출물**이 움직이면 멈춘다. 멈추는 것은 옳다 — 그것은
배선 배치가 아니라 측정 배치이고, §13-5 규칙 2 가 「사람이 판단한다」고 적었다.
**그런데 멈춘 다음에 할 일이 어디에도 없었다.**

그래서 사람이 손으로 여섯 도구를 돌렸고 순서 하나가 틀렸다 — `baseline freeze`
뒤에 `evalgen` 을 돌렸다. 봉인은 그 자리의 산출물을 지문으로 굳히는 일이라,
굳힌 뒤에 지표를 다시 내면 **봉인이 그 순간 거짓이 된다.** 전수 verify 가 여덟
단계 빨갰고 여덟이 다 같은 뿌리였다.

★ 그래서 여기가 무는 것은 「사슬이 도는가」가 아니라 **둘**이다 —

    ① 순서   봉인이 끝 · 지표가 봉인 앞 · 지문이 처음
    ② 판단   태그가 없으면 **아무것도 안 고치고** 멈추는가

  ②가 없으면 이 도구는 §13-5 규칙 2 를 어기는 장치가 된다 — 판정 이동을
  사람 판단 없이 받아들이는 것이고, 그것이 제일 나쁜 방향이다.

IN    tools/remeasure.py · tools/verdict_tally.py · tools/fl.sh
OUT   없음
밖    **사슬을 실제로 돌리지 않는다.** `golden lock` · `evalgen` · `baseline
      freeze` 는 레이크와 파이프라인 산출물이 있어야 돌고, 그것은 이 시험의
      물음이 아니다 — 여기는 **순서와 판단**만 든다.
      **판정 이동이 옳은가는 안 본다.** 그것이 바로 사람의 판단이다.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_t", ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


RM = _load("remeasure")
VT = _load("verdict_tally")


# ── ① 순서 ─────────────────────────────────────────────────────

def test_the_seal_is_last_and_the_metrics_come_before_it():
    """★ 09-30 에 틀린 그 순서. 되돌아오면 여기서 운다."""
    tools = [a[0] for _n, a in RM.CHAIN]
    assert tools[-1] == "tools/baseline.py", "봉인이 사슬의 끝이 아니다"
    assert tools.index("tools/evalgen.py") < tools.index("tools/baseline.py"), (
        "지표를 봉인 **뒤**에 낸다 — 봉인이 그 순간 거짓이 된다")
    assert tools.index("tools/golden.py") == 0, "판정 지문 재잠금이 처음이 아니다"
    assert tools.index("tools/ratchet.py") < tools.index("tools/baseline.py"), (
        "래칫 상수는 코드이고 코드는 지문에 든다 — 봉인 앞이어야 한다")


def test_every_link_in_the_chain_is_a_real_tool():
    for _name, argv in RM.CHAIN + RM.AFTER:
        assert (ROOT / argv[0]).exists(), f"없는 도구를 부른다 — {argv[0]}"


def test_the_human_judgment_has_a_place_in_the_chain():
    """태그를 쓰는 자리가 없으면 사람의 판단이 사슬에 안 들어간다."""
    assert "{tag}" in [a for _n, argv in RM.CHAIN for a in argv]


def test_the_selftest_is_alive():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "remeasure.py"),  # noqa: S603 — 트리 안의 도구다
                        "--selftest"], capture_output=True, text=True,
                       cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# ── ② 판단 ─────────────────────────────────────────────────────

def test_without_a_tag_nothing_is_touched(monkeypatch, capsys):
    """★ **이것이 §13-5 규칙 2 다.** 태그가 없으면 사슬이 돌지 않는다."""
    monkeypatch.setattr(RM, "moved", lambda: ["data/processed/segments.geojson"])
    monkeypatch.setattr(RM, "tally", lambda _ref: "구간 1 · clear 1")
    ran: list[str] = []
    monkeypatch.setattr(RM, "_run", lambda argv: ran.append(argv[0]) or 0)
    rc = RM.run("")
    out = capsys.readouterr().out
    assert rc == 1, "판단 없이 초록을 냈다"
    assert ran == [], f"태그도 없이 사슬을 돌렸다 — {ran}"
    assert "측정" in out and "--measured" in out, "무엇을 해야 하는지 안 적는다"
    for name, _ in RM.CHAIN:
        assert name in out, f"사슬의 「{name}」을 안내에 안 적는다"


def test_nothing_moved_means_nothing_runs(monkeypatch):
    """배선 배치에서 사슬이 도는 것도 결함이다 — 봉인 태그가 헛되게 붙는다."""
    monkeypatch.setattr(RM, "moved", lambda: [])
    ran: list[str] = []
    monkeypatch.setattr(RM, "_run", lambda argv: ran.append(argv[0]) or 0)
    assert RM.run("v9.99") == 0
    assert ran == [], "안 움직였는데 사슬을 돌렸다"


def test_a_broken_link_stops_the_rest(monkeypatch):
    """★ 중간이 죽으면 **뒤를 안 돈다.** 건너뛰면 봉인이 거짓이 된다."""
    monkeypatch.setattr(RM, "moved", lambda: ["x"])
    monkeypatch.setattr(RM, "tally", lambda _ref: "?")
    ran: list[str] = []

    def fake(argv):
        ran.append(argv[0])
        return 1 if argv[0] == "tools/evalgen.py" else 0

    monkeypatch.setattr(RM, "_run", fake)
    assert RM.run("v9.99") == 1
    assert "tools/baseline.py" not in ran, "죽은 뒤에도 봉인까지 갔다"


def test_the_tag_reaches_the_seal(monkeypatch):
    monkeypatch.setattr(RM, "moved", lambda: ["x"])
    monkeypatch.setattr(RM, "tally", lambda _ref: "?")
    seen: list[list[str]] = []
    monkeypatch.setattr(RM, "_run", lambda argv: seen.append(argv) or 0)
    RM.run("v9.99")
    assert ["tools/baseline.py", "freeze", "v9.99"] in seen, "태그가 봉인에 안 닿는다"
    assert not any("{tag}" in a for c in seen for a in c), "`{tag}` 를 안 갈아 끼웠다"


# ── ③ 세기 ─────────────────────────────────────────────────────

def test_an_unknown_verdict_is_not_silently_dropped(tmp_path: Path):
    """★ 네 수의 합이 구간 수와 다르면 이동표를 통째로 못 믿는다."""
    q = tmp_path / "s.geojson"
    q.write_text(json.dumps({"features": [
        {"properties": {"verdict": v}} for v in ("clear", "구멍")]}), encoding="utf-8")
    t = VT.tally(q)
    assert t["n"] == 2 and t["clear"] == 1
    assert t.get("★모르는 판정") == 1, "모르는 어휘를 조용히 흘렸다"
    assert "구멍" in VT.line(t), "모르는 어휘를 한 줄에 안 적는다"


def test_one_door_counts_the_verdicts():
    """★ 전후를 **같은 셈**으로 재야 이동표가 참이다 — 그래서 문이 하나다."""
    src = (ROOT / "tools" / "docnum_check.py").read_text(encoding="utf-8")
    assert "verdict_tally" in src, (
        "`docnum_check` 가 판정을 따로 센다 — 문이 둘이면 전후가 어긋난다")
    rm = (ROOT / "tools" / "remeasure.py").read_text(encoding="utf-8")
    assert "verdict_tally" in rm, "`remeasure` 가 판정을 따로 센다"


# ── ④ 배선 ─────────────────────────────────────────────────────

def test_fl_calls_the_chain_and_keeps_the_judgment_with_the_human():
    sh = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    assert "tools/remeasure.py" in sh, "`fl.sh` 가 사슬을 안 부른다 — 4b 가 다시 막다른 길이다"
    assert "--measured=" in sh, "사람이 판단을 줄 깃발이 없다"
    # ★ 순서를 셸에 **다시 적지 않았는가.** 적으면 정본이 둘이 되고 갈린다.
    for t in ("tools/evalgen.py", "tools/baseline.py", "tools/docx_figs.py"):
        assert t not in sh, f"`fl.sh` 가 사슬의 `{t}` 를 직접 부른다 — 순서가 두 집에 산다"
