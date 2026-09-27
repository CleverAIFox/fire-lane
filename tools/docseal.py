#!/usr/bin/env python3
"""
docseal.py — 문서 절과 그 절이 가리키는 코드에 **정합 도장**을 찍는다.  (§265)

    uv run python tools/docseal.py            무효가 된 도장을 낸다 (rc 1) ← 기본
    uv run python tools/docseal.py status     몇 개가 유효 · 무효 · 미날인인가
    uv run python tools/docseal.py stamp      지금 상태로 도장을 찍는다
    uv run python tools/docseal.py stamp --only DECISIONS/262
    uv run python tools/docseal.py --selftest 판별식이 살아 있나

── 왜 생겼나 (2026-09-27 · DECISIONS §265) ──────────────────────
문서↔코드 강제자가 열일곱인데 **전부 한 방향**이다 — 「문서가 가리킨 것이
실재하는가」. `§262` 는 그 열일곱을 **전부 통과하면서** 거짓이었다.
「`web/navi/src` 의 내용 대조는 golden 소관」 — 수도 맞고 경로도 실재하고
`golden` 도 실재했다. **뜻만 거짓이었다.**

★ 뜻은 기계가 못 읽는다. 그러나 **「누가 언제 확인했는가」는 기록할 수 있고,
  그 확인이 언제 낡았는지는 기계가 안다.** 그것이 봉인의 취지다 — 「안 바뀐다」가
  아니라 **「양쪽 다 안 바뀌었으면 그때의 입증이 아직 유효하다」**.

★ 문서가 자주 바뀌면 도장도 자주 무효가 된다. **그것이 옳은 동작이다** — 자주
  무효가 되는 것과 쓸모없는 것은 다르다. 무효가 잦다는 것은 그 절이 실제로 자주
  흔들린다는 뜻이고, 그 사실 자체가 정보다.

★ `shardseal` 과 같은 원리이고 축만 다르다. 거기는 (원본, 코드 폐포) → 샤드,
  여기는 (절 본문, 그 절이 가리키는 파일) → 절.

── 도장이 무엇을 덮나 ──────────────────────────────────────────
    문서 쪽   그 절의 본문 (다음 같은 깊이 제목 전까지)
    코드 쪽   그 절이 백틱으로 지목한 실재 파일들의 내용

둘 중 **하나라도** 바뀌면 도장이 무효다. 무효는 「틀렸다」가 아니라
**「다시 봐야 한다」**이다 — 사람이 보고 `stamp` 로 다시 찍는다.

IN    docs/*.md (tools/dms.py 의 절 수집) · 그 절이 지목한 파일
OUT   data/golden/docseal.json
PARAM 없음
밖    **뜻이 옳은지는 안 본다.** 이 도구가 아는 것은 「확인한 뒤로 바뀌었는가」
      하나다. 옳은지는 사람이 보고 찍는다 — 그 판단을 기계가 대신하는 척하면
      도장이 거짓 초록이 된다.
      강제자 칸이 없는 절(`blank`)과 부모 칸을 무는 절(`inherit`)은 대상이
      아니다 — 무는 절은 부모의 도장이 덮는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / "data" / "golden" / "docseal.json"

#: 절 본문에서 코드 쪽을 뽑는 정규식. 백틱 안의 **경로꼴**만 본다.
PATH = re.compile(r"`([\w][\w./-]*\.(?:py|sh|ts|tsx|js|mjs|json|ya?ml))(?:::[\w.]+)?`")


def _sections() -> list[dict]:
    """`dms` 가 세는 절. **정본은 거기다** — 여기서 다시 세지 않는다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dms_seal", ROOT / "tools" / "dms.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m       # @dataclass 가 되짚는다 (DECISIONS §258-10)
    spec.loader.exec_module(m)
    return m.scan()["rows"]


def body(rows: list[dict], i: int) -> str:
    """절 본문 — 다음 **같거나 얕은** 깊이의 제목 전까지."""
    r = rows[i]
    lines = (ROOT / r["doc"]).read_text(encoding="utf-8").splitlines()
    end = len(lines)
    for q in rows[i + 1:]:
        if q["doc"] == r["doc"] and q["depth"] <= r["depth"]:
            end = q["line"] - 1
            break
    return "\n".join(lines[r["line"] - 1:end])


def refs(text: str) -> list[str]:
    """그 절이 지목한 **실재하는** 파일. 없는 것은 `tools/refcheck.py` 가 본다."""
    # ★ 도장 파일 자신은 뺀다. 안 빼면 그 파일을 지목한 절이 **찍는 순간 무효**가
    #   된다 — 찍기가 도장 파일을 바꾸고 그 변경이 그 절의 코드 쪽이기 때문이다.
    #   §265 에서 실제로 무한 루프가 났다.
    try:
        me = SEAL.relative_to(ROOT).as_posix()
    except ValueError:       # 도장 파일이 저장소 밖(시험 · 임시 경로)이면 뺄 것이 없다
        me = ""
    return sorted({p for p in PATH.findall(text)
                   if p != me and (ROOT / p).is_file()})


def digest(text: str, files: list[str]) -> str:
    h = hashlib.sha256(text.encode("utf-8"))
    for f in files:
        h.update(f.encode("utf-8"))
        h.update(hashlib.sha256((ROOT / f).read_bytes()).digest())
    return h.hexdigest()[:16]


def survey() -> tuple[dict, dict]:
    """절 → 지금 지문. 그리고 찍혀 있는 도장."""
    rows = _sections()
    now = {}
    for i, r in enumerate(rows):
        if r["state"] != "wired":
            continue                      # 무는 절은 부모 도장이 덮는다(머리말 `밖`)
        t = body(rows, i)
        fs = refs(t + " " + (r.get("field") or ""))
        if not fs:
            continue                      # 코드를 안 가리키는 절은 도장 대상이 아니다
        now[r["id"]] = {"sha": digest(t, fs), "files": fs, "doc": r["doc"]}
    was = json.loads(SEAL.read_text(encoding="utf-8")) if SEAL.is_file() else {}
    return now, was


def status() -> int:
    now, was = survey()
    ok = [k for k, v in now.items() if was.get(k, {}).get("sha") == v["sha"]]
    void = [k for k, v in now.items() if k in was and was[k]["sha"] != v["sha"]]
    none = [k for k in now if k not in was]
    gone = [k for k in was if k not in now]
    print(f"  도장 대상 {len(now)}절 (코드를 지목하는 wired 절)")
    print(f"    유효   {len(ok):>4}   확인한 뒤로 양쪽 다 안 바뀌었다")
    print(f"    무효   {len(void):>4}   한쪽이 바뀌었다 — 다시 봐야 한다")
    print(f"    미날인 {len(none):>4}   아직 아무도 확인 안 했다")
    if gone:
        print(f"    사라짐 {len(gone):>4}   절이 없어졌거나 코드 지목을 잃었다")
    for k in void[:10]:
        print(f"      ✗ {k}")
    return 0


def check() -> int:
    now, was = survey()
    if not now:
        print("★ 도장 대상이 0절이다 — 판별식을 의심하라")
        return 1
    void = sorted(k for k, v in now.items() if k in was and was[k]["sha"] != v["sha"])
    if not void:
        n = sum(1 for k in now if k in was)
        print(f"✓ 도장 {n}/{len(now)}절 유효 · 무효 0 — 확인한 뒤로 안 바뀌었다")
        return 0
    print(f"✗ 도장이 무효가 된 절 {len(void)}건 — **틀렸다가 아니라 다시 보라는 뜻이다**")
    for k in void:
        print(f"    {k}   {' · '.join(was[k]['files'][:3])}")
    print("\n  절과 코드를 같이 읽고, 여전히 맞으면 다시 찍어라:")
    print("    uv run python tools/docseal.py stamp --only <절>")
    return 1


def stamp(only: str | None) -> int:
    now, was = survey()
    if only:
        if only not in now:
            print(f"✗ `{only}` 는 도장 대상이 아니다 (wired 이고 코드를 지목해야 한다)")
            return 1
        was[only] = now[only]
    else:
        was = now
    SEAL.write_text(json.dumps(was, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    print(f"✓ 도장 {len(was)}절 → {SEAL.relative_to(ROOT)}")
    return 0


def selftest() -> int:
    """판별식이 **빈 그물이 아닌가.**"""
    bad = []
    rows = _sections()
    if len(rows) < 500:
        bad.append(f"절을 {len(rows)}개밖에 못 셌다")
    if not refs("본문에 `tools/docseal.py` 가 있다"):
        bad.append("백틱 경로를 못 뽑는다")
    if refs("`없는파일_abc.py` 뿐이다"):
        bad.append("없는 파일을 지목으로 센다")
    a = digest("본문", ["tools/docseal.py"])
    if a == digest("본문이 바뀌었다", ["tools/docseal.py"]):
        bad.append("문서 쪽이 바뀌어도 지문이 같다")
    if a == digest("본문", []):
        bad.append("코드 쪽을 안 센다")
    now, _ = survey()
    if len(now) < 20:
        bad.append(f"도장 대상이 {len(now)}절뿐이다 — 수집이 좁다")
    if bad:
        print("selftest 빨강")
        for b in bad:
            print(f"  ✗ {b}")
        return 1
    print(f"selftest 초록 · 도장 대상 {len(now)}절")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="문서 절 ↔ 코드 정합 도장")
    # ★ 2026-09-27 (DECISIONS §272). 기본이 `status` 였다 — **rc 를 늘 0 으로 낸다.**
    #   그래서 `uv run python tools/docseal.py` 를 검사로 부른 스윕이 **빈 그물**이었고,
    #   관문(`check`)이 잡은 무효를 개발 기계가 못 잡았다. 이 저장소의 다른 도구는
    #   전부 인자 없이 부르면 **검사**다(`sizecheck` · `deadcheck` · `treecheck` …).
    #   같은 규약으로 맞춘다 — 이름이 같으면 행동도 같아야 한다.
    ap.add_argument("cmd", nargs="?", default="check",
                    choices=["status", "check", "stamp"])
    ap.add_argument("--only", help="그 절 하나만 찍는다")
    ap.add_argument("--selftest", action="store_true", help="판별식 자기검사")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return {"status": status, "check": check}.get(a.cmd, lambda: stamp(a.only))()


if __name__ == "__main__":
    sys.exit(main())
