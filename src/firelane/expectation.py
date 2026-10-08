"""
expectation.py — **산출물이 기대와 맞는가.** 파이프라인이 끝난 뒤 묻는다.

── 왜 생겼나 (2026-10-08 · DECISIONS §431 · PLAN #157) ────────
`pipeline.py` 가 598줄로 **상한 600 에 붙어 살았다.** §426·§427 이 기능을
하나씩 더해 628 이 됐고, §431 이 차량 제원 주입을 더해 **646** 이 됐다.
상한에 붙어 사는 파일은 **기능 하나에 넘친다** — 예외 수를 올리는 것은
답이 아니다(「예외는 늘 자리가 아니다」· `sizecheck`).

★ 쪼갠 자리는 `PLAN #157` 이 **미리 적어 뒀다** — `expect` · `verify` ·
  `verify_ingest` · `verify_schema` · `web_size_verdict` 다섯이 「산출물이
  기대와 맞는가」 한 묶음이고 **밖에서 부르는 데가 없다.** 그래서 이 이사는
  부르는 쪽을 하나도 안 고친다(`pipeline.main()` 의 한 줄 빼고).

IN    data/golden/segments.fingerprint.json   기대 판정의 **정본**
      data/processed/_manifest.json           대장 건수
      web/data · data/processed 의 산출물과 스키마
OUT   없음 — **깨진 것을 목록으로 돌려준다.** 종료 코드는 부르는 쪽이 정한다
PARAM `INGEST_EXPECT` · `INGEST_TOL` · `WEB_MAX_MB`
밖    **기대 불일치를 세지 않는다.** 그것은 「예보와 실제의 대조」이고 사람이
      읽는 수다(§13-5 규칙 2). 여기는 기계적으로 답이 하나인 것만 든다.
      판정 폐포 **밖**이다 — `firelane.segments` 는 이 파일을 안 든다.
"""
from __future__ import annotations

from firelane.console import col
from firelane.paths import GOLDEN, PROCESSED, WEB

# ── 기대값 ────────────────────────────────────────────────────
# ★ 2026-08-18. 판정 숫자를 여기 하드코딩하지 않는다.
#   종전에는 정본이 셋이었다 — pipeline.EXPECT · golden 지문 · 문서.
#   하나가 바뀌면 셋을 손으로 맞춰야 했고, 그것을 맞추려고
#   `docnum_check` 를 만들었다. 동기화 도구가 필요하다는 것은
#   정본이 하나가 아니라는 뜻이다.
#
#   이제 `golden.py lock` 한 번이 정본을 옮긴다.
#   ingest 기준선만 여기 남는다 — 그것은 산출이 아니라 입력 계약이다.
# ★ 2026-08-23. 이 표는 선언만 있고 **아무도 읽지 않았다.** 죽은 코드였는데
#   지울 것이 아니라 배선할 것이었다 — PLAN §1 #13 이 정확히 이 게이트를
#   요구한다.
#
#   2026-08-21, `turn_restriction` 이 87 이어야 하는데 전국 44,125행(507배)을
#   읽고도 status 는 `OK` 였다. 좌표가 없는 DBF 라 `node_point` 가 만든 노드
#   집합으로만 걸러지는데, `node_point` 가 실패하면 필터가 통째로 사라진다.
#   재현 조건이 좁아 타이밍에 따라 오염되기도 하고 아니기도 한다 — 그만큼
#   위험하다.
#
#   `pipeline.EXPECT`(판정 숫자)를 지운 것과 혼동하지 말 것. 그것은 **산출**
#   이라 정본이 golden 지문이면 충분했다. 이것은 **입력 계약**이다.
#   산출물 지문은 입력이 507배로 늘어난 것을 알려주지 않는다.
INGEST_EXPECT = {"ngii1k": 14336, "ngii_road": 216, "road_link": 1508,
                 "road_rw": 1957, "node_link": 1366, "streetlight": 1786,
                 # ★ 이 한 줄이 08-21 사고를 잡는다.
                 "turn_restriction": 87}

# 건수 허용 오차. contract.py 의 rows_tolerance 와 같은 값이다.
INGEST_TOL = 0.30

# web/data 용량 상한(MB). ★ 세 곳이 같은 값을 봐야 한다 —
#   .github/workflows/contract.yml · tools/commit_policy.py · 여기.
#   tests/test_guards.py::test_webdata_limit_is_one_number 가 강제한다.
WEB_MAX_MB = 40


def expect() -> dict:
    """golden 지문에서 기대 판정을 읽는다. 없으면 검증을 건너뛴다."""
    import json
    f = GOLDEN / "segments.fingerprint.json"
    if not f.exists():
        return {}
    L1 = json.loads(f.read_text(encoding="utf-8"))["L1"]
    return {"segments": L1["n"], "verdict": L1["verdict"],
            "unknown_reason": L1["unknown_reason"]}


def verify_ingest() -> list[str]:
    """대장의 건수를 입력 계약과 대조한다. 어긋난 것을 목록으로 낸다.

    ★ 산출물이 아니라 **입력**을 본다. segments 지문이 같아도 입력이
      507배로 늘어난 것은 못 잡는다(PLAN §1 #13).
    """
    import json
    man = PROCESSED / "_manifest.json"
    if not man.exists():
        return []
    got = {d.get("key"): d.get("features")
           for d in json.loads(man.read_text(encoding="utf-8")).get("datasets", [])}
    bad = []
    print(col("\n입력 계약 (대장 건수)", "c"))
    for k, want in sorted(INGEST_EXPECT.items()):
        n = got.get(k)
        if n in (None, ""):
            bad.append(f"{k}: 대장에 건수가 없다 (status 확인)")
            print(f"  {k:18} {'—':>8}  " + col("★ 대장에 없음", "r"))
            continue
        n = int(n)
        lo, hi = want * (1 - INGEST_TOL), want * (1 + INGEST_TOL)
        ok = lo <= n <= hi
        if not ok:
            bad.append(f"{k}: {n:,} — 선언 {want:,} ±{INGEST_TOL:.0%} 밖")
        mark = col("OK", "g") if ok else col(f"★ 선언 {want:,}", "r")
        print(f"  {k:18} {n:8,}  {mark}")
    return bad


def verify_schema() -> list[str]:
    """스키마 필드 집합이 산출물 키와 **정확히** 같은가.

    ★ MASTER §18-5 R7 이 "계약 테스트에 컬럼 집합 == 스키마 키 집합 검사를
      넣는다" 고 적어놓고 안 넣었다. `test_schema_matches_data` 는
      `set(fields) >= set(REQUIRED)` — 부분집합만 본다.

      그래서 둘이 오래 어긋나 있었다(2026-08-23 발견).
        · `seg_label` — 08-21 에 만들고 08-22 에 툴팁 정본이 됐는데 스키마에 없음
        · `merged_n` · `cov_*` · `merge_why` — processed 전용인데 web 스키마가
          웹 필드처럼 서술. UI 가 그걸 보고 쓰면 undefined
      2026-08-18 에 MASTER §11 필드표로 똑같이 겪은 일이 스키마 쪽에 남아 있었다.
    """
    import json
    out = []
    for tag, seg, sch in (("web", WEB / "segments.geojson", WEB / "segments.schema.json"),
                          ("processed", PROCESSED / "segments.geojson",
                           PROCESSED / "segments.schema.json")):
        if not (seg.exists() and sch.exists()):
            continue
        feats = json.loads(seg.read_text(encoding="utf-8"))["features"]
        if not feats:
            continue
        real = set(feats[0]["properties"])
        doc = set(json.loads(sch.read_text(encoding="utf-8"))["fields"])
        for k in sorted(real - doc):
            out.append(f"{tag}: 산출물에 {k} 가 있는데 스키마에 없다")
        for k in sorted(doc - real):
            out.append(f"{tag}: 스키마가 {k} 를 적었는데 산출물에 없다")
    return out


def web_size_verdict(mb: float) -> list[str]:
    """`web/data` 크기 판정. 순수 함수 — 시험이 합성 수로 경계를 민다(§426-4).

    실물을 훑으면 「지금 초록인가」만 묻고 상한을 1000 으로 올려도 통과한다(§17-0).
    """
    if mb >= WEB_MAX_MB:
        return [f"web/data {mb:.1f}MB — CI 상한 {WEB_MAX_MB}MB 를 넘었다. CI 가 막는다"]
    return []


def verify() -> list[str]:
    """산출물이 기대값과 맞는지 본다. **깨진 것을 돌려준다**(§426-1 · §415 족).

    ★ **기대 불일치는 여기서 안 센다** — 그것은 「예보와 실제의 대조」이고 사람이
      읽는 수다(§13-5 규칙 2). 여기는 기계적으로 답이 하나인 것만 든다.
    """
    import json
    bad: list[str] = []
    p = WEB / "segments.schema.json"
    if not p.exists():
        return bad
    E = expect()
    if not E:
        print("\n  ! golden 지문 없음 — 판정 검증 생략. tools/golden.py lock")
        return bad
    s = json.loads(p.read_text(encoding="utf-8"))
    n = s.get("count")
    ok = n == E["segments"]
    want = E["segments"]
    mark = col("OK", "g") if ok else col(f"★ 기대 {want}", "y")
    print(f"\n  세그먼트 {n}  {mark}")
    import collections
    g = json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))
    v = collections.Counter(f["properties"]["verdict"] for f in g["features"])
    r = collections.Counter(
        f["properties"].get("unknown_reason")
        for f in g["features"] if f["properties"]["verdict"] == "unknown")
    for k, want in E["unknown_reason"].items():
        got = r.get(k, 0)
        mark = col("OK", "g") if got == want else col(f"★ 기대 {want}", "y")
        print(f"    unknown:{k:8s} {got:4d}  {mark}")
    for k, want in E["verdict"].items():
        got = v.get(k, 0)
        mark = col("OK", "g") if got == want else col(f"★ 기대 {want}", "y")
        print(f"    {k:10s} {got:4d}  {mark}")
    for d, label in ((WEB / "terrain", "지형 타일"), (WEB / "ortho", "항공영상")):
        if d.is_dir():
            print(f"  {label} {sum(1 for _ in d.rglob('*') if _.is_file())}장")
    if WEB.is_dir():
        mb = sum(f.stat().st_size for f in WEB.rglob("*") if f.is_file()) / 1e6
        # ★ 상한 정본은 하나여야 한다. contract.yml · tools/commit_policy.py 가
        #   40 인데 여기만 60 이었다(PLAN #12 에서 60→40 으로 내리면서 누락).
        #   40~60 구간에서 파이프라인은 초록불이고 CI 만 빨간불이 된다 —
        #   "로컬에서는 되는데 CI 가 막는다" 가 정확히 이런 자리에서 나온다.
        over = web_size_verdict(mb)
        warn = col(f"  ★ CI 상한 {WEB_MAX_MB}MB 초과", "r") if over else ""
        print(f"  web/data {mb:.0f} MB{warn}")
        bad += over
    return bad
