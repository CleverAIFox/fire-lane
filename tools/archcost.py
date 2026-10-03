#!/usr/bin/env python3
"""
archcost.py — **디렉 구조를 바꾸는 값을 먼저 매긴다.** (DECISIONS §368)

    uv run python tools/archcost.py              묶음별 값
    uv run python tools/archcost.py --files      파일마다
    uv run python tools/archcost.py --selftest

── 왜 이 도구가 생겼나 ─────────────────────────────────────────
「`src/firelane` 이 평평하다. GoF 든 모범사례든 보고 리팩할 게 있으면 해라」는
물음에서 시작했다. 그런데 **옮기면 값이 든다** — 그 값이 자리마다 다르고,
비싼 자리는 이 저장소에서 반나절짜리다.

```
판정 폐포 안       옮기면 `code_closure("firelane.segments")` 가 달라지고
                   `golden.py lock` 재잠금이 따라온다(1분 44초 + 전량 1회)
취입 폐포 안       샤드 `seal.code` 가 찢어진다 — 72 데이터셋 중 닿는 만큼
                   재빌드이고 `ngii_road` 는 8GB 기계에서 거의 OOM 이다(§243)
둘 다 밖           **공짜다.** import 경로와 그것을 적은 자리만 고친다
```

★ **그래서 「무엇을 옮길까」보다 「무엇이 공짜인가」가 먼저다.** §274 가 같은
  순서를 배웠다 — 「재기 전에 짰으면 #132 를 먼저 짰을 것이고, 짜고 나서
  아끼는 게 없네를 알았을 것이다」.

── GoF 가 이 모양의 레퍼런스가 아닌 이유 ───────────────────────
GoF 23패턴은 **객체가 협력하는 방식**을 다룬다(생성 · 구조 · 행위). 이 저장소의
`src` 는 **데이터프레임을 넘기는 함수들**이고 상태를 가진 객체 협력이 거의 없다 —
클래스가 `WidthEngine` · `RoadNameIndex` 둘뿐이다. 거기에 Factory 나 Strategy 를
얹으면 **얻는 것 없이 간접층만 는다.**

맞는 레퍼런스는 **꾸러미 원칙**이다 —

```
CCP  함께 바뀌는 것이 같은 꾸러미에  Martin, Agile Software Development, ch.28
CRP  같이 쓰이는 것이 같은 꾸러미에  같은 책
정보 은닉  바뀔 것을 모듈 경계로 감싼다  Parnas 1972 (CACM 15-12)
```

그리고 이 저장소는 그 원칙을 **이미 두 번 적용했다** — `seg/`(판정 계산 ·
§13 계열)와 `read/`(갈래별 읽기 · §274). 둘 다 축을 **크기가 아니라 「무엇을
읽는가 · 무엇이 같이 바뀌는가」**로 골랐고, 그것이 여기서도 기준이다.

★ `publish_*` 접두 아홉은 **평평한 이름공간의 교과서적 냄새**다(Fowler 가
  「Divergent Change」로, Martin 이 CCP 위반으로 적는 그것). 접두로 꾸러미를
  흉내 내고 있으면 꾸러미가 없는 것이다.

── 이 도구가 **안** 하는 것 ────────────────────────────────────
옮기지 않는다. **값만 매긴다.** 무엇을 옮길지는 PLAN 이 들고, 옮기는 배치는
재잠금·재빌드를 각오하고 들어가는 일이다(§339-3 의 그 규율).

RATCHETS  UNCLUSTERED — 내려가는 쪽으로만. **0 이 목표이고 지금 0 이다.**

IN    src/firelane/**/*.py · `firelane.shardseal.code_closure`
OUT   표준출력
밖    **옮기지 않는다.** 값만 매긴다. 그리고 **어느 묶음이 옳은가도 안 본다** —
      묶음 선언은 사람이 사유와 함께 적고, 이 도구는 **빠진 파일이 있는가**만 든다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "firelane"

#: 옮기는 값. 비싼 순서.
PRICE = {
    "재잠금": "판정 폐포 안이다 — 옮기면 `golden.py lock` 이 따라온다(전량 1회)",
    "재도장": "취입 폐포 안이다 — 샤드 `seal.code` 가 찢어진다(§243 · OOM 위험)",
    "둘 다": "두 폐포에 다 있다 — 가장 비싸다. 옮기지 않는 것이 기본이다",
    "공짜": "어느 폐포에도 없다 — import 경로와 그것을 적은 자리만 고친다",
}

#: 묶음 선언. **글로브 → (사유, 제안)**. 사유 없는 묶음은 선언이 아니다.
#: ★ 순서가 뜻이 있다 — 먼저 맞는 것이 이긴다. 좁은 것을 위에 둔다.
CLUSTERS: list[tuple[str, str, str]] = [
    ("seg/*.py",
     "판정 계산. 이미 꾸러미다 — `segments.py` 가 조립하고 계산은 여기 산다",
     "그대로"),
    ("read/*.py",
     "갈래별 읽기(§274). 이미 꾸러미이고 축이 **무엇을 읽는가**다",
     "그대로"),
    ("ops/*.py",
     "관제 ↔ 내비 중개자(§342 · §343). 이미 꾸러미다",
     "그대로"),
    ("krgis/*.py",
     "좌표계·국가공간정보 어댑터. 이미 꾸러미다",
     "그대로"),
    ("publish_*.py",
     "표출용 산출을 쓴다. **아홉이 접두로 꾸러미를 흉내 낸다** — CCP 위반의 "
     "교과서 꼴이고, 같이 바뀌는 것들이 같이 안 산다",
     "publish/ 로 묶는다"),
    ("webmanifest.py",
     "발행물의 계보를 쓴다. `publish_*` 와 같은 때 바뀐다",
     "publish/ 로 묶는다"),
    ("destinations.py",
     "목적지 색인을 **발행한다**(§181 · §183). 이름만 접두가 없다",
     "publish/ 로 묶는다"),
    ("display_scope.py",
     "표출 범위 단계. 판정 지문 **밖**이라고 스스로 적는다(§220) — 즉 발행 쪽이다",
     "publish/ 로 묶는다"),
    ("ortho.py",
     "정사영상 타일을 굽는다. 래스터 쪽이고 벡터 발행과 다른 때 바뀐다",
     "raster/ 로 묶는다"),
    ("terrain.py",
     "Terrain-RGB 타일을 굽는다. `ortho` 와 같은 때 바뀐다",
     "raster/ 로 묶는다"),
    ("mercator.py",
     "타일 좌표 변환. `ortho` · `terrain` 둘만 쓴다",
     "raster/ 로 묶는다"),
    ("lake.py",
     "레이크 실물을 본다. 대장 쪽이지만 **취입 폐포 밖**이다",
     "두고 본다 — `ledger.py` 가 폐포 안이라 꾸러미가 경계를 가른다"),
    ("datalog.py",
     "대장 ↔ 실물 대조 명령. 같은 경계 문제를 공유한다",
     "두고 본다 — 위와 같은 사유"),
    ("inventory.py",
     "레이크 목록 — 어디에 무엇이 몇 바이트 있나. 같은 경계 문제를 공유한다",
     "두고 본다 — 위와 같은 사유"),
    ("layerfsck.py",
     "계층 선언 ↔ 실물. 같은 경계 문제",
     "두고 본다 — 위와 같은 사유"),
    ("layers.py",
     "계층 이름 ↔ 경로. `paths.py` 가 **두 폐포에 다** 있어 같이 못 옮긴다",
     "그대로 — 짝이 폐포 안이다"),
    ("providers.py",
     "제공기관 조회(§73). 대장을 읽지만 폐포 밖이다",
     "두고 본다"),
    ("generated.py",
     "생성물 족 선언. 발행·레이크 둘 다 걸린다",
     "그대로 — 어느 꾸러미에도 온전히 안 속한다"),
    ("pipeline.py",
     "단계 선언과 실행. **진입점이다** — 꾸러미 안으로 넣으면 더 깊어진다",
     "그대로"),
    ("contract.py",
     "raw 계약 검사. 단계 앞에 서는 독립 관문이다",
     "그대로"),
    ("console.py",
     "출력 꼴 하나(색 · 들여쓰기). 어디서나 쓰므로 꾸러미 안으로 못 내린다",
     "그대로"),
    ("probe.py",
     "조사 도구가 같이 쓰는 도우미. 꾸러미로 내리면 조사 쪽에서 더 깊어진다",
     "그대로"),
    ("quiet_gdal.py",
     "GDAL 경고 억제. 읽는 자리 전부가 쓰므로 뿌리가 맞다 — `console` 과 같은 사유",
     "그대로"),
    ("normalize_raw.py",
     "원본명 → 정규명 규칙(§18-2a). **취입 앞**이고 폐포 밖이다",
     "두고 본다 — `prep` 과 같은 꾸러미가 될 수 있으나 `prep` 이 폐포 안이다"),
    ("intake_rules.py",
     "획득 규칙. `normalize_raw` 의 짝",
     "두고 본다 — 위와 같은 사유"),
    ("skeleton.py",
     "뼈대 후보(R3). 판정 폐포에서 **일부러 뺐다**(§266-2) — 되돌리면 재잠금이다",
     "그대로 — 뺀 것이 이 파일의 요점이다"),
    ("nfa_compare.py",
     "소방서 지정 대조. 우리 폭의 유일한 외부 검증축(MASTER §4)",
     "그대로"),
    ("transition.py",
     "seg_uid 전이표(R2 · §187). 뼈대 교체 때만 쓴다",
     "그대로"),
    ("vehiclecard.py",
     "차량 관리카드(PDF) 파싱(§172). 차량 제원이 들어오는 유일한 길이고 독립이다",
     "그대로"),
    ("*.py",
     "폐포 안이거나 뿌리의 공용이다 — 묶음 제안은 폐포가 정한다",
     "폐포가 정한다"),
]

#: 묶음 선언에 안 걸린 파일 수. **0 이 목표이고 지금 0 이다.**
UNCLUSTERED = 0
RATCHETS = {"UNCLUSTERED": "down"}


def closures() -> tuple[set[Path], set[Path]]:
    """(판정 폐포, 취입 폐포). **경로로** 든다.

    ★ 이름(`p.name`)으로 집합을 만들면 **`__init__.py` 둘이 하나로 접힌다** —
      이 배치가 실제로 그렇게 세어 폐포를 16 으로 읽었고, `test_r3` 가 드는
      17 과 어긋났다. **세는 법이 틀리면 설계가 틀린다**(§274-1 과 같은 자리).
    """
    # ★ `sys.path` 를 안 만진다 — 패키지이고 `test_layering` 이 그 손질을 막는다.
    #   `golden.py` 가 같은 자리에서 같은 꼴로 늦게 import 한다.
    from firelane.shardseal import code_closure
    return ({p.resolve() for p in code_closure("firelane.segments")},
            {p.resolve() for p in code_closure("firelane.ingest")})


def price_of(p: Path, seg: set[Path], ing: set[Path]) -> str:
    r = p.resolve()
    if r in seg and r in ing:
        return "둘 다"
    if r in seg:
        return "재잠금"
    if r in ing:
        return "재도장"
    return "공짜"


def cluster_of(rel: str) -> tuple[str, str, str]:
    from fnmatch import fnmatch
    for pat, why, plan in CLUSTERS:
        if fnmatch(rel, pat):
            return pat, why, plan
    return "", "", ""


def rows() -> list[dict]:
    seg, ing = closures()
    out = []
    for p in sorted(SRC.rglob("*.py")):
        rel = p.relative_to(SRC).as_posix()
        pat, why, plan = cluster_of(rel)
        out.append({"rel": rel, "lines": len(p.read_text(encoding="utf-8").splitlines()),
                    "price": price_of(p, seg, ing), "pat": pat, "why": why, "plan": plan})
    return out


def unclustered() -> list[str]:
    return [r["rel"] for r in rows() if not r["pat"]]


def ratchet_values() -> dict[str, int]:
    return {"UNCLUSTERED": len(unclustered())}


def selftest() -> int:
    """★ 합성 입력으로 **값 매김과 묶음 고르기**를 민다."""
    bad = []
    a, b = Path("/x/seg/width.py"), Path("/x/read/dbf.py"),
    if price_of(a, {a.resolve()}, set()) != "재잠금":
        bad.append("판정 폐포를 재잠금으로 안 센다")
    if price_of(b, set(), {b.resolve()}) != "재도장":
        bad.append("취입 폐포를 재도장으로 안 센다")
    if price_of(a, {a.resolve()}, {a.resolve()}) != "둘 다":
        bad.append("두 폐포에 다 있는 것을 안 가른다")
    if price_of(a, set(), set()) != "공짜":
        bad.append("폐포 밖을 공짜로 안 센다")
    # 좁은 글로브가 넓은 것을 이긴다
    if cluster_of("publish_web.py")[2] != "publish/ 로 묶는다":
        bad.append("`publish_*` 가 `*.py` 에 먹혔다 — 순서가 뜻을 잃었다")
    if cluster_of("segments.py")[0] != "*.py":
        bad.append("뿌리 공용이 넓은 글로브에 안 걸린다")
    if cluster_of("seg/width.py")[2] != "그대로":
        bad.append("꾸러미 안 파일이 안 걸린다")
    # 사유가 본체다
    thin = [p for p, w, _ in CLUSTERS if len(w) < 20]
    if thin:
        bad.append(f"사유가 너무 짧다: {thin}")
    # ★ 빈 그물 — 파일을 하나도 못 읽으면 `UNCLUSTERED` 가 언제나 0 이다
    if len(rows()) < 50:
        bad.append(f"`src` 에서 파일 {len(rows())}개밖에 못 읽었다 — 수집기를 의심하라")
    # ★ 이름으로 세면 폐포가 접힌다는 그 사실 자체를 문다
    seg, _ = closures()
    if len({p.name for p in seg}) >= len(seg):
        bad.append("폐포에 같은 이름 둘이 없다 — `closures()` 머리말의 사유가 낡았다")
    for x in bad:
        print(f"  ✗ {x}")
    print(f"{'✗' if bad else '✓'} 자기검사 판별식 10")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", action="store_true", help="파일마다 한 줄")
    ap.add_argument("--ratchet", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    rs = rows()
    if a.ratchet:
        print(f"UNCLUSTERED {len(unclustered())}")
        return 0

    tot = sum(r["lines"] for r in rs)
    print(f"src/firelane  파일 {len(rs)} · 줄 {tot:,}\n")
    print("── 옮기는 값 ───────────────────────────────────────────")
    for k in ("재잠금", "재도장", "둘 다", "공짜"):
        g = [r for r in rs if r["price"] == k]
        if not g:
            continue
        print(f"  {k:<5} 파일 {len(g):>3} · 줄 {sum(x['lines'] for x in g):>6,}"
              f"  ({100 * sum(x['lines'] for x in g) / tot:.0f}%)")
        print(f"        {PRICE[k]}")

    print("\n── 제안별 ──────────────────────────────────────────────")
    plans: dict[str, list[dict]] = {}
    for r in rs:
        plans.setdefault(r["plan"], []).append(r)
    for plan, g in sorted(plans.items(), key=lambda kv: -sum(x["lines"] for x in kv[1])):
        free = sum(1 for x in g if x["price"] == "공짜")
        print(f"  {plan:<34} 파일 {len(g):>3} · 줄 {sum(x['lines'] for x in g):>6,}"
              f" · 공짜 {free}/{len(g)}")

    if a.files:
        print("\n── 파일마다 ────────────────────────────────────────────")
        for r in sorted(rs, key=lambda x: (x["plan"], -x["lines"])):
            print(f"  {r['lines']:>5} {r['price']:<5} {r['rel']:<34} {r['plan']}")

    miss = unclustered()
    if miss:
        print(f"\n✗ 묶음 선언에 안 걸린 파일 {len(miss)}\n  " + "\n  ".join(miss))
        print("  ★ 새 파일이 생기면 **어느 묶음인지 정해야** 한다. 넓은 글로브가")
        print("    받아주면 그 결정이 조용히 미뤄지므로, 안 걸린 수를 래칫이 든다.")
        return 1
    print(f"\n✓ 묶음 선언에 안 걸린 파일 0 · 래칫 {UNCLUSTERED}")
    print("  ★ 이 도구는 **옮기지 않는다.** 값만 매긴다 — 옮기는 것은 PLAN 이 든다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
