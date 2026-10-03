"""
test_naviweight.py — **출동 중에 끊기는 것이 없는가**를 관문이 실제로 무는가.
(PLAN §13 W13-3 · W13-4 · DECISIONS §312 · §313)

── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
W13-4 는 「지하·산간에서 지도 글자가 사라진다」였다. 원인은 `GLYPHS` 상수 하나가
`demotiles.maplibre.org` 를 가리킨 것이고, **그것을 보는 검사가 하나도 없었다.**
누가 내일 다른 CDN 을 하나 더 붙여도 아무도 안 운다.

★ 그래서 무는 것은 「지금 초록인가」가 아니라 **「밖에 기대는 것이 늘면 빨개지는가」**다.
  그리고 오프라인은 **셋이 다 있어야** 성립한다 — 글자 · 서비스 워커 · 없는 주소의 문.
  하나만 빠져도 「대체로 된다」가 되고, 그것은 출동에서 「안 된다」와 같다.

IN    tools/naviweight.py · web/navi/** · web/fonts/** · web/404.html
OUT   없음
밖    **바이트를 안 센다** — 무엇을 쪼갤지는 사람이 정한다(원칙 ⑥).
      **브라우저를 안 띄운다** — 서비스 워커가 실제로 캐시하는가는 관문 밖이고,
      그 사실은 `tools/naviweight.py` 의 `밖` 칸이 든다.
      **글자가 예쁜가는 안 본다** — 글꼴 선택은 사람의 판단이다.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVI = ROOT / "web" / "navi"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_t", ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


NW = _load("naviweight")


# ── ① 밖에 기대는 것 ───────────────────────────────────────────

def test_every_outside_host_is_declared_with_a_reason():
    """선언 없는 바깥 의존이 없다. **사유 없는 이름은 선언이 아니다.**"""
    for host in NW.hosts():
        assert host in NW.ALLOWED, f"`{host}` 가 선언에 없다"
        assert len(NW.ALLOWED[host]) > 30, f"`{host}` 의 사유가 너무 짧다 — 무엇이 죽는지 적어라"


def test_the_two_that_broke_offline_are_gone():
    """★ W13-4 의 실물. 이 둘이 돌아오면 지하에서 도로 이름이 사라진다."""
    h = NW.hosts()
    assert "demotiles.maplibre.org" not in h, "지도 글자가 다시 남의 서버로 갔다"
    assert "cdn.jsdelivr.net" not in h, "글꼴 CSS 가 다시 외부 CDN 으로 갔다"


def test_a_new_outside_host_turns_it_red(tmp_path: Path, monkeypatch):
    """★ 반대 방향. 없으면 **항상 통과하는 검사**가 된다(§69)."""
    fake = tmp_path / "navi"
    (fake / "src").mkdir(parents=True)
    (fake / "src" / "x.ts").write_text('const U = "https://evil.example.com/a";\n', encoding="utf-8")
    (fake / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(NW, "NAVI", fake)
    # ★ 2026-10-03. 종전 `"evil.example.com" in NW.hosts()`. `hosts()` 는 호스트
    #   **목록**이라 `in` 이 정확 일치인데, 꼴만 보면 부분문자열 검사와 구별이
    #   안 된다(CodeQL `py/incomplete-url-substring-sanitization`). 정확 일치를
    #   정확 일치로 적는다 — 덤으로 `a.evil.example.com` 이 들어와도 안 속는다.
    assert any(h == "evil.example.com" for h in NW.hosts()), "새 바깥 호스트를 못 잡는다"


def test_a_commented_out_url_is_not_counted(tmp_path: Path, monkeypatch):
    """★ 주석의 옛 주소를 호출로 세면, 왜 걷었는지를 적을 수가 없게 된다."""
    fake = tmp_path / "navi"
    (fake / "src").mkdir(parents=True)
    (fake / "src" / "x.ts").write_text(
        " * 종전에는 https://demotiles.maplibre.org 였다 — 걷었다\n// https://a.b\nconst A = 1;\n",
        encoding="utf-8")
    (fake / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(NW, "NAVI", fake)
    assert NW.hosts() == {}, "주석에 적힌 주소를 호출로 센다"


# ── ② 오프라인 셋 ──────────────────────────────────────────────

def test_the_glyphs_live_in_the_repo():
    """지도 글자가 저장소 안에 있다. **이것이 W13-4 의 증표다.**"""
    d = ROOT / "web" / "fonts"
    pbf = sorted(d.rglob("*.pbf"))
    assert pbf, "web/fonts 에 글자 파일이 없다 — 오프라인에서 도로 이름이 사라진다"
    for p in pbf:
        assert p.stat().st_size > 0, f"{p.name} 이 비었다"
    stacks = {p.parent.name for p in pbf}
    src = (NAVI / "src" / "components" / "layers.ts").read_text(encoding="utf-8")
    for s in stacks:
        assert s in src, f"글자 묶음 `{s}` 를 코드가 안 부른다 — 이름과 실물이 갈렸다"


def test_the_glyph_url_is_relative():
    """★ 절대 주소면 배포와 로컬 중 한쪽이 404 다(`../data/` 와 같은 사유)."""
    src = (NAVI / "src" / "components" / "layers.ts").read_text(encoding="utf-8")
    line = next(ln for ln in src.splitlines() if ln.startswith("export const GLYPHS"))
    assert "http" not in line, "글자 주소가 절대 URL 이다"
    assert "{fontstack}" in line and "{range}" in line, "MapLibre 글자 주소 꼴이 아니다"


def test_the_service_worker_prefers_network_for_judgment_data():
    """★ 판정 데이터를 캐시 먼저로 두면 **틀린 답**을 보여 준다.

    폭 판정이 바뀌었는데 옛것을 그리면 그것은 오프라인 지원이 아니다.
    """
    sw = (NAVI / "public" / "sw.js").read_text(encoding="utf-8")
    assert "/data/" in sw, "판정 데이터를 따로 안 가른다"
    i_data, i_shell = sw.index("isData"), sw.index("caches.open")
    assert i_data < len(sw) and i_shell < len(sw)
    assert "await fetch(req)" in sw, "망 먼저 갈래가 없다"
    assert "cache.match(req)" in sw, "캐시 되돌림이 없다"


def test_the_service_worker_is_registered():
    src = (NAVI / "src" / "main.tsx").read_text(encoding="utf-8")
    assert "serviceWorker" in src, "파일만 있고 등록을 안 한다"
    assert "catch" in src.split("serviceWorker", 1)[1], (
        "등록 실패를 안 삼킨다 — 워커가 없다고 내비가 안 뜨면 그것이 더 나쁘다")


def test_the_manifest_and_404_are_there():
    m = json.loads((NAVI / "public" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["display"] == "standalone", "설치형으로 안 열린다"
    assert m.get("lang") == "ko"
    h = (ROOT / "web" / "404.html").read_text(encoding="utf-8")
    assert "http" not in h.split("<style>")[0] or "https://" not in h, (
        "없는 주소 화면이 외부를 부른다 — 오프라인에서 그것도 안 뜬다")
    for door in ("/fire-lane/", "/fire-lane/navi/"):
        assert door in h, f"404 화면에 `{door}` 문이 없다"


# ── ③ 번들 ─────────────────────────────────────────────────────

def test_the_bundle_is_split():
    """W13-3. 지도 엔진과 React 를 갈랐다 — 판정을 고쳐도 1MB 를 다시 안 받는다."""
    cfg = (NAVI / "vite.config.ts").read_text(encoding="utf-8")
    assert "manualChunks" in cfg, "청크를 안 가른다"
    for want in ("maplibre", "react"):
        assert f'"{want}"' in cfg, f"`{want}` 청크 선언이 없다"


def test_the_entry_ratchet_is_declared_and_wired():
    """★ **이 시험은 빌드본을 안 읽는다.**

    2026-09-30 실기. 종전에는 `dist` 를 읽어 래칫과 댔는데, `verify.sh` 의
    「내비 빌드」가 pytest **뒤(65/81)** 에 있어 pytest(4/81)는 **패치 적용 전
    빌드본**을 본다. 시험이 단계 순서에 기댄 것이고, 그렇게 붙은 빨간불은
    배치의 결함이 아니라 **관문 자신의 결함**이라 제일 찾기 어렵다(§316 ③).

    ★ 빌드본을 재는 일은 `naviweight --build` 하나가 한다. 여기가 무는 것은
      「선언이 있고 관문에 배선됐는가」 — 소스만 보면 답이 나오는 것들이다.
    """
    assert isinstance(NW.ENTRY_KB, int) and NW.ENTRY_KB > 0, "래칫이 수가 아니다"
    assert "ENTRY_KB" not in NW.RATCHETS, (
        "`ENTRY_KB` 를 래칫 규약에 태웠다 — 어디서나 잴 수 있는 수가 아니다(§313-1 ①)")
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert "npm run -s build" in sh, "관문이 빌드본을 안 짓는다 — 새 클론이 늘 빨갛다"
    assert sh.index("npm run -s build") < sh.index("tools/naviweight.py --build"), \
        "짓기 전에 잰다 — 순서가 뒤집혔다"


# ── ④ 배선 ─────────────────────────────────────────────────────

def test_verify_runs_all_three_axes():
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    for want in ("tools/naviweight.py", "tools/naviweight.py --build", "glyphs -- --check"):
        assert want in sh, f"verify.sh 가 `{want}` 를 안 부른다"


def test_the_source_axis_is_in_ci():
    yml = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
    assert "tools/naviweight.py" in yml, "바깥 의존 관문이 CI 에 없다"


def test_the_selftest_is_alive():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "naviweight.py"), "--selftest"],  # noqa: S603 — 트리 안의 도구다
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


# ── ⑤ 빨강의 이름 (§313) ───────────────────────────────────────

def test_a_red_test_name_is_recorded():
    """★ 9분을 돌려 빨간불을 얻고 **무엇이 빨간지는 안 적는** 결함(§313)."""
    dms = _load("dms")
    got = dms._failed_names(
        "FAILED tests/test_a.py::test_x - AssertionError\n"
        "ERROR tests/test_b.py::test_y\n"
        "1 failed, 1957 passed in 543.05s\n")
    assert got == ["tests/test_a.py::test_x", "tests/test_b.py::test_y"]
    assert dms._failed_names("1958 passed in 500s") == [], "초록인데 이름을 만든다"
    src = (ROOT / "tools" / "dms.py").read_text(encoding="utf-8")
    assert '"red": _failed_names(txt)' in src, "봉인이 그 이름을 안 담는다"
