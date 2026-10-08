#!/usr/bin/env python3
"""
delivertest.py — **배달 판정기가 살아 있나.** `deliver.py` 의 자기검사다.

    uv run python tools/deliver.py --selftest     ← 이 파일이 답한다
    uv run python tools/delivertest.py            같은 것을 직접 돈다

── 왜 제 파일인가 (2026-10-08 · DECISIONS §436-6) ──────────────
`tools/deliver.py` 가 **상한에 붙어 살았다.** 636 → 655 로 한 판에서 올렸고
이 판에서 또 넘겼다. 「예외는 늘 자리가 아니다」 — 상한을 또 올리는 대신
자기검사를 떼낸다. 떼낼 자리가 자기검사인 이유는 둘이다 —

```
판정기(`cmd_base` · `cmd_dryrun` · `cmd_pack`)는 **배달을 한다**
자기검사는 그 판정기가 **제 일을 하는가**를 묻는다 — 배달을 안 한다
```

★ `tools/mutate_guard.py` 를 `mutate.py` 에서 뗀 것과 같은 가름이다(§435-16):
  일하는 쪽과 **일이 되는가를 묻는 쪽**은 다른 파일이다.

★ 판별식 수는 **소스에서 센다** — `bad.append` 하나가 판별식 하나다(§276-1).
  그 규약 때문에 줄을 줄이려고 `bad += [...]` 로 바꾸면 **계수기가 눈을
  감는다.** 이 판에서 실제로 그렇게 했고 29 → 31 → 29 로 흔들렸다. 줄은
  이 파일을 떼서 줄이고, 꼴은 안 바꾼다.

IN    없음
OUT   종료코드 (0 초록)
PARAM 없음
밖    배달 자체는 `tools/deliver.py` 가, 축·시험 면제 선언은
      `tools/delivercheck.py` 가 든다.
부류  절차   도구가 제 일을 하는가를 묻는다  (DECISIONS §398)
"""
from __future__ import annotations

import inspect
import shutil
import sys
from pathlib import Path

from deliver import PATCH_PREFIX, ROOT, parse, render
from delivercheck import (
    BODY_CHECK,
    FORBIDDEN,
    LAKE_ONLY,
    RELOCK_AXES,
    RELOCK_TESTS,
    bodies_missing,
    collide,
    diff_sweep,
    diff_tests,
    excused,
    forbidden,
    func_name,
    lonely_tests,
    new_red,
    patch_paths,
    tails,
    zip_items_broken,
)


def selftest() -> int:
    """판별식이 살아 있나. 셋을 일부러 깨고 셋 다 울어야 한다."""
    bad = []
    if collide(["0001-a.patch", "0001-a.patch"]) != ["0001-a.patch"]:
        bad.append("이름 충돌을 못 잡는다")
    if collide(["0001-a.patch", "0002-b.patch"]):
        bad.append("멀쩡한 이름에 운다")
    # ★ §278-5. 접두사가 붙어도 같은 꼬리를 잡는가. 안 떼면 무음으로 통과한다.
    if not tails([f"{PATCH_PREFIX}0001-x.patch", f"{PATCH_PREFIX}0003-x.patch"]):
        bad.append("접두사 붙은 같은 꼬리를 안 잡는다")
    if tails([f"{PATCH_PREFIX}0001-x.patch", f"{PATCH_PREFIX}0002-y.patch"]):
        bad.append("접두사 붙은 다른 꼬리를 잡는다")
    if not tails(["0001-x.patch", "0003-x.patch"]):
        bad.append("번호만 다른 같은 꼬리를 못 잡는다")
    if tails(["0001-x.patch", "0002-y.patch"]):
        bad.append("멀쩡한 꼬리에 운다")
    if not parse(render({"a": "1"})) == {"a": "1"}:
        bad.append("EXPECT 를 적고 되읽지 못한다")
    if parse(render({"a": "1"})).get("#"):
        bad.append("주석을 값으로 읽는다")
    # ★ `deadcheck ③` — 대장이 비면 통과가 아니라 실패다. 비운 채로 초록이면
    #   「금지 문자열 없음」이 「볼 것이 없음」의 다른 말이 된다.
    if not FORBIDDEN:
        bad.append("`FORBIDDEN` 이 비었다 — 볼 것이 없으면 통과가 아니다")
    if not LAKE_ONLY:
        bad.append("`LAKE_ONLY` 가 비었다 — 면제 대장이 비면 ④ 가 죽은 칸이다")
    if not bodies_missing(["0001-x.patch", "EXPECT"]):
        bad.append("`PR_BODY.md` 가 없는데 안 운다")
    if bodies_missing(["PR_BODY.md", "PR_BODY_DEV.md"]):
        bad.append("본문이 있는데 운다")
    if not (ROOT / BODY_CHECK).exists():
        bad.append(f"`{BODY_CHECK}` 가 없다 — 본문 검사가 죽은 칸이다")
    # ★ §294. zip 이 제 목록에 들면 끝나지 않는다. 경로 꼴까지 재는 전수는
    #   `tests/test_delivercheck.py` 가 들고, 여기서는 **죽은 칸만** 막는다.
    bad += zip_items_broken()
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad)); return 1

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        dirty = Path(td) / "0001-x.patch"
        dirty.write_text(f"제목\n\n{FORBIDDEN[0]} <x@y>\n", encoding="utf-8")
        clean = Path(td) / "0002-y.patch"
        clean.write_text("제목\n\n본문뿐이다\n", encoding="utf-8")
        if not forbidden([dirty]):
            bad.append("금지 문자열을 심었는데 못 잡는다")
        if forbidden([clean]):
            bad.append("멀쩡한 파일에 운다")
        # ★ diff 안의 같은 글자는 **결함이 아니다.** 규약은 커밋 메시지에 걸린다.
        indiff = Path(td) / "0003-z.patch"
        indiff.write_text(f"제목\n\n본문\n---\n a | 1 +\n+{FORBIDDEN[0]}\n",
                          encoding="utf-8")
        if forbidden([indiff]):
            bad.append("diff 안의 글자를 결함으로 센다 — 그 규약을 무는 검사를 못 쓰게 된다")
        inmsg = Path(td) / "0004-z.patch"
        inmsg.write_text(f"제목\n\n{FORBIDDEN[0]} <x@y>\n---\n a | 1 +\n",
                         encoding="utf-8")
        if not forbidden([inmsg]):
            bad.append("메시지의 서명을 못 잡는다")
        # ★ 면제는 **판별식이 참일 때만**이다. 레이크가 있는 자리에서는 안 봐준다.
        frag = next(iter(LAKE_ONLY))
        (Path(td) / "data" / "raw").mkdir(parents=True)
        if excused(frag, Path(td)) is not None:
            bad.append("레이크가 있는데도 면제해준다 — 도장 찍기다")
        shutil.rmtree(Path(td) / "data")
        if excused(frag, Path(td)) is None:
            bad.append("레이크가 없는데 면제를 안 해준다")
        if excused("test_아무거나", Path(td)) is not None:
            bad.append("대장에 없는 빨간불을 면제해준다")
        # ★ 재잠금 축은 **재잠금이 선언됐을 때만** 받는다. 아니면 그대로 운다.
        axis = next(iter(RELOCK_AXES))
        try:
            diff_sweep(set(), {axis}, Path(td), relock=True)
        except SystemExit:
            bad.append("재잠금 배치에서 재잠금 축에 운다")
        try:
            diff_sweep(set(), {axis}, Path(td), relock=False)
            bad.append("재잠금이 아닌데 재잠금 축을 받아준다 — 도장 찍기다")
        except SystemExit:
            pass
        # ★ 2026-10-08 (DECISIONS §439 · PLAN #138). **외로운 시험**을 민다.
        #   합성 패치 넷으로 네 갈래를 본다 — 시험만(중간) · 시험+구현 ·
        #   시험만인데 마지막 · 구현만. 넷을 다 안 밀면 그물이 한쪽으로 쏠린다.
        def patch(td2, name, *paths, names=()):
            q = Path(td2) / name
            body = "".join(f"--- a/{x}\n+++ b/{x}\n" for x in paths)
            q.write_text(body + "".join(f"+# {n}\n" for n in names), encoding="utf-8")
            return q

        lonely = patch(td, "0001-t.patch", "tests/test_x.py", names=("tools/z.py",))
        paired = patch(td, "0002-tp.patch", "tests/test_y.py", "src/firelane/y.py")
        impl = patch(td, "0003-i.patch", "tools/z.py")
        tail = patch(td, "0004-t2.patch", "tests/test_z.py", names=("tools/z.py",))
        # ★ 이미 있는 코드를 시험하는 커밋 — 뒤 패치가 그것을 안 건드린다
        settled = patch(td, "0005-t3.patch", "tests/test_w.py", names=("tools/w.py",))
        if patch_paths(lonely) != ["tests/test_x.py"]:
            bad.append("패치에서 경로를 못 뽑는다")
        if not lonely_tests([lonely, impl]):
            bad.append("시험이 드는 것이 뒤 커밋에 오는데 안 잡는다 — §258-13")
        if lonely_tests([settled, impl]):
            bad.append("**이미 있는 코드**를 시험하는 커밋에 운다 — 혼자 초록이다")
        if lonely_tests([paired, impl]):
            bad.append("구현이 같이 든 커밋에 운다 — 짝이 있으면 혼자 초록이다")
        if lonely_tests([impl, tail]):
            bad.append("**마지막** 시험 커밋에 운다 — 그 지점은 예습이 이미 본다")
        if lonely_tests([lonely]):
            bad.append("패치가 하나인데 운다 — 그것이 마지막이다")

        # ★ 2026-10-08 (DECISIONS §436-6). 시험 쪽도 **양방향으로** 민다. 먹이는
        #   것은 **실물 pytest id** 다 — 함수 이름만 먹이면 검사가 내 손을 잰다.
        tn, X = next(iter(RELOCK_TESTS)), "tests/test_x.py::"
        nid = f"{X}{tn}[data/processed/segments.schema.json]"
        empty: tuple[set[str], str] = (set(), "")
        if func_name(nid) != tn:
            bad.append("실물 id 에서 함수 이름을 못 뽑는다")
        for red, lock, why in ((nid, True, "재잠금 배치에서 재잠금 시험에 운다"),
                               (nid, False, None), (f"{X}{tn}_x", True, None),
                               (f"{X}x_{tn}", True, None),
                               (f"{X}{tn[:-2]}", True, None)):
            try:
                diff_tests(empty, ({red}, ""), Path(td), relock=lock)
                if why is None:
                    bad.append(f"면제가 넓다 — {red} lock={lock}")
            except SystemExit:
                if why:
                    bad.append(why)
        # ★ ④ 기준선 대조. 밑동에서 이미 빨간 것은 흡수하고, 새것은 울어야 한다.
        try:
            new_red({"a::b"}, {"a::b"}, Path(td), "시험")
        except SystemExit:
            bad.append("밑동에서 이미 빨간 것에 운다 — 기준선을 안 뺀다")
        try:
            new_red({"a::b"}, {"a::b", "c::d"}, Path(td), "시험")
            bad.append("이 배치가 새로 빨갛게 만든 것에 안 운다")
        except SystemExit:
            pass
        try:
            new_red(set(), {frag}, Path(td), "시험")   # 레이크 없음 → 면제가 맞다
        except SystemExit:
            bad.append("레이크 없는 자리에서 레이크 전용 빨간불에 운다")

    # ★ 꼴의 왕복. **`render`·`parse` 가 사는 집이 여기다** — 대조는 저쪽이 한다.
    if parse(render({"a": "1", "b": "x y"})) != {"a": "1", "b": "x y"}:
        bad.append("`render` → `parse` 왕복이 깨졌다")
    if parse(render({"a": "1"})) != {"a": "1"}:
        bad.append("머리말 주석을 값으로 센다")

    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad)); return 1
    # ★ 2026-09-27 (§276-1). 종전에는 `18개` 가 **손으로 박혀** 있었다. 팔을
    #   더해도 그 수가 안 따라오므로 곧 거짓이 된다 — 이 저장소가 수를 손으로
    #   적었다가 열두 번 고친 자리와 같은 형태다(PLAN §1 제목 · DECISIONS §246).
    #   판별식 하나가 `bad.append` 하나이므로 **소스에서 센다.**
    arms = inspect.getsource(selftest).count("bad.append(")
    print(f"✓ 자기검사 — 판별식 {arms}개가 다 운다")
    return 0

if __name__ == "__main__":
    # ★ `argparse` 를 쓴다 — 맨손 `sys.argv` 는 **모르는 깃발을 조용히 무시**하고
    #   일을 하고, `tests/test_cli_surface.py` 가 그것을 센다. 오타 하나로
    #   「돌았는데 다른 일을 했다」가 되는 자리다.
    import argparse  # noqa: PLC0415  진입점에서만 쓴다

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true",
                    help="기본 동작이다 — 적어도 되고 안 적어도 된다")
    ap.parse_args()
    sys.exit(selftest())
