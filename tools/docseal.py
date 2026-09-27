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
import subprocess
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


def _body_v1(rows: list[dict], i: int) -> str:
    """2026-09-27 이전 판 — 끝의 빈 줄을 안 뗐다. 만나면 받고 새 판으로 고쳐 적는다."""
    r = rows[i]
    lines = (ROOT / r["doc"]).read_text(encoding="utf-8").splitlines()
    end = len(lines)
    for q in rows[i + 1:]:
        if q["doc"] == r["doc"] and q["depth"] <= r["depth"]:
            end = q["line"] - 1
            break
    return "\n".join(lines[r["line"] - 1:end])


#: 옛 판 본문 잘라내기. 줄이 늘 때마다 「한 번 지나면 안 흔들린다」가 한 세대 더 간다.
LEGACY_BODIES = (_body_v1,)


def body(rows: list[dict], i: int) -> str:
    """절 본문 — 다음 **같거나 얕은** 깊이의 제목 전까지. 끝의 빈 줄은 뗀다.

    ★ 2026-09-27 (DECISIONS §273-10). 끝을 안 떼면 **절을 하나 append 할 때마다
      직전 절의 도장이 무효가 된다.** 마지막 절은 EOF 까지 잘리는데, 뒤에 새 절이
      붙는 순간 구분용 빈 줄 하나가 본문에 들고 나기 때문이다. 실제로 §272 가
      그렇게 무효가 됐다 — 참조 파일이 **하나도 안 바뀌었는데**.

    ★ 거짓 무효는 도장을 죽인다. 매번 뜨는 「다시 보라」는 아무도 안 읽고,
      그러면 진짜 무효도 같이 안 읽힌다(§18-13 · 오탐이 본문을 덮는다).
      끝의 빈 줄은 뜻을 안 바꾸므로 떼는 것이 옳다.
    """
    r = rows[i]
    lines = (ROOT / r["doc"]).read_text(encoding="utf-8").splitlines()
    end = len(lines)
    for q in rows[i + 1:]:
        if q["doc"] == r["doc"] and q["depth"] <= r["depth"]:
            end = q["line"] - 1
            break
    return "\n".join(lines[r["line"] - 1:end]).rstrip()


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


#: 도장의 갈래. **같은 칸에 다른 주장을 적지 않는다.**
#:
#: ★ 2026-09-28 (DECISIONS §277). 미날인이 470절이었다. 절 단위로 재보니 그중
#:   174절은 **절을 쓴 뒤로 지목 코드가 한 번도 안 움직였다** — 쓸 때 참이었고
#:   그대로다. 그걸 기계가 찍을 수 있다. 그런데 「사람이 읽었다」와 같은 도장으로
#:   찍으면 **그 수가 거짓말이 된다** — 읽은 적 없는 174가 읽은 것으로 세어진다.
#:   주장이 다르면 칸도 다르다.
KINDS = {
    "read": "사람이 절과 코드를 같이 읽었다",
    "unmoved": "절을 쓴 뒤로 지목 코드가 한 번도 안 움직였다 — 기계가 찍었다",
}
#: 옛 판에는 갈래 칸이 없다. 그것들은 **사람이 찍은 것**이다.
DEFAULT_KIND = "read"


def _git_ct(*args: str) -> int:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return int(r.stdout.strip() or 0) if r.returncode == 0 else 0


def _blame(doc: str) -> list[int]:
    """문서 한 장의 **줄마다 마지막으로 바뀐 시각**. 문서당 한 번만 부른다."""
    r = subprocess.run(["git", "blame", "-t", "--line-porcelain", doc],
                       cwd=ROOT, capture_output=True, text=True)
    out, cur = [], 0
    for ln in r.stdout.splitlines():
        if ln.startswith("author-time "):
            cur = int(ln.split()[1])
        elif ln.startswith("\t"):
            out.append(cur)
    return out


def _span(rows: list[dict], i: int) -> tuple[int, int]:
    """절의 줄 범위. **`body()` 와 같은 규칙**이어야 한다 — 두 벌이면 갈린다."""
    r = rows[i]
    end = len((ROOT / r["doc"]).read_text(encoding="utf-8").splitlines())
    for q in rows[i + 1:]:
        if q["doc"] == r["doc"] and q["depth"] <= r["depth"]:
            end = q["line"] - 1
            break
    return r["line"] - 1, end


def moved_after(rows: list[dict], i: int, files: list[str],
                blames: dict[str, list[int]], mtimes: dict[str, int]) -> int:
    """지목 코드가 **절을 쓴 뒤에** 움직였나. 움직였으면 그 시각, 아니면 0.

    ★ 문서 전체의 mtime 으로 재면 안 된다 — 문서는 배치마다 손대므로 **모든 절이
      「코드보다 나중」**으로 나온다. 실제로 그렇게 재봤다가 459/470 이라는 쓸모없는
      수가 나왔다. 절 단위 blame 이라야 뜻이 있다.
    """
    r = rows[i]
    doc = r["doc"]
    if doc not in blames:
        blames[doc] = _blame(doc)
    a, b = _span(rows, i)
    lines = blames[doc][a:b]
    if not lines:
        return 0                       # 못 쟀다 — 안 찍는다
    sec = max(lines)
    newest = 0
    for f in files:
        if f not in mtimes:
            mtimes[f] = _git_ct("log", "-1", "--format=%ct", "--", f)
        newest = max(newest, mtimes[f])
    return newest if newest > sec else 0


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
        now[r["id"]] = {"sha": digest(t, fs), "files": fs, "doc": r["doc"],
                        "legacy": [digest(f(rows, i), fs) for f in LEGACY_BODIES]}
    was = json.loads(SEAL.read_text(encoding="utf-8")) if SEAL.is_file() else {}
    return now, was


def valid(now_one: dict, was_one: dict | None) -> bool:
    """도장이 아직 맞는가. **옛 판 지문도 받는다.**

    ★ 2026-09-27 (DECISIONS §273-10). 본문 잘라내기 규칙을 고치자 도장 14개가
      한꺼번에 무효가 됐다. 내용은 한 글자도 안 바뀌었고 **규칙만** 바뀐 것이다.
      열넷을 안 읽고 다시 찍으면 그것이 도장 찍기다(§272).

    ★ 이 저장소엔 이미 답이 있다 — `shardseal.LEGACY_PRINTS` 가 cfg 지문에
      같은 일을 한다(「옛 판 지문이면 받고 새 판으로 고쳐 적는다 · 재빌드 없음」).
      같은 규약을 쓴다. 규칙이 바뀌어도 **사람이 확인한 사실**은 그대로다.
    """
    if not was_one:
        return False
    return was_one.get("sha") in {now_one["sha"], *now_one.get("legacy", [])}


def kind_of(one: dict | None) -> str:
    return (one or {}).get("kind", DEFAULT_KIND)


def status() -> int:
    now, was = survey()
    ok = [k for k, v in now.items() if valid(v, was.get(k))]
    read = [k for k in ok if kind_of(was.get(k)) == "read"]
    unm = [k for k in ok if kind_of(was.get(k)) == "unmoved"]
    void = [k for k, v in now.items() if k in was and not valid(v, was[k])]
    none = [k for k in now if k not in was]
    gone = [k for k in was if k not in now]
    print(f"  도장 대상 {len(now)}절 (코드를 지목하는 wired 절)")
    print(f"    읽음   {len(read):>4}   {KINDS['read']}")
    print(f"    불변   {len(unm):>4}   {KINDS['unmoved']}")
    print(f"    무효   {len(void):>4}   한쪽이 바뀌었다 — 다시 봐야 한다")
    print(f"    미날인 {len(none):>4}   아직 아무도 확인 안 했다")
    if gone:
        print(f"    사라짐 {len(gone):>4}   절이 없어졌거나 코드 지목을 잃었다")
    for k in void[:10]:
        print(f"      ✗ {k}")
    return 0


def queue(limit: int = 30) -> int:
    """**사람이 읽어야 할 줄.** 코드가 절보다 나중에 움직인 절을, 최근 순으로.

    ★ 470 을 뭉뚱그려 「미날인」이라 부르면 어디부터 읽을지 모른다. 위험한 것은
      **절을 쓴 뒤에 코드가 움직인 절**이고, 최근에 움직였을수록 어긋났을 확률이 높다.
    """
    import datetime as _dt
    rows = _sections()
    now, was = survey()
    idx = {r["id"]: i for i, r in enumerate(rows)}
    blames: dict[str, list[int]] = {}
    mtimes: dict[str, int] = {}
    out = []
    for k, v in now.items():
        if valid(v, was.get(k)):
            continue
        i = idx.get(k)
        if i is None:
            continue
        at = moved_after(rows, i, v["files"], blames, mtimes)
        if at:
            out.append((at, k, v["files"]))
    out.sort(reverse=True)
    print(f"  읽어야 할 절 {len(out)} — 코드가 절보다 **나중에** 움직였다 (최근 순)")
    for at, k, fs in out[:limit]:
        d = _dt.datetime.fromtimestamp(at, tz=_dt.UTC).strftime("%m-%d")
        print(f"    {d}  {k:<18} {' · '.join(fs[:3])}")
    if len(out) > limit:
        print(f"    … {len(out) - limit}절 더 (--limit 로 늘려라)")
    print("\n  하나 읽었으면:  uv run python tools/docseal.py stamp --only <절>")
    return 0


def check() -> int:
    now, was = survey()
    if not now:
        print("★ 도장 대상이 0절이다 — 판별식을 의심하라")
        return 1
    void = sorted(k for k, v in now.items() if k in was and not valid(v, was[k]))
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


def _write(was: dict) -> None:
    SEAL.write_text(json.dumps(was, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")


def stamp(only: str | None, unmoved: bool = False) -> int:
    """도장을 찍는다. **인자 없이는 안 찍는다.**

    ★ 2026-09-28 (DECISIONS §277-2). 종전에는 `stamp` 를 인자 없이 부르면
      `was = now` 로 **전부** 찍었다. 470절을 한 줄로 「확인했다」로 만드는
      명령이 있었다는 뜻이다 — 이 도구의 뜻이 그 한 줄로 죽는다.
      찍으려면 **무엇을 왜 찍는지**를 말해야 한다.
    """
    now, was = survey()
    if only:
        if only not in now:
            print(f"✗ `{only}` 는 도장 대상이 아니다 (wired 이고 코드를 지목해야 한다)")
            return 1
        was[only] = {**now[only], "kind": "read"}
        _write(was)
        print(f"✓ 읽음 도장 — {only}  (총 {len(was)}절)")
        return 0

    if unmoved:
        rows = _sections()
        idx = {r["id"]: i for i, r in enumerate(rows)}
        blames: dict[str, list[int]] = {}
        mtimes: dict[str, int] = {}
        hit = []
        for k, v in now.items():
            if valid(v, was.get(k)):
                continue
            i = idx.get(k)
            if i is None:
                continue
            if not moved_after(rows, i, v["files"], blames, mtimes):
                was[k] = {**v, "kind": "unmoved"}
                hit.append(k)
        if not hit:
            print("  찍을 것이 없다 — 미날인 절 전부 코드가 나중에 움직였다")
            return 0
        _write(was)
        print(f"✓ 불변 도장 {len(hit)}절 — {KINDS['unmoved']}")
        print("  이제 사람이 읽을 줄:  uv run python tools/docseal.py queue")
        return 0

    print("✗ 무엇을 찍을지 말해라 — 인자 없는 `stamp` 는 없다.")
    print("    --only <절>   사람이 읽고 찍는다")
    print("    --unmoved     절을 쓴 뒤로 코드가 안 움직인 절을 기계가 찍는다")
    print("  ★ 종전에는 인자 없이 부르면 **전부** 찍었다. 그 한 줄로 이 도구가 죽는다(§277-2).")
    return 1


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
                    choices=["status", "check", "stamp", "queue"])
    ap.add_argument("--only", help="그 절 하나만 찍는다 (사람이 읽었다)")
    ap.add_argument("--unmoved", action="store_true",
                    help="절을 쓴 뒤로 코드가 안 움직인 절을 기계가 찍는다")
    ap.add_argument("--limit", type=int, default=30, help="queue 가 보여줄 줄 수")
    ap.add_argument("--selftest", action="store_true", help="판별식 자기검사")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.cmd == "queue":
        return queue(a.limit)
    return {"status": status, "check": check}.get(
        a.cmd, lambda: stamp(a.only, a.unmoved))()


if __name__ == "__main__":
    sys.exit(main())
