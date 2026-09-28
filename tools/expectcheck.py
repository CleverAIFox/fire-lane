#!/usr/bin/env python3
"""
expectcheck.py — **받는 쪽이 배달 계약을 읽는다.** `EXPECT` 의 독자.

    uv run python tools/expectcheck.py "$FIRE_LANE_INBOX/EXPECT"
    uv run python tools/expectcheck.py --selftest       ★ 판별식이 살아 있나

── 왜 생겼나 (2026-09-28 · DECISIONS §290-4) ───────────────────
`tools/deliver.py` 가 `EXPECT` 를 원격 팁 위에서 **재서** 썼다. zip 에 담겼고
건너갔고 **거기서 끝이었다** — 저장소 전체에서 그 파일을 읽는 코드가 0개였고
`fl.sh` 에는 `EXPECT` 라는 글자가 없었다. 그런데 그 파일의 머리말은
「go.sh 가 제가 잰 값과 대조한다」고 **적혀 있었다.** 없는 소비자를 있다고
적은 것이다.

★ `deliver.py` 가 생긴 이유가 「주장의 저자를 사람에서 기계로 바꾼다」였다.
  저자만 바꾸고 **독자를 안 만들었다.** 기계가 쓴 주장도 아무도 안 읽으면
  사람이 쓴 주장과 값이 같다(5족 · 파이프 단절).

★ **왜 `deliver.py` 안이 아닌가.** 그 파일이 750줄로 상한(600)을 넘었다.
  넘은 만큼이 **받는 쪽**이고 성질이 다르다 — 저쪽은 원격에 닿아 워크트리를
  떠서 재고, 이쪽은 **이미 얹힌 이 저장소**를 잰다. 꼴(`render`·`parse`)은
  여전히 `deliver.py` 하나에만 산다. 대조하는 쪽이 꼴을 제 손으로 파싱하면
  그때 2족이 된다.

── 무엇을 대는가 ───────────────────────────────────────────────
① **밑동**    `base.sha` 가 정말 HEAD 의 조상인가. 아니면 EXPECT 의 다른 값
              전부가 **다른 나무에서 온 수**다(§274-9 가 걱정한 자리).
② **폐포**    `closure.*` — 붙은 뒤의 지문이 이 기계의 실측과 같은가.
③ **재잠금**  `golden stale` 이 지금 `no` 인가. `yes` 로 남으면 재잠금이 안
              돌았다는 뜻이고 그 빨간불이 습관이 된다(§69).
④ **통보**    `unexercised` — 배달 기계가 **증명하지 않은** 축을 크게 찍는다.
              판정이 아니다. 「이 배치는 이 축들을 증명하지 않았다」를 읽고
              시작하게 하려는 줄이다.

IN    배달물의 `EXPECT` · 이 저장소의 실물
OUT   없음 (검사). 종료코드 = 어긋남 유무
PARAM 없음
밖    **`sweep` · `pytest` 는 안 댄다** — 산문 요약이라 기계가 댈 것이 없다.
      그 둘은 `verify.sh` 가 이 기계에서 다시 전수로 돈다(5단계).
      **`EXPECT` 를 고치지 않는다.** 고치는 것은 주장을 되살리는 것이다.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# ★ `sys.path` 를 건드리지 않는다 — `test_layering::test_sys_path_해킹이_없다` 가
#   막는다. `tools/` 는 스크립트를 돌릴 때 자동으로 들어오고, 시험은 선언
#   (`pyproject` 의 `pythonpath = ["tools", "src"]`)으로 본다.
# ★ 꼴(`render` · `parse`)은 `deliver` 하나에만 산다. 여기서 다시 파싱하면 2족이다.
from deliver import ROOT, _closure, _run, _wt_env, parse, render


def state(root: Path, env: dict) -> dict[str, str]:
    """지금 이 저장소의 사실. `deliver.dryrun` 이 워크트리에서 재는 것과 **같은 자다.**"""
    c = _closure(root, env)
    rc, _ = _run([sys.executable, "tools/golden.py", "stale"], cwd=root, env=env)
    _rc, out = _run(["git", "status", "--porcelain", "--", "web/data"], cwd=root)
    return {"closure.ingest": c["firelane.ingest"],
            "closure.segments": c["firelane.segments"],
            "golden.stale": "no" if rc == 0 else "yes",
            "webdata": "unchanged" if not out.strip() else "changed"}


def closure_target(v: str) -> str:
    """`same:abc` · `moved:abc->def` 에서 **붙은 뒤의** 지문을 꺼낸다."""
    return v.split("->")[-1].split(":")[-1].strip()


def notice(want: dict) -> list[str]:
    """④ 통보. **판정이 아니다** — 배달 기계가 증명하지 않은 축을 소리내어 읽는다."""
    unex = want.get("unexercised", "")
    n, _, names = unex.partition(":")
    out = [f"  배달 기계가 **증명하지 않은 축** {n or '?'}"]
    out += [f"    {x}" for x in (names.split(" · ") if names else [])]
    if not unex:
        out.append("    ★ EXPECT 에 `unexercised` 칸이 없다 — 옛 판으로 싼 배달이다")
    return out


def disagreements(want: dict, got: dict, root: Path) -> list[str]:
    """계약과 실측이 어긋난 것. **순수하게 대기만 한다** — 밑동 조상만 git 을 든다."""
    bad: list[str] = []
    if sha := want.get("base.sha"):
        rc, _ = _run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=root)
        if rc:
            bad.append(f"base.sha {sha} 가 HEAD 의 조상이 아니다 — "
                       "이 배달물은 **다른 밑동에서 재어졌다**")
    for k in ("closure.ingest", "closure.segments"):
        if k in want and closure_target(want[k]) != got[k]:
            bad.append(f"{k}  적힘 {closure_target(want[k])} · 실측 {got[k]}")
    # ★ 재잠금은 **여기서 이미 끝났어야 한다.** EXPECT 가 `yes` 였다면 `fl.sh --relock`
    #   이 4b 에서 돌았을 것이고 그랬으면 지금은 `no` 다. `yes` 로 남아 있으면
    #   재잠금을 안 한 것이다 — `golden check` 가 다음 실행부터 계속 울고
    #   그 빨간불이 습관이 된다(§69).
    if got["golden.stale"] != "no":
        bad.append("golden.stale  지금도 `yes` 다 — 재잠금이 안 돌았다"
                   f" (EXPECT 의 예고는 `{want.get('golden.relock', '?')}`)")
    if want.get("webdata") == "unchanged" and got["webdata"] == "changed":
        bad.append("webdata  안 바뀐다고 적혔는데 바뀌었다")
    return bad


def check(expect: Path, root: Path = ROOT) -> int:
    if not expect.is_file():
        print(f"✗ EXPECT 가 없다: {expect}")
        print("  배달물이 계약 없이 왔다. `deliver.py pack` 이 안 돌았다는 뜻이다")
        return 1
    want = parse(expect.read_text(encoding="utf-8"))
    if not want:
        print("✗ EXPECT 에 읽을 줄이 없다 — 손으로 쓴 파일인가")
        return 1
    for line in notice(want):
        print(line)

    got = state(root, _wt_env(root))
    if bad := disagreements(want, got, root):
        print(f"\n✗ 계약과 실측이 어긋난다 {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        print("\n  **EXPECT 를 고치지 마라.** 어긋난 것은 배달이거나 이 기계다.")
        return 1
    print(f"\n✓ 계약 대조 — 폐포 {got['closure.segments']} · "
          f"golden 최신 · web/data {got['webdata']}")
    return 0


def selftest() -> int:
    """판별식이 **빈 그물이 아닌가.** 데이터 없이 합성으로 문다."""
    bad = []
    ok = {"closure.ingest": "aaaa", "closure.segments": "bbbb",
          "golden.stale": "no", "webdata": "unchanged"}
    want = {"base.sha": "", "closure.ingest": "same:aaaa",
            "closure.segments": "moved:zzzz->bbbb", "golden.stale": "no",
            "webdata": "unchanged", "unexercised": "0"}
    if disagreements(want, ok, ROOT):
        bad.append(f"맞는 계약에 운다 — {disagreements(want, ok, ROOT)}")
    if not disagreements({**want, "closure.segments": "same:cccc"}, ok, ROOT):
        bad.append("폐포 지문이 달라도 안 운다")
    if not disagreements(want, {**ok, "golden.stale": "yes"}, ROOT):
        bad.append("재잠금이 안 돌았는데 안 운다")
    if not disagreements(want, {**ok, "webdata": "changed"}, ROOT):
        bad.append("web/data 가 안 바뀐다고 적혔는데 바뀐 것을 안 잡는다")
    if disagreements({**want, "webdata": "changed"},
                     {**ok, "webdata": "changed"}, ROOT):
        bad.append("바뀐다고 적힌 web/data 가 바뀐 것에 운다 — 그것은 예고대로다")

    # ★ `moved:a->b` 는 **뒤쪽**이 기준이다. 앞을 대면 늘 어긋난다.
    if closure_target("same:abc123") != "abc123":
        bad.append("`same:` 꼴에서 지문을 못 꺼낸다")
    if closure_target("moved:abc123->def456") != "def456":
        bad.append("`moved:` 꼴에서 뒤쪽을 못 꺼낸다")

    # ★ 통보는 **판정이 아니다.** 없는 칸을 조용히 넘기지도 않는다.
    if "3" not in notice({"unexercised": "3:가 · 나 · 다"})[0]:
        bad.append("못 돈 축의 수를 안 찍는다")
    if len(notice({"unexercised": "3:가 · 나 · 다"})) != 4:
        bad.append("못 돈 축의 이름을 줄마다 안 찍는다")
    if not any("옛 판" in x for x in notice({})):
        bad.append("`unexercised` 칸이 없는 옛 배달을 조용히 넘긴다")

    # ★ 꼴은 `deliver.py` 가 안다. 왕복이 되는지를 여기서 한 번 문다.
    if parse(render({"a": "1", "b": "x y"})) != {"a": "1", "b": "x y"}:
        bad.append("`render` → `parse` 왕복이 깨졌다")

    with tempfile.TemporaryDirectory() as td:
        if check(Path(td) / "없다", Path(td)) == 0:
            bad.append("EXPECT 가 없는 배달을 받아준다")
        e = Path(td) / "EXPECT"
        e.write_text("# 머리말뿐이다\n", encoding="utf-8")
        if check(e, Path(td)) == 0:
            bad.append("읽을 줄이 없는 EXPECT 를 받아준다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad))
        return 1
    print("✓ 자기검사 — 밑동 · 폐포 · 재잠금 · web/data · 통보 · 꼴 왕복")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="배달 계약(EXPECT)을 받는 쪽에서 댄다")
    ap.add_argument("expect", nargs="?", type=Path, help="배달물의 EXPECT 파일")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.expect is None:
        ap.error("EXPECT 파일 경로를 줘라 (예: \"$FIRE_LANE_INBOX/EXPECT\")")
    return check(a.expect)


if __name__ == "__main__":
    sys.exit(main())
