#!/usr/bin/env python3
"""
axis_gain.py — 샤드 `seal.code` 를 **축으로 쪼개면 실제로 얼마나 아끼는가.**
(PLAN §1 #132 · DECISIONS §274-3)

    uv run python tools/axis_gain.py              정적 + 동적 이득을 잰다
    uv run python tools/axis_gain.py --since 200  볼 커밋 수 (기본 150)
    uv run python tools/axis_gain.py --json       기계가 읽는 요약
    uv run python tools/axis_gain.py --selftest   ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-27. `#132`(축 분리)를 **짜기 전에** 「그게 실제로 뭘 아끼냐」를 물었고,
  답을 추정으로 냈다("`raw_only` 26개가 멈춘다"). 추정으로 설계하면 짜고 나서
  "생각보다 별로네" 를 알게 된다 — `#132` 가 이미 한 번 그랬다(§274-3: 이 행은
  `#128` 을 막는다고 적혀 있었는데 **반대였다**).

★ **그래서 재는 일을 도구로 만든다.** 사람이 세면 갈리고, 한 번 세고 나면
  다음 판에 다시 안 센다.

── 무엇을 재는가 ───────────────────────────────────────────────
① **정적** — 샤드 하나가 지금 몇 파일을 해싱하는가, 축을 쪼개면 몇 개인가.
   공용 폐포는 어느 갈래든 다 들므로 **거기 있는 파일을 고치면 이득이 0** 이다.

② **동적** — 지난 N 커밋 중 **몇 번이 한 갈래만 건드렸나.** 이것이 진짜 이득이다.
   공용만 건드린 커밋은 축을 쪼개도 전량 재도장이다.

   ★ `read/` 는 오늘 생겼으므로 이력이 없다. 그래서 **옛 `ingest.py` 의 분기
     구역으로 환산한다** — 커밋 시점의 파일을 파싱해 `elif kind` 경계를 얻고,
     그 커밋의 hunk 가 어느 구역에 떨어졌는지 본다. 지금 갈래를 그때 적용했다면
     무엇이 찢어졌을지를 재는 것이다.

③ **대장 가중** — 갈래마다 데이터셋 수가 다르다. 7줄짜리 `passthrough` 가
   26개(36%)를 든다. 「몇 번 아끼나」가 아니라 **「샤드 몇 개를 아끼나」**다.

IN    firelane.shardseal 폐포 · firelane.read.READERS · 대장 · git 이력
OUT   표준출력 (판정) · `--json` 이면 요약 dict
밖    **축을 실제로 쪼개지 않는다.** 이 도구는 재기만 한다 — 쪼개는 것은
      `shardseal` 소관이고, 그 판단의 근거를 여기가 낸다.
      **재도장 비용(초)도 안 본다** — 찢어지는 샤드 수가 비용의 대리 변수다.
부류  조사   사람이 손으로 돌린다. 수를 내고 멈춘다  (DECISIONS §398)
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 분기 경계. `ingest.py` 의 옛 판에서도 같은 꼴이었다.
BRANCH = re.compile(r"^    (?:el)?if kind (?:==|in) (.+?):")
#: 이력에서 볼 파일 — 갈래가 여기서 나왔다.
LEGACY = "src/firelane/ingest.py"
#: hunk 머리 — `@@ -a,b +c,d @@`
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _git(*a: str, timeout: int = 60) -> str:
    r = subprocess.run(["git", *a], cwd=ROOT, capture_output=True,
                       text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else ""


# ── ① 정적 ─────────────────────────────────────────────────────
def families() -> dict[str, list[str]]:
    """갈래 모듈 → 그 갈래가 맡은 kind 들."""
    from firelane import read
    out: dict[str, list[str]] = collections.defaultdict(list)
    for kind, fn in read.READERS.items():
        out[fn.__module__.split(".")[-1]].append(kind)
    return dict(out)


def datasets_per_kind() -> dict[str, int]:
    from firelane import ledger
    c: collections.Counter[str] = collections.Counter()
    for e in ledger.load()["datasets"].values():
        k = (e or {}).get("kind")
        if k:
            c[k] += 1
    return dict(c)


def static() -> dict:
    """지금 폐포 · 공용 폐포 · 갈래별 폐포."""
    from firelane import shardseal as ss
    whole = {Path(p).name for p in ss.code_closure("firelane.ingest")}
    fam = families()
    own = {f: f"{f}.py" for f in fam}
    shared = whole - set(own.values())
    return {"whole": sorted(whole), "shared": sorted(shared),
            "own": own, "families": fam}


# ── ② 동적 ─────────────────────────────────────────────────────
def _boundaries(text: str) -> list[tuple[int, int, str]]:
    """그 판의 `elif kind` 구역들 — (시작줄, 끝줄, 첫 kind)."""
    lines = text.splitlines()
    marks = [(i + 1, m.group(1)) for i, ln in enumerate(lines)
             if (m := BRANCH.match(ln))]
    if not marks:
        return []
    ends = [*[a for a, _ in marks[1:]], len(lines) + 1]
    out = []
    for (a, expr), b in zip(marks, ends, strict=True):
        ks = re.findall(r'"([a-z0-9_]+)"', expr)
        if ks:
            out.append((a, b - 1, ks[0]))
    return out


def _touched_kinds(sha: str) -> set[str] | None:
    """그 커밋이 `ingest.py` 에서 건드린 분기들. 분기 밖만 건드렸으면 빈 집합."""
    text = _git("show", f"{sha}~1:{LEGACY}")
    if not text:
        return None
    zones = _boundaries(text)
    if not zones:
        return None
    diff = _git("diff", "-U0", f"{sha}~1", sha, "--", LEGACY)
    hit: set[str] = set()
    for ln in diff.splitlines():
        m = HUNK.match(ln)
        if not m:
            continue
        a = int(m.group(1))
        n = int(m.group(2) or 1)
        for s, e, kind in zones:
            if a <= e and (a + max(n, 1) - 1) >= s:
                hit.add(kind)
    return hit


def dynamic(since: int) -> dict:
    """지난 N 커밋 중 몇 번이 **한 갈래만** 건드렸나."""
    shas = [s for s in _git("log", f"-{since}", "--format=%H", "--", LEGACY).split() if s]
    kind2fam = {k: f for f, ks in families().items() for k in ks}
    rows: list[tuple[str, set[str]]] = []
    for s in shas:
        hit = _touched_kinds(s)
        if hit is None:
            continue
        rows.append((s, {kind2fam.get(k, "?") for k in hit}))
    one = [s for s, f in rows if len(f) == 1]
    none = [s for s, f in rows if not f]
    many = [s for s, f in rows if len(f) > 1]
    per: collections.Counter[str] = collections.Counter()
    for _, f in rows:
        if len(f) == 1:
            per[next(iter(f))] += 1
    return {"seen": len(rows), "one": len(one), "shared_only": len(none),
            "many": len(many), "per_family": dict(per)}


# ── 판정 ────────────────────────────────────────────────────────
#: 이 밑이면 짜지 않는다 — 아끼는 샤드·커밋이 적으면 축을 늘린 값이 없다.
WORTH_COMMITS = 0.20      # 한 갈래만 건드린 커밋 비율
WORTH_SHARDS = 0.30       # 그때 안 찢어지는 샤드 비율 (가중 평균)


def judge(st: dict, dy: dict, ds: dict) -> tuple[bool, list[str]]:
    total = sum(ds.values())
    per_fam_ds = {f: sum(ds.get(k, 0) for k in ks)
                  for f, ks in st["families"].items()}
    say = []
    if not dy["seen"]:
        return False, ["이력에서 `ingest.py` 커밋을 하나도 못 읽었다 — "
                       "얕은 클론이면 `--since` 를 줄이거나 전체 이력을 받아라. "
                       "못 잰 것을 「이득 없음」으로 세지 않는다"]
    r_commit = dy["one"] / dy["seen"]
    # 한 갈래만 건드렸을 때 **안 찢어지는** 샤드 비율 — 커밋 수로 가중
    saved = sum(cnt * (total - per_fam_ds.get(f, 0))
                for f, cnt in dy["per_family"].items())
    r_shard = saved / (dy["one"] * total) if dy["one"] else 0.0
    say.append(f"한 갈래만 건드린 커밋  {dy['one']}/{dy['seen']} = {r_commit:.0%}"
               f"  (기준 {WORTH_COMMITS:.0%})")
    say.append(f"그때 안 찢어지는 샤드  {r_shard:.0%}"
               f"  (기준 {WORTH_SHARDS:.0%})")
    return (r_commit >= WORTH_COMMITS and r_shard >= WORTH_SHARDS), say


def selftest() -> int:
    """★ 판정기가 **양쪽으로** 우는가. 통과만 보면 방향을 못 잰다."""
    n = 0
    st = {"families": {"a": ["k1"], "b": ["k2"]}}
    ds = {"k1": 10, "k2": 90}
    # ① 이득 있음 — a 만 건드린 커밋이 잦고, 그때 90 이 안 찢어진다
    ok, _ = judge(st, {"seen": 10, "one": 9, "shared_only": 1, "many": 0,
                       "per_family": {"a": 9}}, ds)
    n += ok is True
    # ② 커밋 비율이 낮다
    ok, _ = judge(st, {"seen": 100, "one": 5, "shared_only": 95, "many": 0,
                       "per_family": {"a": 5}}, ds)
    n += ok is False
    # ③ 잦지만 **큰 갈래만** 건드린다 — 아끼는 샤드가 적다
    ok, _ = judge(st, {"seen": 10, "one": 9, "shared_only": 1, "many": 0,
                       "per_family": {"b": 9}}, ds)
    n += ok is False
    # ④ 이력을 못 읽었다 — 「이득 없음」이 아니라 **못 쟀다**
    ok, why = judge(st, {"seen": 0, "one": 0, "shared_only": 0, "many": 0,
                         "per_family": {}}, ds)
    n += (ok is False and "못 잰 것" in why[0])
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=150)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        n = selftest()
        print(f"{'✓' if n == 4 else '✗'} 자기검사 — 판별식 {n}/4 가 운다")
        return 0 if n == 4 else 1

    st, ds = static(), datasets_per_kind()
    dy = dynamic(a.since)
    total = sum(ds.values())

    print("\n── ① 정적 — 샤드 하나가 해싱하는 파일")
    print(f"  지금        {len(st['whole'])}개 (갈래 전부가 폐포 안)")
    print(f"  축 쪼갠 뒤  {len(st['shared'])} + 1 = {len(st['shared']) + 1}개")
    print("\n── ② 갈래별 — 그 갈래를 고치면 찢어지는 샤드")
    for f, ks in sorted(st["families"].items(),
                        key=lambda x: -sum(ds.get(k, 0) for k in x[1])):
        n = sum(ds.get(k, 0) for k in ks)
        print(f"  {f:<12} {n:>3}/{total}  ({n/total:>4.0%})  "
              f"안 찢어짐 {total - n:>2}개 · kind {' · '.join(sorted(ks))}")
    print(f"\n── ③ 동적 — 지난 {a.since} 커밋 중 `ingest.py` 를 건드린 {dy['seen']}건")
    print(f"  한 갈래만     {dy['one']:>3}건   {dy['per_family']}")
    print(f"  공용만        {dy['shared_only']:>3}건   (축을 쪼개도 전량 재도장)")
    print(f"  여러 갈래     {dy['many']:>3}건")

    worth, say = judge(st, dy, ds)
    print("\n── 판정")
    for s in say:
        print(f"  {s}")
    print(f"\n{'✓ 값이 있다 — #132 를 짠다' if worth else '✗ 값이 없다 — #132 를 접고 PLAN 에 이 수치를 적는다'}")
    if a.json:
        print(json.dumps({"static": {k: v for k, v in st.items() if k != "own"},
                          "dynamic": dy, "datasets": ds, "worth": worth},
                         ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
