#!/usr/bin/env python3
"""
ledger_cross.py — **약속과 실측이 대장 안에서 서로를 반박하지 않는가.**

    uv run python tools/ledger_cross.py            판정 (verify.sh · CI)
    uv run python tools/ledger_cross.py --table    대조한 짝 전부
    uv run python tools/ledger_cross.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-10-02 (DECISIONS §349). `tests/test_k2.py` 가 2026-09-28 부터 이렇게
  적고 있었다 —

      `ledger_schema --check` 는 **덮개가 없다.** 실물에서 읽는 것이 전부라
      대장만 보고 할 수 있는 절반이 없다.

  그 문장이 사흘 뒤에 거짓이 됐다. §340-4 가 같은 파일 안에서 정반대를 적었다 —
  「세는 대상은 **대장에 적혀 있는 값**이고 `sources.yaml` 은 저장소 안에 있다.
  레이크는 **읽을 때만** 필요하다」. 그런데 **선언 쪽 문장은 안 고쳤고**, 그래서
  「덮개 없음」이 선언으로 살아남아 그 자리를 영구 사각지대로 뒀다.
  §346 과 같은 족이다 — **적어 두는 것은 보이게 만드는 것이고 고치는 것이 아니다.**

★ 그리고 여기는 잴 것이 실제로 있다. 대장은 같은 사실을 **두 벌**로 들고 있다 —

      contract:   규범. 「이래야 한다」. 사람이 고른다
      schema:     기술. 「지금 실물에 이렇더라」. `ledger_schema.py` 가 쓴다

  `ledger_schema.py` 머리말이 왜 둘을 안 합치는지 적는다 — 「실물이 바뀌었을 때
  **약속이 함께 바뀌면 아무도 못 알아챈다**」. 옳다. 그런데 **둘을 대 보는
  자리가 없었다.** 갈라 두기만 하고 대조를 안 하면 두 벌이 조용히 갈린다(2족).

── 무엇을 보는가 ───────────────────────────────────────────────
    required_cols   ⊆ schema.columns        약속한 칸이 실물에 있는가
    layer_must_exist → layer_used ∈ layers  쓰기로 한 레이어가 실측 목록에 있는가
    contract.encoding = schema.encoding_seen 약속한 인코딩으로 읽혔는가
    contract.rows    ≈ schema.features       약속한 행 수가 실측과 같은가
    what ⊬ 남의 칸                           산문이 **다른 소스의 칸**을 서술하는가

★ 다섯째 축은 **사람이 쓴 칸**을 본다(2026-10-10 · DECISIONS §452 · PLAN #56 ①).
  2026-09-17 에 `hydrant_summary` 의 `what` 이 **다른 판의 컬럼 체계**를 서술하고
  있었다 — `schema` 는 실물을 맞게 들고 있었고 사람이 쓴 칸만 틀렸다(§178-2).
  그날 「사람이 쓴 칸과 도구가 쓴 칸을 대조하는 검사가 없다」고 적고 24일을 뒀다.

★ **약하다.** 산문의 뜻은 안 본다 — 「이 칸 이름이 남의 것인가」만 본다. 줄여 쓴
  이름(`지상식` ← `지상식소화전`)은 **못 잡는다.** 넓히려면 말씨를 읽어야 하고
  그것은 이 저장소가 안 쓰는 물건이다(`plan_renumber` 머리말이 같은 판단을 적는다).

★ **양쪽이 다 적힌 항목만 센다.** 한쪽이 없으면 할 말이 없다 — 그것은
  `src/firelane/ledger.py` 의 필수 칸 검사가 든다.
★ **빈 그물**(MASTER §17-0 ③). 짝이 `NET_MIN` 보다 적으면 실패다. 선언 꼴이
  바뀌어 수집기가 죽으면 위 넷이 전부 조용히 통과한다 — 0을 0과 비교한다.

IN    sources.yaml (`firelane.ledger.load_sources` 한 문으로)
OUT   표준출력 (판정)
PARAM NET_MIN
밖    **실물을 안 읽는다.** 그래서 레이크 없는 기계에서도, CI 에서도 돈다 —
      그것이 이 파일이 `ledger_schema.py` 와 갈라져 있는 이유다. 저쪽은
      `require_lake(need=("raw",))` 뒤에 있어 CI 에서 한 번도 안 돈다.
      **읽은 값이 참인지도 안 본다** — `schema` 가 통째로 틀렸으면 둘이
      사이좋게 틀릴 수 있다. 그 자리는 `ledger_schema.unreadable()` 과
      드리프트 `--check` 가 든다. 여기가 드는 것은 **두 벌이 갈렸는가** 하나다.
      **대장 밖 실물 파일**도 안 본다(`lakecheck` · `contract` 소관).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

#: ★ 대장을 **직접 안 읽는다.** `ledger` 가 `sources.yaml` 의 주인이고 읽는 법도
#: 거기 있다(§175 — 같은 일을 하는 함수 다섯이 `or {}` 에서 갈려 있었다).
#: `tests/test_lake.py::test_ledger_is_loaded_through_one_door` 가 그 문을 센다.
from firelane.ledger import load_sources

ROOT = Path(__file__).resolve().parents[1]

#: 대조한 짝이 이보다 적으면 **수집기가 죽은 것**이다. 2026-10-02 실측 57
#: (칸 18 · 레이어 10 · 인코딩 26 · 행 3). 대장이 줄어도 이 아래로는 안 간다.
#: ★ 실측보다 낮게 둔다 — 못 박으면 항목 하나 지울 때마다 맞는 대장이 빨개진다.
NET_MIN = 40

#: 산문이 든 이름을 실측 칸과 댈 때의 문턱. **글자 수**다.
#: ★ 실측으로 골랐다 — 넷이면 오탐 셋(`관할구역` · `안전센터` · `법정동코드`),
#:   다섯이면 둘, **여섯이면 0**이다. 짧은 이름은 산문의 보통명사와 구별이
#:   안 된다. 넓히는 쪽은 오탐을 먼저 없앤 뒤에 한다(PLAN §13-4 가 같은 순서).
NAME_MIN = 6


def distinct_cols(d: dict) -> set[str]:
    """**한 소스만 쓰는 긴 칸 이름.** 산문에 나오면 그 소스의 것이어야 한다.

    ★ `retired` 는 안 본다. 실측으로 확인했다 — 폐기 넷 중 `schema` 를 가진 것이
      **0건**이고, `ledger_schema.py` 는 활성 소스만 읽는다. §178-2 의 그 칸
      (`지상식소화전`)도 활성 `hydrant_type` 의 것이다. 안 쓰는 블록을 읽으면
      「주인 블록 직접 해석」 래칫만 올라간다(`tests/test_lake.py`).
    ★ 여럿이 쓰는 이름은 뺀다. `소방서` · `위치` · `구분` 은 칸 이름이면서
      산문의 낱말이고, 그 둘을 가를 수가 없다.
    """
    seen: dict[str, int] = {}
    for e in (d.get("datasets") or {}).values():
        for c in {str(x) for x in ((e or {}).get("schema") or {}).get("columns") or []}:
            seen[c] = seen.get(c, 0) + 1
    return {c for c, n in seen.items() if n == 1 and len(c) >= NAME_MIN}


def names(what: str, c: str) -> bool:
    """산문이 그 칸을 **이름으로** 들었는가.

    ★ 둘러싼 글자가 이름의 일부면 아니다 — `A0` 가 `A0080000` 안에서 걸리던
      자리다. 낱말 경계를 안 보는 포함 검사는 축을 못 세운다.
    """
    for i in range(len(what) - len(c) + 1):
        if what[i:i + len(c)] != c:
            continue
        a, b = i - 1, i + len(c)
        if (a < 0 or not (what[a].isalnum() or what[a] == "_")) and \
           (b >= len(what) or not (what[b].isalnum() or what[b] == "_")):
            return True
    return False


def _stem(s: object) -> str:
    """`TL_SPRD_RW.shp` 와 `TL_SPRD_RW` 는 같은 레이어다. **알려진 확장자만** 접는다 — 이름에 점이 든 레이어
    (`Total.JUSUBG.20260801.TL_SPOT_TUNNEL.12210`)의 끝 `.12210` 을 확장자로 지우면 `.shp` 를 뗀 짝과 갈린다(Zm18)."""
    return re.sub(r"\.(?:shp|gpkg|geojson|json|csv)$", "", str(s)).strip()


def _enc(s: object) -> str:
    """`cp949` · `CP-949` · `CP_949` 는 같은 인코딩이다."""
    return str(s).lower().replace("-", "").replace("_", "")


def pairs(d: dict) -> list[tuple[str, str, bool, str]]:
    """대조한 짝 — `(항목, 축, 맞는가, 사연)`. **판정은 안 한다**(`judge` 소관)."""
    out: list[tuple[str, str, bool, str]] = []
    mine = distinct_cols(d)
    for k, e in sorted((d.get("datasets") or {}).items()):
        con = (e or {}).get("contract") or {}
        sch = (e or {}).get("schema") or {}
        req, cols = con.get("required_cols"), sch.get("columns")
        if req and cols:
            miss = [c for c in req if c not in cols]
            out.append((k, "칸", not miss,
                        f"`required_cols` {miss} 가 `schema.columns` 에 없다" if miss
                        else f"약속 {len(req)}칸 전부 실측에 있다"))
        lay, used = sch.get("layers"), sch.get("layer_used")
        if con.get("layer_must_exist") and lay and used:
            ok = _stem(used) in {_stem(x) for x in lay}
            out.append((k, "레이어", ok,
                        f"`layer_used` `{used}` 가 `schema.layers` {len(lay)}개에 없다" if not ok
                        else f"`{used}` 가 실측 목록에 있다"))
        enc, seen = con.get("encoding"), sch.get("encoding_seen")
        if enc and seen:
            ok = _enc(enc) == _enc(seen)
            out.append((k, "인코딩", ok, f"약속 `{enc}` · 읽은 것 `{seen}`"))
        rows, feat = con.get("rows"), sch.get("features")
        if isinstance(rows, int) and isinstance(feat, int):
            tol = con.get("rows_tolerance") or 0
            ok = abs(rows - feat) <= tol
            out.append((k, "행수", ok, f"약속 {rows} · 실측 {feat} (허용 ±{tol})"))
        what, cols = str((e or {}).get("what") or ""), sch.get("columns")
        # ★ `headerless` 는 뺀다. 그 소스의 실측 칸은 `c00` · `c01` 자리표이고,
        #   산문은 **실제 필드 이름**을 적어야 한다 — 댈 것이 서로 다른 축이다.
        if what and cols and not sch.get("headerless"):
            alien = sorted(c for c in mine - {str(x) for x in cols} if names(what, c))
            out.append((k, "산문", not alien,
                        f"`what` 이 남의 칸 {alien} 을 서술한다" if alien
                        else "`what` 이 남의 칸을 서술하지 않는다"))
    return out


def judge(got: list[tuple[str, str, bool, str]]) -> list[str]:
    """실패 사유들. 빈 리스트면 초록."""
    bad = [f"{k} [{axis}] {why}" for k, axis, ok, why in got if not ok]
    if len(got) < NET_MIN:
        bad.append(f"대조한 짝이 {len(got)} 쌍뿐이다 — **빈 그물**. "
                   f"선언 꼴이 바뀌었는지 봐라 (최소 {NET_MIN})")
    return bad


# ── 자기검사 ────────────────────────────────────────────────────
def _no_lake_words() -> bool:
    """레이크를 읽는 길이 **코드에** 들었는가. 들면 이 도구가 레이크 없는 기계에서
    죽고, 죽으면 CI 에서 **영원히 빨갛다** — 그런 빨강은 꺼진다(§318).

    ★ 「안 읽는다」를 말로만 적지 않는다. 산문(독스트링)과 이 판별식 자신은 빼고
      **코드만** 본다 — 설명은 그 이름을 들어야 하고, 코드는 들면 안 된다.
    """
    import ast
    words = ("require_lake", "data/raw", "pyogrio", "FIRE_LANE_RAW")
    src = Path(__file__).read_text(encoding="utf-8")
    code = "\n".join(ast.get_source_segment(src, n) or "" for n in ast.parse(src).body
                     if not isinstance(n, ast.Expr)
                     and getattr(n, "name", "") not in ("selftest", "_no_lake_words"))
    return not any(w in code for w in words)


def _one(contract: dict, schema: dict) -> dict:
    return {"datasets": {"x": {"contract": contract, "schema": schema}}}


def _prose(what: str, *, bare: bool = False) -> bool | None:
    """합성 대장에서 **산문 축의 답**만 꺼낸다. 축이 안 서면 `None`.

    소스 둘을 세운다 — `owner` 가 `지상식소화전` 을 가지고, `x` 는 안 가진다.
    §178-2 의 그날 모양이다.
    """
    sch = {"columns": ["c00", "c01"], "headerless": True} if bare \
        else {"columns": ["일반지하식소화전", "데이터기준일자"]}
    d = {"datasets": {"x": {"what": what, "schema": sch},
                      "owner": {"schema": {"columns": ["지상식소화전", "연번"]}}}}
    got = [ok for k, ax, ok, _ in pairs(d) if k == "x" and ax == "산문"]
    return got[0] if got else None


def selftest() -> int:
    """판별식 — 하나라도 틀리면 이 도구가 거짓말을 한다."""
    def g(c: dict, s: dict) -> list[bool]:
        return [ok for _, _, ok, _ in pairs(_one(c, s))]

    ok: list[tuple[str, bool]] = [
        ("칸이 들어 있으면 참", g({"required_cols": ["a"]}, {"columns": ["a", "b"]}) == [True]),
        ("칸이 빠지면 거짓", g({"required_cols": ["z"]}, {"columns": ["a"]}) == [False]),
        ("한쪽만 있으면 안 센다", g({"required_cols": ["a"]}, {}) == []),
        ("레이어 확장자를 접는다",
         g({"layer_must_exist": True}, {"layers": ["A"], "layer_used": "A.shp"}) == [True]),
        ("점이 든 레이어 이름도 접힌다",
         g({"layer_must_exist": True}, {"layers": ["T.1.12210"], "layer_used": "T.1.12210.shp"}) == [True]),
        ("레이어가 밖이면 거짓",
         g({"layer_must_exist": True}, {"layers": ["A"], "layer_used": "B.shp"}) == [False]),
        ("약속 안 했으면 레이어를 안 센다",
         g({}, {"layers": ["A"], "layer_used": "B.shp"}) == []),
        ("인코딩 표기를 접는다", g({"encoding": "CP-949"}, {"encoding_seen": "cp949"}) == [True]),
        ("인코딩이 다르면 거짓", g({"encoding": "utf-8"}, {"encoding_seen": "cp949"}) == [False]),
        ("행수 허용 안이면 참",
         g({"rows": 100, "rows_tolerance": 5}, {"features": 103}) == [True]),
        ("행수 허용 밖이면 거짓",
         g({"rows": 100, "rows_tolerance": 5}, {"features": 200}) == [False]),
        ("허용 없으면 정확히 같아야", g({"rows": 100}, {"features": 101}) == [False]),
        ("빈 그물이면 실패", any("빈 그물" in b for b in judge([("x", "칸", True, "")]))),
        ("실물 대장이 빈 그물이 아니다", len(pairs(load_sources())) >= NET_MIN),
        ("실물 대장에 다섯 축이 다 있다",
         {a for _, a, _, _ in pairs(load_sources())}
         == {"칸", "레이어", "인코딩", "행수", "산문"}),
        # ★ 산문 축 — 그물이 비면 영원히 초록이다.
        ("남의 칸 목록이 비지 않았다", len(distinct_cols(load_sources())) > 100),
        # ★ 합성 결함 — 남의 긴 칸을 산문이 들면 운다. **이 축의 카나리아다.**
        ("남의 칸을 서술하면 거짓", _prose("지상식소화전 418건") is False),
        ("제 칸을 서술하면 참", _prose("일반지하식소화전 171건") is True),
        ("자리표 칸(headerless)은 안 센다", _prose("지상식소화전 418건", bare=True) is None),
        ("낱말 경계를 본다", not names("A0080000 코드", "A0") and names("A0 코드", "A0")),
        ("짧은 이름은 안 센다", "위치" not in distinct_cols(load_sources())),
        ("레이크 경로를 안 든다", _no_lake_words()),
    ]
    for what, good in ok:
        print(f"   {'OK ' if good else '✗  '} {what}")
    bad = [w for w, g_ in ok if not g_]
    print(f"\n판별식 {len(ok)} · 실패 {len(bad)}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="대장의 약속과 실측이 서로를 반박하지 않는가")
    ap.add_argument("--table", action="store_true", help="대조한 짝 전부")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    got = pairs(load_sources())
    axes = sorted({ax for _, ax, _, _ in got})
    print(f"대조한 짝 {len(got)} · 축 {len(axes)} ({' · '.join(axes)})")
    if a.table:
        for k, ax, ok, why in got:
            print(f"   {'OK ' if ok else '✗  '} {k:22} [{ax}] {why}")

    if bad := judge(got):
        print("\n✗ 대장 교차 선언")
        for b in bad:
            print(f"   {b}")
        print("\n  **약속(`contract`)과 실측(`schema`)이 갈렸다.** 어느 쪽이 맞는지는")
        print("  사람이 정한다 — 실물이 바뀐 것이면 약속을 고치고, 잘못 읽은 것이면")
        print("  `uv run python tools/ledger_schema.py --apply` 로 다시 읽어라(레이크 필요).")
        return 1
    print("✓ 대장 교차 선언")
    return 0


if __name__ == "__main__":
    sys.exit(main())
