"""`lakecheck L3` 이 **레이크를 전부 해시하지 않는지** 잰다.  (§293 · PLAN #134)

★ 왜 이 파일이 따로 있나 (2026-09-28). L3 은 「입구를 안 거친 원본이 밖에
  있나」를 센다. 판정은 맞았는데 **재는 값이 레이크 크기에 비례했다** —

    have = {p.name for p in D.rglob("*") if p.is_file()}
    fp = {_sha(p) for p in D.rglob("*") if p.is_file() and p.stat().st_size > 100_000}

  레이크를 두 번 훑고 100KB 넘는 것을 전부 해시한다. 실기 레이크는 2.5GB 라
  이 한 프로브가 23초를 먹었고, `verify.sh` 가 단계를 병렬로 돌리는 WSL 에서
  `OSError: [Errno 12] Cannot allocate memory` 로 **죽었다.** 결함이 0건인
  레이크에서 배달이 멈췄다.

  고친 판은 후보를 먼저 고르고 **크기가 겹치는 것만** 해시한다. 같은 내용이면
  크기도 같으니 판정은 글자 그대로 같다. 여기 잠그는 것은 그 두 가지다 —
  **판정이 안 바뀌었다**와 **읽는 바이트가 후보에만 비례한다.**

★ 속도를 세지 않는다. 세는 것은 **해시한 파일**이다. 초로 재는 시험은
  기계에 따라 흔들려서 사람이 끄게 된다(§69).

IN    tools/lakecheck.py L3
OUT   없음
밖    100KB 문턱 · DATA_EXT 어휘 · `landing_disposition` 글롭 규칙은 여기서
      판단하지 않는다. 그것은 L3 의 선언이고 여기 잠그는 것은 그 선언을
      **어떤 값을 치르고 지키는가**다.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "tools" / "lakecheck.py"
BIG = 200_000        # 100KB 문턱을 넘는다


@pytest.fixture
def lc():
    """경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)."""
    spec = importlib.util.spec_from_file_location("lakecheck_l3t", SRC)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    m.HITS.clear()
    return m


@pytest.fixture
def counted(lc, monkeypatch):
    """`_sha` 를 세는 판으로 갈아끼운다. 반환값은 그대로다."""
    seen: list[pathlib.Path] = []
    real = lc._sha

    def spy(p: pathlib.Path) -> str:
        seen.append(p)
        return real(p)

    monkeypatch.setattr(lc, "_sha", spy)
    return seen


def _write(p: pathlib.Path, body: bytes) -> pathlib.Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body)
    return p


def _lake(tmp: pathlib.Path, n_big: int = 5) -> pathlib.Path:
    """raw 에 서로 크기가 다른 큰 파일 여럿. 후보와는 하나도 안 겹친다."""
    D = tmp / "data"
    for i in range(n_big):
        _write(D / "raw" / f"원본{i}.zip", b"L" * (BIG + i))
    (D / "landing").mkdir(parents=True, exist_ok=True)
    return D


# ── ① 판정이 안 바뀌었다 ────────────────────────────────────────


def test_레이크에_내용이_같은_것이_있으면_개명해도_안_운다(lc, tmp_path):
    """반입하며 개명한다. 이름이 아니라 내용으로 봐야 한다."""
    D = _lake(tmp_path)
    body = "같은내용".encode() * 50_000
    _write(D / "raw" / "gjcity" / "반입된_이름.zip", body)
    down = tmp_path / "Downloads"
    _write(down / "받은_이름.zip", body)

    lc.l3(D, {}, [down])
    assert lc.HITS == []


def test_레이크에_없으면_운다(lc, tmp_path):
    D = _lake(tmp_path)
    down = tmp_path / "Downloads"
    _write(down / "처음_보는_것.zip", b"X" * BIG)

    lc.l3(D, {}, [down])
    assert len(lc.HITS) == 1
    assert "처음_보는_것.zip" in lc.HITS[0]["what"]
    # ★ 자리를 어느 폴더에서 봤는지 적어야 사람이 찾아간다
    assert str(down) in lc.HITS[0]["detail"]


def test_이름이_같으면_내용을_안_보고_넘긴다(lc, tmp_path):
    """종전 판의 `have` 규칙이다. 판정을 안 바꾼다."""
    D = _lake(tmp_path)
    _write(D / "raw" / "같은이름.zip", b"A" * BIG)
    down = tmp_path / "Downloads"
    _write(down / "같은이름.zip", b"B" * BIG)   # 내용은 다르다

    lc.l3(D, {}, [down])
    assert lc.HITS == []


def test_처분이_적힌_것은_안_운다(lc, tmp_path):
    D = _lake(tmp_path)
    down = tmp_path / "Downloads"
    _write(down / "남의프로젝트_덤프.csv", b"X" * BIG)
    y = {"landing_disposition": {"items": [
        {"file": "남의프로젝트_*.csv", "why": "다른 과제 파일이다"}]}}

    lc.l3(D, y, [down])
    assert lc.HITS == []


def test_사유가_없으면_처분이_아니다(lc, tmp_path):
    """글롭 한 줄로 L3 전체를 끌 수 있으니 사유를 강제한다."""
    D = _lake(tmp_path)
    down = tmp_path / "Downloads"
    _write(down / "아무거나.zip", b"X" * BIG)
    y = {"landing_disposition": {"items": [{"file": "*", "why": "  "}]}}

    lc.l3(D, y, [down])
    assert len(lc.HITS) == 1


def test_scan_이_폴더가_아니면_운다(lc, tmp_path):
    D = _lake(tmp_path)
    lc.l3(D, {}, [tmp_path / "없는폴더"])
    assert len(lc.HITS) == 1
    assert "폴더가 아니다" in lc.HITS[0]["what"]


# ── ② 읽는 바이트가 후보에만 비례한다 ───────────────────────────


def test_후보가_없으면_레이크를_한_건도_해시하지_않는다(lc, counted, tmp_path):
    """제일 흔한 경우다 — 다운로드 폴더가 깨끗하면 할 일이 없다."""
    D = _lake(tmp_path, n_big=8)
    down = tmp_path / "Downloads"
    down.mkdir()
    _write(down / "작은것.csv", b"x" * 10)          # 문턱 아래
    _write(down / "코드.py", b"y" * BIG)            # 어휘 밖

    lc.l3(D, {}, [down])
    assert lc.HITS == []
    assert counted == [], f"후보가 0인데 {len(counted)}건을 해시했다"


def test_크기가_안_겹치는_레이크_파일은_해시하지_않는다(lc, counted, tmp_path):
    """★ 이것이 ENOMEM 을 낸 줄이다. 되돌리면 여기서 걸린다."""
    D = _lake(tmp_path, n_big=8)                    # 크기 BIG+0 .. BIG+7
    match = _write(D / "raw" / "겹치는것.zip", b"M" * (BIG + 500))
    down = tmp_path / "Downloads"
    _write(down / "후보.zip", b"M" * (BIG + 500))    # 같은 크기 · 같은 내용

    lc.l3(D, {}, [down])
    assert lc.HITS == []

    lake_hashed = [p for p in counted if D in p.parents or p.parent == D]
    assert lake_hashed == [match], (
        f"크기가 겹치는 한 건만 해시해야 하는데 {len(lake_hashed)}건을 해시했다: "
        f"{[p.name for p in lake_hashed]}")


def test_후보_하나당_레이크를_다시_훑지_않는다(lc, tmp_path, monkeypatch):
    """종전 판은 `D.rglob` 를 두 번 불렀다. 훑기 자체가 9p 마운트에서 비싸다."""
    D = _lake(tmp_path, n_big=3)
    down = tmp_path / "Downloads"
    for i in range(4):
        _write(down / f"후보{i}.zip", b"C" * (BIG + i))

    walks = []
    real = pathlib.Path.rglob

    def spy(self, pat):
        if self == D:
            walks.append(pat)
        return real(self, pat)

    monkeypatch.setattr(pathlib.Path, "rglob", spy)
    lc.l3(D, {}, [down])
    assert len(lc.HITS) == 4
    assert len(walks) == 1, f"레이크를 {len(walks)}번 훑었다"


# ── ③ 못 잰 것은 결함을 센 것이 아니다 ─────────────────────────


def test_죽은_프로브는_고치는_법을_적는다(lc, tmp_path, monkeypatch, capsys):
    """ENOMEM 을 「레이크에 결함 1건」으로 읽었다. 둘은 다른 일이다."""
    monkeypatch.setattr(lc, "lake", lambda: tmp_path / "data")
    monkeypatch.setattr(lc, "led", lambda: {})
    (tmp_path / "data").mkdir()

    def boom(*a, **k):
        raise OSError(12, "Cannot allocate memory")

    monkeypatch.setattr(lc, "l3", boom)
    monkeypatch.setattr(lc.sys, "argv", ["lakecheck.py"])
    monkeypatch.setattr(lc, "ROOT", tmp_path)

    lc.main()
    dead = [h for h in lc.HITS if "죽었다" in h["what"]]
    assert len(dead) == 1
    assert "못 쟀다" in dead[0]["detail"], "결함을 센 것과 못 잰 것을 안 갈랐다"
    assert dead[0]["fix"], "고치는 법이 비었다"
