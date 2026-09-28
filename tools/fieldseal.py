#!/usr/bin/env python3
"""
fieldseal.py — `data/field` 의 **무결성 지문**. 재취득 불가 층의 유일한 증표다.

    uv run python tools/fieldseal.py            대조 (verify · CI 가 이것을 돈다)
    uv run python tools/fieldseal.py --write    지문을 다시 뜬다 (★ 사람이 친다)
    uv run python tools/fieldseal.py --selftest 판별식이 살아 있나

── 왜 생겼나 (PLAN §13 W13-7 · DECISIONS §288) ─────────────────
`data/field` 는 **재취득 불가**다(`layers.field.regenerable: false`). 사람이
현장에 나가 잰 값이고 다시 가서 재면 다른 날의 값이 된다. 그런데 —

    data/processed   `_manifest.json` 이 계보를 든다
    판정             `segments.fingerprint.json` 이 지문을 든다
    data/field       **없다**

`git` 이 「바뀌었다」는 알려준다. 그러나 **「그날 잰 그 파일인가」는 아무도
안 물었다.** 둘은 다르다 — git 은 HEAD 와의 차이를 말할 뿐, 어느 날 어떤
내용이 정본이었는지를 선언하지 않는다.

★ 2026-09-28 에 실제로 났다. CLI 전수에 모르는 깃발을 하나씩 줘 보다가
  (§283-2) 도구들이 그것을 무시하고 **일을 해서** `obs_points.csv` ·
  `sample_segments.csv` · `fieldsheet.md` 가 덮어써졌다. `git status` 를
  우연히 본 사람이 되돌렸다. **우연에 기대고 있었다.**

★ `data/field` 는 커밋되므로 **CI 가 이 검사를 돌 수 있다.** 레이크가
  필요 없는, 재생성 불가 층의 관문이다.

IN    data/field/**
OUT   data/golden/field.fingerprint.json
PARAM 없음
밖    **값이 옳은가는 안 본다.** 관측점이 실제 그 자리인지, 폭 값이 맞는지는
      `tests/test_fieldsheet.py` 와 실측 대장이 본다. 여기가 드는 것은
      「선언한 그 파일 그대로인가」 하나다.
      **재생성도 안 한다** — 재생성 불가 층이라 애초에 못 한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELD = ROOT / "data" / "field"
SEAL = ROOT / "data" / "golden" / "field.fingerprint.json"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def survey() -> dict[str, dict]:
    """지금 실물. 이름 → {sha256, bytes, lines}."""
    out: dict[str, dict] = {}
    for p in sorted(FIELD.rglob("*")):
        if not p.is_file() or p.name.startswith("."):
            continue
        b = p.read_bytes()
        out[p.relative_to(FIELD).as_posix()] = {
            "sha256": _sha(p),
            "bytes": len(b),
            # ★ 줄 수를 같이 든다. sha 만 있으면 「무엇이 달라졌나」에
            #   답을 못 하고, 사람은 답 없는 빨강을 오래 안 본다.
            "lines": b.count(b"\n"),
        }
    return out


def load() -> dict[str, dict]:
    if not SEAL.is_file():
        return {}
    return json.loads(SEAL.read_text(encoding="utf-8")).get("files", {})


def diff(now: dict[str, dict], was: dict[str, dict]) -> list[str]:
    """(바뀐 것, 사라진 것, 새로 생긴 것)을 사람이 읽는 줄로."""
    out: list[str] = []
    for k in sorted(set(was) - set(now)):
        out.append(f"사라졌다  {k}  — 재취득 불가 층이다. 되돌려라")
    for k in sorted(set(now) - set(was)):
        out.append(f"새로 생겼다  {k}  ({now[k]['lines']}행) — 실측이면 "
                   f"`--write` 로 등재하고, 아니면 이 층에서 치워라")
    for k in sorted(set(now) & set(was)):
        a, b = was[k], now[k]
        if a.get("sha256") == b["sha256"]:
            continue
        out.append(f"바뀌었다  {k}  — {a.get('lines', '?')}행 "
                   f"{a.get('bytes', '?')}B → {b['lines']}행 {b['bytes']}B")
    return out


def check() -> int:
    was = load()
    if not was:
        print(f"✗ 지문이 없다 — {SEAL.relative_to(ROOT)}")
        print("  `--write` 로 한 번 떠라. **없는 것은 통과가 아니다.**")
        return 1
    now = survey()
    bad = diff(now, was)
    if bad:
        print(f"✗ `data/field` 가 지문과 다르다 {len(bad)}건")
        for line in bad:
            print(f"    {line}")
        print("\n  ★ **재취득 불가 층이다.** 다시 가서 재면 다른 날의 값이 된다.")
        print("  의도한 변경이 아니면 `git checkout -- data/field` 로 되돌려라.")
        print("  새로 잰 값이면 `--write` 로 지문을 다시 뜨고 **무엇을 언제")
        print("  잰 것인지**를 커밋에 적어라.")
        return 1
    print(f"✓ `data/field` {len(now)}개 파일이 지문과 같다")
    return 0


def write() -> int:
    now = survey()
    was = load()
    if was and (bad := diff(now, was)):
        print(f"지문을 다시 뜬다 — 바뀌는 것 {len(bad)}건")
        for line in bad:
            print(f"    {line}")
    SEAL.parent.mkdir(parents=True, exist_ok=True)
    SEAL.write_text(json.dumps(
        {"what": "data/field 무결성 지문 — 재취득 불가 층. tools/fieldseal.py 가 쓴다",
         "files": now}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"✓ 지문 {len(now)}개 → {SEAL.relative_to(ROOT)}")
    return 0


def selftest() -> int:
    """★ 판별식이 실제로 셋을 가르는가. 빈 그물이면 조용히 통과한다."""
    bad = []
    base = {"a.csv": {"sha256": "x", "bytes": 10, "lines": 2}}
    if diff(base, base):
        bad.append("같은 것을 다르다고 한다")
    if not diff({"a.csv": {"sha256": "y", "bytes": 10, "lines": 2}}, base):
        bad.append("sha 가 바뀐 것을 못 잡는다")
    if not diff({}, base):
        bad.append("사라진 파일을 못 잡는다")
    if not diff({**base, "b.csv": {"sha256": "z", "bytes": 1, "lines": 0}}, base):
        bad.append("새로 생긴 파일을 못 잡는다")
    # ★ 실물에서도 재 본다. 0개를 재면 「전부 같다」가 거짓이 된다.
    if len(survey()) < 2:
        bad.append(f"실물을 {len(survey())}개만 읽었다 — 조사가 죽었다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print(f"✓ 자기검사 — 판별식이 바뀜 · 사라짐 · 새로 생김 셋을 가른다 "
          f"(실물 {len(survey())}개)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="지문을 다시 뜬다 (★ 새로 잰 값일 때만)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return write() if a.write else check()


if __name__ == "__main__":
    sys.exit(main())
