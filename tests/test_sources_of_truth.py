#!/usr/bin/env python3
"""
test_sources_of_truth.py — `docs/SOURCES_OF_TRUTH.yaml` 이 든 사실마다 정본과 따르는 자리가 같은가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §218-6 · 계급 가드 2). uv 판이 CI 둘 · Dockerfile 에 0.12.13 으로
박혀 있는데 `.devcontainer/setup.sh` 의 대체 설치만 판이 없었다 — 그날의 최신을 받았다.
`render_figures` 는 TRUCK 은 정본에서 읽으면서 여유선 7.0 은 글자로 박았다. 같은 값이
여러 파일에 사는 것을 막을 수 없는 자리(YAML · Dockerfile · 셸)는 **목록으로 적고 맞춘다.**

  ① owner regex 가 정확히 한 번 걸린다(집이 하나다)
  ② consumer 마다 값(has) · 정본 참조(ref) · 비교(regex+cmp) 가 맞다
  ③ scan 범위 안에서 pins 자리는 전부 값과 같고, 그 파일은 목록에 있다
  ④ exclusive 면 값 literal 이 목록 밖 파일에 없다

IN    docs/SOURCES_OF_TRUTH.yaml · 그것이 가리키는 파일
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SOT = ROOT / "docs" / "SOURCES_OF_TRUTH.yaml"
FACTS: dict = yaml.safe_load(SOT.read_text(encoding="utf-8"))["facts"]


class _V(str):
    """`{v}` 는 적힌 그대로, `{v:g}` 처럼 서식이 붙으면 수로 서식한다."""
    def __format__(self, spec: str) -> str:
        return str(self) if not spec else format(float(self), spec)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _ver(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", s))


def owner_value(fact: dict) -> str:
    o = fact["owner"]
    hits = re.findall(o["regex"], _read(o["file"]), re.M)
    assert len(hits) == 1, (f"정본 {o['file']} 에서 {o['regex']!r} 가 {len(hits)}번 걸린다 — "
                            "집이 하나가 아니거나 서식이 바뀌었다")
    return hits[0]


def _scan_files(fact: dict) -> list[Path]:
    out: set[Path] = set()
    for g in fact.get("scan", []):
        out |= {p for p in ROOT.glob(g) if p.is_file()}
    return sorted(out)


def _listed(fact: dict) -> set[str]:
    return {fact["owner"]["file"], *(c["file"] for c in fact["consumers"])}


def consumer_errors(fact: dict, v: str) -> list[str]:
    bad = []
    for c in fact["consumers"]:
        txt = _read(c["file"])
        if "has" in c:
            want = c["has"].format(v=_V(v))
            if _squash(want) not in _squash(txt):
                bad.append(f"{c['file']} 에 {want!r} 가 없다")
        elif "ref" in c:
            if _squash(c["ref"]) not in _squash(txt):
                bad.append(f"{c['file']} 가 정본을 읽지 않는다 — {c['ref']!r} 가 없다")
        else:
            hits = re.findall(c["regex"], txt, re.M)
            cmp = c.get("cmp", "==")
            ok = hits and all((_ver(h) >= _ver(v)) if cmp == ">=" else h == v for h in hits)
            if not ok:
                bad.append(f"{c['file']} 의 {hits or '(못 찾음)'} 가 정본 {v} 와 {cmp} 가 아니다")
    return bad


def scan_errors(fact: dict, v: str) -> list[str]:
    bad, listed = [], _listed(fact)
    for p in _scan_files(fact):
        rel = p.relative_to(ROOT).as_posix()
        try:
            txt = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pin in fact.get("pins", []):
            for m in re.finditer(re.escape(pin["find"]), txt):
                got = re.compile(pin["regex"]).match(txt, m.start())
                line = txt[: m.start()].count("\n") + 1
                if not got or got.group(1) != v:
                    bad.append(f"{rel}:{line} 이 판을 {got.group(1) if got else '안 적었다'!s} "
                               f"— 정본은 {v}")
                elif rel not in listed:
                    bad.append(f"{rel}:{line} 에 값이 있는데 목록(consumers)에 없다")
        if fact.get("exclusive") and rel not in listed and v in txt:
            bad.append(f"{rel} 에 {v} 가 literal 로 있는데 목록에 없다")
    return bad


@pytest.mark.parametrize("name", sorted(FACTS))
def test_fact_consumers_follow_owner(name: str):
    fact = FACTS[name]
    v = owner_value(fact)
    bad = consumer_errors(fact, v) + scan_errors(fact, v)
    assert not bad, (f"사실 {name!r} (정본 {fact['owner']['file']} = {v}) 이 갈렸다:\n  "
                     + "\n  ".join(bad)
                     + "\n  정본을 고쳤으면 따르는 자리를 같이 고치고, 새 자리면 "
                       "docs/SOURCES_OF_TRUTH.yaml consumers 에 더한다.")


def test_the_file_covers_the_declared_facts():
    """빈 그물 금지 — 맡은 사실이 목록에서 빠지면 검사도 조용히 빠진다."""
    need = {"uv", "node", "python", "pytest", "coverage_floor",
            "truck_m", "park_m", "cctv_range_m", "code_owner", "font_stack"}
    assert need <= set(FACTS), f"빠진 사실: {sorted(need - set(FACTS))}"


# ── 검사가 무는가 ──────────────────────────────────────────────

def test_unpinned_installer_and_stray_literal_are_caught(tmp_path, monkeypatch):
    """판 없는 설치 줄 · 목록 밖 literal · 어긋난 consumer 가 각각 잡힌다."""
    (tmp_path / "Dockerfile").write_text("COPY --from=ghcr.io/astral-sh/uv:9.9.9 /uv /bin/\n")
    (tmp_path / "setup.sh").write_text("curl -LsSf https://astral.sh/uv/install.sh | sh\n")
    (tmp_path / "other.yml").write_text("# uv 9.9.9 를 쓴다\n")
    (tmp_path / "ci.yml").write_text('version: "9.9.8"\n')
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    fact = {"owner": {"file": "Dockerfile", "regex": r"astral-sh/uv:([\w.]+)"},
            "consumers": [{"file": "setup.sh", "has": "astral.sh/uv/{v}/install.sh"},
                          {"file": "ci.yml", "has": 'version: "{v}"'}],
            "scan": ["*"], "exclusive": True,
            "pins": [{"find": "astral.sh/uv/", "regex": r"astral\.sh/uv/([\d.]+)/install\.sh"}]}
    v = owner_value(fact)
    assert v == "9.9.9"
    errs = consumer_errors(fact, v) + scan_errors(fact, v)
    joined = "\n".join(errs)
    assert "setup.sh 에" in joined and "ci.yml 에" in joined, joined
    assert "안 적었다" in joined, joined
    assert "other.yml 에 9.9.9" in joined, joined
