#!/usr/bin/env python3
"""
test_prune_landing.py — **짝을 찾되 레이크를 통째로 해시하지 않는다.**
  (DECISIONS §536-1)

── 왜 생겼나 ──────────────────────────────────────────────────
반입 사슬 4단계(`--prune-landing`)가 WSL 에서 역추적을 토하고 죽었다 —
`OSError: [Errno 12] Cannot allocate memory`. 자리는 `sha256()` 안이었지만
**결함은 호출부**였다. landing 에 파일이 한 개 있을 때도 raw 91개 3.97 GB
전부를 해시했다.

내용이 같으면 크기도 같다. 그러므로 크기가 안 맞는 raw 파일은 **짝이 될 수
없다** — 걸러도 답이 안 바뀐다. 이 파일은 그 둘을 같이 잰다: ① 걸러도 짝을
찾는다(손실 없음) ② 안 맞는 것은 **해시하지 않는다**(일을 안 한다).

IN    tools/acquire.py
OUT   없음 (검사)
PARAM 없음
밖    **레이크를 안 본다.** tmp 에 작은 레이크를 세워 돌린다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("acquire", ROOT / "tools/acquire.py")
assert _spec and _spec.loader
acquire = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = acquire
_spec.loader.exec_module(acquire)


def _lake(tmp: Path) -> tuple[Path, Path]:
    raw, landing = tmp / "raw", tmp / "landing"
    (raw / "gjcity").mkdir(parents=True)
    landing.mkdir()
    return raw, landing


def _wire(monkeypatch, tmp: Path, raw: Path, landing: Path) -> list[Path]:
    """경로를 tmp 로 돌리고 해시된 파일을 적어 돌려준다."""
    monkeypatch.setattr(acquire, "RAW", raw)
    monkeypatch.setattr(acquire, "LANDING", landing)
    monkeypatch.setattr(acquire, "QUARANTINE", tmp / "_quarantine")
    seen: list[Path] = []
    real = acquire.sha256

    def spy(p, *a, **k):
        seen.append(Path(p))
        return real(p, *a, **k)

    monkeypatch.setattr(acquire, "sha256", spy)
    return seen


# ── ① 걸러도 짝을 찾는다 ───────────────────────────────────────
def test_a_landing_file_whose_twin_is_in_raw_is_removed(tmp_path, monkeypatch):
    """★ 크기 사전 필터가 **진짜 짝을 가리지 않는다.**

    사전 필터를 잘못 끼우면 조용히 아무것도 못 지운다 — 아무 말 없이
    「지운 용량 0 B」 가 되므로 사람이 못 알아챈다. 그래서 잰다.
    """
    raw, landing = _lake(tmp_path)
    body = b"oneway-table-rows\n" * 7
    (raw / "gjcity" / "gjcity_oneway_donggu_jngj-donggu_20261008.xlsx").write_bytes(body)
    orig = landing / "0. 일방통행로 현황(공개).xlsx"
    orig.write_bytes(body)

    _wire(monkeypatch, tmp_path, raw, landing)
    assert acquire.cmd_prune_landing(dry=False) == 0
    assert not orig.exists(), "내용이 같은 원본인데 안 지웠다"


def test_a_landing_file_with_no_twin_is_kept(tmp_path, monkeypatch):
    """짝이 없으면 남긴다. 「복사됐다」는 확인 없이 지우면 그게 소실이다."""
    raw, landing = _lake(tmp_path)
    (raw / "gjcity" / "other.csv").write_bytes(b"a" * 40)
    lone = landing / "아직 안 들어간 것.hwpx"
    lone.write_bytes(b"b" * 41)

    _wire(monkeypatch, tmp_path, raw, landing)
    assert acquire.cmd_prune_landing(dry=False) == 0
    assert lone.exists(), "짝이 없는데 지웠다 — 유일본을 날렸다"


# ── ② 안 맞는 것은 해시하지 않는다 ─────────────────────────────
def test_raw_files_of_a_different_size_are_never_hashed(tmp_path, monkeypatch):
    """★ **ENOMEM 으로 죽은 자리.** 큰 파일은 읽지도 않아야 한다.

    크기가 안 맞으면 짝이 될 수 없으므로 해시할 이유가 없다. 이 자가 울면
    누군가 사전 필터를 뺀 것이고, 레이크가 커지는 만큼 4단계가 다시
    메모리에서 죽는다.
    """
    raw, landing = _lake(tmp_path)
    body = b"twin\n" * 3
    twin = raw / "gjcity" / "twin.csv"
    twin.write_bytes(body)
    big = raw / "gjcity" / "its_nodelink_kr.zip"
    big.write_bytes(b"x" * 9999)          # 크기가 안 맞는다
    (landing / "원본.csv").write_bytes(body)

    seen = _wire(monkeypatch, tmp_path, raw, landing)
    assert acquire.cmd_prune_landing(dry=False) == 0
    assert big not in seen, "크기가 안 맞는 raw 파일을 해시했다"
    assert twin in seen, "크기가 맞는 짝 후보를 안 해시했다"


def test_a_big_raw_file_is_hashed_once_a_landing_file_matches_its_size(
        tmp_path, monkeypatch):
    """★ 「크기 필터」와 「큰 건 건너뛴다」를 **가른다.**

    앞의 자는 큰 파일을 안 읽는 것만 본다. 그것만으로는 누가 크기 상한을
    박아도 통과한다 — 그러면 큰 파일의 짝은 영원히 안 지워진다. 그래서
    landing 쪽 크기를 **그 큰 파일에 맞추면** 반드시 해시해야 한다.
    """
    raw, landing = _lake(tmp_path)
    body = b"x" * 9999
    big = raw / "gjcity" / "its_nodelink_kr.zip"
    big.write_bytes(body)
    orig = landing / "nodelink 원본.zip"
    orig.write_bytes(body)

    seen = _wire(monkeypatch, tmp_path, raw, landing)
    assert acquire.cmd_prune_landing(dry=False) == 0
    assert big in seen, "크기가 맞는데 큰 파일을 건너뛰었다 — 크기 상한이 박혔다"
    assert not orig.exists(), "짝이 맞는데 안 지웠다"


# ── ③ 기계가 모자랄 때 (DECISIONS §536) ────────────────────────
def test_a_hash_backs_off_to_a_smaller_chunk_on_enomem(tmp_path, monkeypatch):
    """★ 큰 청크가 ENOMEM 이면 작은 청크로 **같은 답**을 낸다.

    청크 무관성은 `hashing` 이 2026-09-13 에 이미 선언한 것이다. 선언이
    있으니 물러서도 답이 안 바뀐다 — 규약이 고치는 길을 미리 열어둔 자리다.
    """
    import errno

    from firelane import hashing

    f = tmp_path / "big.bin"
    f.write_bytes(b"ENOMEM" * 5000)
    want = hashing.sha256(f, chunk=hashing.SMALL)

    real = hashing._digest
    tried: list[int] = []

    def flaky(p, chunk):
        tried.append(chunk)
        if chunk > hashing.SMALL:
            raise OSError(errno.ENOMEM, "Cannot allocate memory")
        return real(p, chunk)

    monkeypatch.setattr(hashing, "_digest", flaky)
    assert hashing.sha256(f) == want, "물러선 뒤 답이 달라졌다"
    assert tried == [hashing.CHUNK, hashing.SMALL], f"물러선 자리가 다르다 {tried}"


def test_a_hash_that_cannot_back_off_any_further_names_the_machine(tmp_path,
                                                                   monkeypatch):
    """작은 청크로도 못 읽으면 **기계가 모자란 것**이라고 말하고 멈춘다.

    역추적을 토하면 사람이 파일 탓을 한다. 어느 쪽이 모자란지 말해야 한다.
    """
    import errno

    import pytest

    from firelane import hashing

    f = tmp_path / "big.bin"
    f.write_bytes(b"z" * 100)

    def always(p, chunk):  # noqa: ARG001
        raise OSError(errno.ENOMEM, "Cannot allocate memory")

    monkeypatch.setattr(hashing, "_digest", always)
    with pytest.raises(hashing.NoMemory) as e:
        hashing.sha256(f)
    assert "메모리" in str(e.value)


def test_a_hash_does_not_swallow_other_oserrors(tmp_path, monkeypatch):
    """ENOMEM 이 아닌 OSError 는 **그대로 올린다.** 권한 오류를 메모리로
    둔갑시키면 사람이 엉뚱한 곳을 본다."""
    import errno

    import pytest

    from firelane import hashing

    f = tmp_path / "x.bin"
    f.write_bytes(b"z")

    def denied(p, chunk):  # noqa: ARG001
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(hashing, "_digest", denied)
    with pytest.raises(OSError) as e:
        hashing.sha256(f)
    assert e.value.errno == errno.EACCES
    assert not isinstance(e.value, hashing.NoMemory)
