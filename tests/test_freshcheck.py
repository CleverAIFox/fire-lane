#!/usr/bin/env python3
"""
test_freshcheck.py — 「무엇이 왜 움직였나」를 말하는 검사가 정직한가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W4-10). `tools/freshcheck.py` 는 `verify.sh` 의
「커밋된 web/data 가 최신인가」를 대신한다. 종전 한 줄은 파일 이름까지만
말했고, 48줄이 움직여도 그중 45자리가 코드 봉인인지 판정값 드리프트인지
화면에서 구분이 안 됐다.

**분류하는 검사는 분류를 틀리면 덮어준다.** 덮어주는 검사는 없는 검사보다
나쁘다(DECISIONS §69 · §76). 그래서 여기는 「맞게 분류하는가」보다
**「덮어주지 않는가」**를 더 많이 든다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 자체시험 일곱이 실제로 돈다
    2. 비결정 필드 목록이 `firelane.manifest` 와 같다  (정본이 둘 방지)
    3. 봉인 칸 이름이 `shardseal` 이 내는 것과 같다
    4. 모르는 자리는 전부 `산출값` 이다                (모름 ≠ 통과)
    5. 통과 경계가 종전과 같다                          (관대해지지 않았다)
"""
from __future__ import annotations

import inspect
from pathlib import Path

import freshcheck as F
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_selftest_passes():
    """도구가 들고 다니는 자체시험이 초록인가."""
    assert F.selftest() == 0


def test_nondet_matches_manifest_writer():
    """비결정 필드 목록이 **생산자 쪽과 같은가.**

    `firelane.manifest.write_stable()` 은 `STAMP_KEYS` 가 든 필드만 빌려서
    「쓸까 말까」를 정하고, 이 검사는 같은 필드를 빼고 「왜 바뀌었나」를
    말한다. 둘이 갈리면 **한쪽이 무시한 필드를 다른 쪽이 산출값으로 운다** —
    영원히 빨간 단계가 되거나, 반대로 진짜 변경을 시각으로 덮는다.
    """
    from firelane import manifest
    assert set(manifest.STAMP_KEYS) == set(F.NONDET), (
        f"비결정 필드가 갈렸다 — manifest {manifest.STAMP_KEYS} · "
        f"freshcheck {sorted(F.NONDET)}\n"
        "  한쪽만 고치면 이 단계가 영원히 빨갛거나 진짜 변경을 덮는다.")


def test_seal_kinds_match_shardseal():
    """봉인 칸 이름이 `shardseal.make()` 가 내는 것과 같은가.

    ★ 칸이 늘었는데 여기 표가 안 늘면 그 칸의 변경은 **`산출값` 으로** 뜬다.
      과하게 우는 쪽이라 안전하지만, 반대로 표에만 있고 실물에 없는 이름이
      남으면 죽은 분류가 된다. 양방향으로 본다.
    """
    src = inspect.getsource(__import__("firelane.shardseal", fromlist=["x"]).make)
    for k in F.SEAL_KIND:
        assert f'"{k}"' in src, (
            f"`{k}` 가 SEAL_KIND 에 있는데 shardseal.make() 에는 없다 — 죽은 분류다")


@pytest.mark.parametrize("spot,expected", [
    (("v",), "산출값"),
    (("datasets", "0", "rows"), "산출값"),
    (("datasets", "0", "seal", "code"), "코드봉인"),
    (("datasets", "0", "seal", "cfg"), "설정봉인"),
    (("datasets", "0", "seal", "raw"), "원본봉인"),
    (("datasets", "0", "seal", "out"), "산출봉인"),
    # ★ `seal` 아래여도 모르는 칸이면 산출값이다
    (("datasets", "0", "seal", "새칸"), "산출값"),
    # ★ `source` 아래여도 모르는 키면 산출값이다
    (("source", "x.json", "새키"), "산출값"),
    # ★ 세 칸이 아니면(깊이가 다르면) 파생으로 안 본다
    (("source", "x.json"), "산출값"),
])
def test_unknown_spots_are_never_excused(spot, expected):
    """모르는 자리를 통과 분류로 흘리지 않는가."""
    assert F.kind_of(spot, frozenset({"x.json"})) == expected


def test_derived_needs_the_named_file_to_have_changed():
    """`source.<이름>.sha256` 은 **그 파일이 함께 바뀌었을 때만** 파생이다.

    ★ 되돌림이 본체다 — 그 파일이 안 바뀌었는데 여기 sha 만 움직였다면
      둘이 어긋난 것이고, 그것은 덮으면 안 되는 종류다.
    """
    spot = ("source", "x.json", "sha256")
    assert F.kind_of(spot, frozenset({"x.json"})) == "파생"
    assert F.kind_of(spot, frozenset()) == "산출값"
    assert F.kind_of(spot, frozenset({"y.json"})) == "산출값"


def test_pass_boundary_did_not_get_looser():
    """통과 경계가 종전(`git diff --quiet`)보다 **관대해지지 않았는가.**

    종전에 통과하던 것은 「차이 없음」 하나다. 지금 통과하는 것은
    「차이 없음」 · 「시각만」 · 「파생만」 셋이고, 앞의 둘은
    `write_stable` 때문에 실무에서 파일이 아예 안 쓰이는 경우다.
    **그 밖의 어떤 분류도 통과가 되면 안 된다.**
    """
    assert F.is_clean({})
    assert F.is_clean({"파생": ["source.x.json.sha256"]})
    for kind in ("산출값", "코드봉인", "설정봉인", "원본봉인", "산출봉인"):
        assert not F.is_clean({kind: ["아무데나"]}), f"{kind} 이 통과로 샌다"
        assert not F.is_clean({"파생": ["a"], kind: ["b"]}), f"파생과 섞이면 {kind} 이 샌다"


def test_canon_drops_stamps_at_every_depth():
    """중첩·배열 안의 시각도 빠지는가. `terrain`·`ortho` 는 제 블록에 넣는다."""
    o = {"generated_at": "A", "d": [{"generated_at": "B", "v": 1}],
         "n": {"m": {"generated_at": "C", "v": 2}}}
    assert F.canon(o) == {"d": [{"v": 1}], "n": {"m": {"v": 2}}}


def test_verify_calls_it_and_declares_the_exemption():
    """`verify.sh` 가 이 도구를 부르고, **면제를 선언하는가.**

    선언이 없으면 `gate_parity` 의 「미선언 로컬 전용」 래칫이 하나 늘어
    빨개진다 — 그 래칫이 이 검사를 대신 들어 주는 것이 아니라, 선언을
    빠뜨린 것을 잡는 것이다(W3-10).
    """
    src = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert "tools/freshcheck.py" in src, "verify.sh 가 freshcheck 을 안 부른다"
    assert "# ci-exempt: tools/freshcheck.py" in src, (
        "freshcheck 의 `ci-exempt` 선언이 없다 — 관문 동등 래칫이 운다")
    assert "git diff --quiet -- web/data data/processed" not in src, (
        "종전 한 줄이 남아 있다 — 정본이 둘이다")
