"""
test_navi_worker.py — **지도 워커 검사가 한 집에 살고, 그 집이 불리는가.**
(DECISIONS §323 · `tools/naviweight.py::worker_faults`)

── 왜 이 파일이 생겼나 (2026-09-30) ────────────────────────────
배치 O 가 **로컬 전수 verify 82/82 초록**에서 CI 의 `dry` 만 24초에 죽었다.
남은 자국은 이것뿐이었다 —

    내비 빌드 2.0M
    Error: Process completed with exit code 1.

결함이 셋 겹쳐 있었다 —

    ① **시야**  검사가 `dist/assets/index-*.js` 만 읽었다. §313 이 청크를
                가르자 워커 참조가 `maplibre-*.js` 로 갔다. 워커는 산출물에
                있었다 — 검사가 못 본 것이다
    ② **진단**  `shell: bash` 는 `-eo pipefail`. `W=$(grep … | head -1)` 에서
                grep 이 미탐으로 1 을 내면 **`echo "★ …"` 에 닿기 전에**
                `set -e` 가 죽인다. 왜 죽었는지가 한 줄도 안 남았다
    ③ **자리**  그 검사가 **CI 에만** 살았다. 로컬 `verify.sh` 의 「내비 빌드」는
                빌드만 하고 산출물을 안 봤다 — 관문이 갈렸다(3족)

①②는 판정을 `naviweight.py` 로 내리면 같이 없어진다 — 파이썬은 미탐에서
설명을 낸다. ③은 **여기가 든다**: 셸에 판정이 다시 적히면 운다.

IN    .github/actions/build-navi/action.yml · .github/workflows/deploy.yml ·
      tools/verify.sh · tools/naviweight.py
OUT   없음
밖    **워커가 실제로 도는가는 안 본다.** 그것은 브라우저의 일이고 `verify.sh`
      끝의 「사람이 봐야 하는 것」이 든다. **실제 빌드본도 안 본다** — pytest 는
      빌드보다 먼저 돌고(4/82 대 66/82), 「있으면 본다」는 새 클론에서 빈 그물이
      된다. 그 몫은 「내비 무게」 단계가 진짜 산출물로 든다.
      여기가 드는 것은 「판정이 한 집에 있고 그 집이 불리는가」다.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = ROOT / ".github" / "actions" / "build-navi" / "action.yml"
DEPLOY = ROOT / ".github" / "workflows" / "deploy.yml"
VERIFY = ROOT / "tools" / "verify.sh"

#: 판정이 사는 집. 이름 하나다.
TOOL = "tools/naviweight.py"


def _naviweight():
    spec = importlib.util.spec_from_file_location(
        "naviweight_t", ROOT / "tools" / "naviweight.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


NW = _naviweight()


def _live(text: str) -> str:
    """주석을 걷은 본문. **주석에 적힌 grep 은 판정이 아니다.**"""
    return "\n".join(x for x in text.splitlines() if not x.lstrip().startswith("#"))


# ── ③ 자리 — 판정이 한 집에 있는가 ──────────────────────────────
def test_the_verdict_lives_in_one_place():
    """액션이 **제 셸로** 산출물을 판정하지 않는가."""
    body = _live(ACTION.read_text(encoding="utf-8"))
    assert NW.WORKER not in body, (
        f"`build-navi` 가 셸로 워커를 판정한다 — 판정은 `{TOOL}` 하나다.\n"
        "  2026-09-30 에 그 셸 판정이 진입 청크만 읽어 CI 를 죽였다(§323).")


def test_the_action_calls_that_place():
    """★ 반대 방향. 안 부르면 위 시험은 **언제나 초록**이다."""
    body = _live(ACTION.read_text(encoding="utf-8"))
    assert TOOL in body, f"`build-navi` 가 `{TOOL}` 을 안 부른다 — 배포본을 아무도 안 본다"
    assert "--build" in body, "`--build` 없이 부른다 — 산출물을 안 읽는 쪽이다"


def test_the_local_gate_calls_it_too():
    """로컬 관문도 같은 도구를 부르는가 — **갈리면 또 이 일이 난다.**"""
    v = VERIFY.read_text(encoding="utf-8")
    assert re.search(rf"step .*{re.escape(TOOL)} --build", v), (
        f"`verify.sh` 가 `{TOOL} --build` 를 단계로 안 든다 — 관문이 갈린다")


def test_uv_is_standing_before_the_action_runs():
    """판정이 파이썬으로 갔다 — **그 작업들에 `uv` 가 먼저 깔려 있는가.**

    ★ 이 시험이 없으면 액션이 `uv: command not found` 로 죽고, 그것은
      「워커가 없다」와 **구별이 안 되는** 빨강이다.
    """
    text = DEPLOY.read_text(encoding="utf-8")
    assert "\njobs:\n" in text, "`deploy.yml` 에 `jobs:` 가 없다"
    jobs = re.split(r"\n  (?=[A-Za-z][\w-]*:[ \t]*(?:#.*)?$)",
                    text.split("\njobs:\n", 1)[1], flags=re.M)
    callers = [b for b in jobs if "./.github/actions/stage-site" in _live(b)]
    assert callers, "`stage-site` 를 부르는 작업이 없다 — 배포 본문이 사라졌다"
    for b in callers:
        name = b.split(":", 1)[0].strip()
        assert "astral-sh/setup-uv" in b, (
            f"작업 `{name}` 에 `setup-uv` 가 없다 — 액션이 uv 를 못 찾는다")
        assert b.index("astral-sh/setup-uv") < b.index("./.github/actions/stage-site"), (
            f"작업 `{name}` 이 `stage-site` **뒤에** uv 를 깐다 — 액션이 먼저 돈다")


# ── ① 시야 — 청크 자리를 박지 않는가 ────────────────────────────
def test_the_check_does_not_pin_a_chunk(tmp_path):
    """**2026-09-30 에 죽은 것이 이것이다.**"""
    a = tmp_path / "assets"
    a.mkdir()
    w = f"{NW.WORKER}-BbFVVOSM.js"
    (a / w).write_text("// 워커\n", encoding="utf-8")
    # 참조가 진입 청크가 **아닌** 곳에 있다 — §313 이후의 실제 모양
    (a / "maplibre-DWQEZNJQ.js").write_text(f'u="assets/{w}";', encoding="utf-8")
    (a / "index-CBuyQVHW.js").write_text("// 워커 얘기 없다\n", encoding="utf-8")
    assert NW.worker_faults(a) == [], (
        "워커가 진입 청크 밖에 있으면 운다 — 어느 청크에 놓을지는 번들러가 정한다")


def test_the_check_still_refuses_the_real_breakage(tmp_path):
    """★ 그물이 비지 않았는가 — 넓혔다고 다 통과시키면 안 된다."""
    a = tmp_path / "assets"
    a.mkdir()
    (a / "index-CBuyQVHW.js").write_text("// 아무것도 없다\n", encoding="utf-8")
    assert NW.worker_faults(a), "워커가 아예 없는데 통과한다 — **브라우저에서 워커만 404** 다"

    # 접두 없는 이름은 참조가 아니다 — 고장난 상태가 정확히 이 꼴이다
    w = f"{NW.WORKER}-BbFVVOSM.js"
    (a / w).write_text("// 워커\n", encoding="utf-8")
    (a / "index-CBuyQVHW.js").write_text(f'u="{NW.WORKER}.mjs";', encoding="utf-8")
    assert NW.worker_faults(a), "`assets/` 접두 없는 이름을 참조로 센다"

    # 참조는 있고 파일이 없으면 404 — 둘은 다른 고장이다
    (a / "index-CBuyQVHW.js").write_text(f'u="assets/{w}";', encoding="utf-8")
    (a / w).unlink()
    assert NW.worker_faults(a), "가리키는 워커 파일이 없는데 통과한다"


def test_no_assets_dir_is_a_fault_not_a_pass(tmp_path):
    """빌드본이 없는 것을 **통과로 읽지 않는가.** 빈 그물의 제일 흔한 꼴이다."""
    assert NW.worker_faults(tmp_path / "없다"), "산출물이 없는데 조용히 통과한다"
