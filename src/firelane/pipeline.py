#!/usr/bin/env python3
"""
pipeline.py — 파이프라인 단일 진입점.

    fire-lane                       # 전체
    fire-lane --from segments       # 그 단계부터 끝까지
    fire-lane --only terrain ortho
    fire-lane --check               # 실행 없이 상태만

    (동등:  python -m firelane.pipeline ...)

★ 단계를 하나씩 손으로 치면 반드시 빠뜨린다.
  terrain 을 건너뛰면 지형이 안 뜨고, publish_web 을 건너뛰면 지도가 옛 데이터를 본다.
  순서도 중요하다. publish_web 은 terrain/ortho 가 기록한 타일 범위를 읽어 보존한다.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from firelane import lineage
from firelane.paths import PROCESSED, RAW, ROOT, WEB

for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8")
    except Exception:
        pass


@dataclass(frozen=True)
class Step:
    """단계 하나. **읽는 것과 쓰는 것을 선언한다.**

    ★ 2026-08-18 도입. 종전 STEPS 는 이름·스크립트·설명·확인경로 4-튜플이었고
      단계 간 의존이 어디에도 없었다. 그래서 `--only publish` 만 돌렸을 때
      terrain 이 `segments.geojson` 에 넣던 `z` 가 소리 없이 빠진 채
      커밋됐다. `docnum_check` 의 필드표 대조가 우연히 잡았을 뿐이다.

      선언이 있으면 셋이 따라온다.
        · 하류 무효화 — 상류를 다시 돌리면 하류 산출물에 stale 을 붙인다
        · --from 유도 — 무엇이 바뀌었는지에서 시작 단계를 계산한다
        · writes 충돌 — 두 단계가 같은 파일을 쓰면 즉시 실패한다

    mutates 는 읽고 그 자리에 덧쓰는 것이다. terrain 이 segments.geojson 에
    z 를 넣는 것이 그렇다. reads/writes 로 쪼개 적으면 자기 자신에 의존하는
    모양이 되어 순환으로 보인다. 별도 항으로 두어 **덧쓰기라는 사실 자체를
    드러낸다** — 이 구조가 z 소실의 원인이었다.
    """
    name: str
    module: str                     # firelane.<module> — `python -m` 으로 부른다
    desc: str
    out: Path                       # --check 에서 존재를 보는 대표 산출물
    reads: tuple[Path, ...] = ()
    writes: tuple[Path, ...] = ()
    mutates: tuple[Path, ...] = ()

    @property
    def produces(self) -> tuple[Path, ...]:
        return self.writes + self.mutates

    @property
    def consumes(self) -> tuple[Path, ...]:
        return self.reads + self.mutates


def matches(path: Path, decl: Path) -> bool:
    """선언이 경로를 덮는가. 선언 이름에 `*` 가 있으면 글롭으로 본다."""
    if "*" in decl.name:
        return path.parent == decl.parent and path.match(decl.name)
    return path == decl


P = PROCESSED
STEPS = [
    Step("ingest", "ingest", "raw → processed (19종)",
         P / "_manifest.json",
         reads=(RAW,),
         # 소스 19종을 정규화한다. 하나씩 적으면 대장(sources.yaml)과
         # 이중 관리가 되므로 패턴으로 선언한다. matches() 가 풀어준다.
         writes=(P / "_manifest.json", P / "*_5186.gpkg")),
    Step("segments", "segments", "노딩 → 폭 → 판정",
         P / "segments.geojson",
         reads=(P / "ngii1k_5186.gpkg", P / "road_link_5186.gpkg",
                P / "road_rw_5186.gpkg", P / "node_link_5186.gpkg",
                P / "cctv_5186.gpkg", P / "_manifest.json"),
         writes=(P / "segments.geojson", P / "segments_5186.gpkg",
                 P / "nfa_compare.json", P / "seg_uid_map.csv")),
    Step("streetlight", "streetlight", "가로등 → 지점 집계",
         P / "streetlight_point.geojson",
         reads=(P / "streetlight_5186.gpkg",),
         writes=(P / "streetlight_point.geojson",)),
    Step("terrain", "terrain", "공개DEM → Terrain-RGB 타일",
         WEB / "terrain",
         writes=(WEB / "terrain", P / "dem_scope.tif"),
         # ★ 여기가 z 소실의 자리다. segments.geojson 을 읽어 z 를 덧쓴다.
         # ★ _manifest.json 도 reads 가 아니라 mutates 다. terrain 기록을
         #   덧쓴다("→ _manifest.json 에 terrain 기록"). reads 로 적어두면
         #   선언과 실제가 달라 하류 무효화 경고가 안 뜬다.
         mutates=(P / "segments.geojson", P / "_manifest.json")),
    Step("ortho", "ortho", "항공정사영상 → 배경 타일",
         WEB / "ortho",
         writes=(WEB / "ortho",)),
    Step("publish", "publish_web", "→ web/data",
         WEB / "segments.geojson",
         reads=(P / "segments.geojson", P / "streetlight_point.geojson"),
         # ★ web/data/_manifest.json 은 publish 가 마지막에 쓰는 계보다.
         #   종전에는 tools/web_manifest.py 를 사람이 따로 돌려야 했고
         #   아무도 안 돌렸다(2026-08-22 CI 가 처음 잡음).
         writes=(WEB / "segments.geojson", WEB / "segments.schema.json",
                 WEB / "_manifest.json")),
]


def expand(decls) -> list[Path]:
    """선언을 실제 경로로 편다. `*` 가 있으면 글롭, 없으면 그대로."""
    out: list[Path] = []
    for d in decls:
        if "*" in d.name:
            out += sorted(q for q in d.parent.glob(d.name) if q.exists())
        else:
            out.append(d)
    return out


def downstream(names: set[str]) -> list[Step]:
    """주어진 단계들의 산출물에 (간접적으로라도) 의존하는 뒤쪽 단계."""
    dirty = [q for s in STEPS if s.name in names for q in s.produces]
    out = []
    for s in STEPS:
        if s.name in names:
            continue
        if any(matches(r, d) for r in s.consumes for d in dirty):
            out.append(s)
            dirty += list(s.produces)
    return out

# ── 기대값 ────────────────────────────────────────────────────
# ★ 2026-08-18. 판정 숫자를 여기 하드코딩하지 않는다.
#   종전에는 정본이 셋이었다 — pipeline.EXPECT · golden 지문 · 문서.
#   하나가 바뀌면 셋을 손으로 맞춰야 했고, 그것을 맞추려고
#   `docnum_check` 를 만들었다. 동기화 도구가 필요하다는 것은
#   정본이 하나가 아니라는 뜻이다.
#
#   이제 `golden.py lock` 한 번이 정본을 옮긴다.
#   ingest 기준선만 여기 남는다 — 그것은 산출이 아니라 입력 계약이다.
INGEST_EXPECT = {"ngii1k": 14336, "ngii_road": 216, "road_link": 1508,
                 "road_rw": 1957, "node_link": 1366, "streetlight": 1786}


def expect() -> dict:
    """golden 지문에서 기대 판정을 읽는다. 없으면 검증을 건너뛴다."""
    import json
    f = ROOT / "data/golden/segments.fingerprint.json"
    if not f.exists():
        return {}
    L1 = json.loads(f.read_text(encoding="utf-8"))["L1"]
    return {"segments": L1["n"], "verdict": L1["verdict"],
            "unknown_reason": L1["unknown_reason"]}


def c(t, k):
    return f"\033[{k}m{t}\033[0m" if sys.stdout.isatty() else t


def check_only():
    print(f"RAW        {RAW}")
    if RAW.is_dir():
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"           {n}개 파일 · {sz:.2f} GB")
    else:
        print(c("           없다. FIRE_LANE_RAW 설정 또는 normalize_raw.py 실행", "33"))
    print()
    for s in STEPS:
        name, desc, out = s.name, s.desc, s.out
        ok = out.exists()
        mark = c("OK  ", "32") if ok else c("없음", "33")
        extra = ""
        if ok and out.is_dir():
            extra = f"  ({sum(1 for _ in out.rglob('*') if _.is_file())}개)"
        print(f"  {mark} {name:9s} {desc:28s} {out.relative_to(ROOT)}{extra}")


def verify():
    """산출물이 기대값과 맞는지 본다."""
    import json
    p = WEB / "segments.schema.json"
    if not p.exists():
        return
    E = expect()
    if not E:
        print("\n  ! golden 지문 없음 — 판정 검증 생략. tools/golden.py lock")
        return
    s = json.loads(p.read_text(encoding="utf-8"))
    n = s.get("count")
    ok = n == E["segments"]
    want = E["segments"]
    mark = c("OK", "32") if ok else c(f"★ 기대 {want}", "33")
    print(f"\n  세그먼트 {n}  {mark}")
    import collections
    g = json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))
    v = collections.Counter(f["properties"]["verdict"] for f in g["features"])
    r = collections.Counter(
        f["properties"].get("unknown_reason")
        for f in g["features"] if f["properties"]["verdict"] == "unknown")
    for k, want in E["unknown_reason"].items():
        got = r.get(k, 0)
        mark = c("OK", "32") if got == want else c(f"★ 기대 {want}", "33")
        print(f"    unknown:{k:8s} {got:4d}  {mark}")
    for k, want in E["verdict"].items():
        got = v.get(k, 0)
        mark = c("OK", "32") if got == want else c(f"★ 기대 {want}", "33")
        print(f"    {k:10s} {got:4d}  {mark}")
    for d, label in ((WEB / "terrain", "지형 타일"), (WEB / "ortho", "항공영상")):
        if d.is_dir():
            print(f"  {label} {sum(1 for _ in d.rglob('*') if _.is_file())}장")
    if WEB.is_dir():
        mb = sum(f.stat().st_size for f in WEB.rglob("*") if f.is_file()) / 1e6
        warn = "" if mb < 60 else c("  ★ CI 상한 60MB 초과", "31")
        print(f"  web/data {mb:.0f} MB{warn}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", choices=[s.name for s in STEPS],
                    help="이 단계부터 끝까지")
    ap.add_argument("--only", nargs="+", choices=[s.name for s in STEPS],
                    help="이 단계만")
    ap.add_argument("--check", action="store_true", help="실행 없이 상태만")
    ap.add_argument("--no-test", action="store_true", help="계약 테스트 생략")
    ap.add_argument("--reset-lineage", action="store_true",
                    help="계보 기록을 지우고 시작한다 (교착 탈출구)")
    a = ap.parse_args()

    if a.reset_lineage:
        # ★ 명시적 탈출구. 지금까지는 _lineage.json 을 손으로 rm 하는 것이
        #   유일한 방법이었고 문서에도 없었다. 몰래 지우는 것보다 로그에
        #   남는 편이 낫다 — 무엇을 근거로 넘어갔는지가 남는다.
        _lin = PROCESSED / "_lineage.json"
        if _lin.exists():
            _lin.unlink()
            print(f"★ 계보 기록을 지웠다: {_lin}")
            print("  이번 실행의 입력은 대조 없이 진행한다. "
                  "산출물이 낡았을 가능성을 사람이 책임진다.")
        else:
            print("· 계보 기록이 이미 없다")

    if a.check:
        check_only()
        return

    steps = STEPS
    if a.only:
        steps = [s for s in STEPS if s.name in a.only]
    elif a.frm:
        i = [s.name for s in STEPS].index(a.frm)
        steps = STEPS[i:]

    if not RAW.is_dir() or not any(RAW.rglob("*.zip")):
        print(c(f"★ raw 가 비어 있다: {RAW}", "31"))
        print("  export FIRE_LANE_RAW=... 또는")
        print("  python -m firelane.normalize_raw <다운로드폴더>")
        if "ingest" in [s.name for s in steps]:
            sys.exit(1)

    # ★ 하류 무효화. --only / --from 으로 일부만 돌리면 그 산출물에
    #   의존하는 뒤쪽 단계의 결과가 낡는다. 2026-08-18 에 `--only publish`
    #   만 돌려 terrain 이 넣던 z 가 빠진 채 커밋됐다.
    skipped = downstream({s.name for s in steps}) if len(steps) < len(STEPS) else []
    if skipped:
        print(c("★ 하류가 낡는다 — 아래 단계도 돌려야 한다", "33"))
        for s in skipped:
            why = [str(r.name) for r in s.consumes
                   if any(r in q.produces for q in steps)]
            print(f"    {s.name:11s} ← {' · '.join(why)}")
        print(c(f"  권장:  --from {min(skipped, key=lambda s: [x.name for x in STEPS].index(s.name)).name}\n", "33"))

    print(f"실행 {len(steps)}단계: {' → '.join(s.name for s in steps)}\n")
    t0 = time.time()
    # ★ 이번 실행에서 성공한 단계. 계보 검사가 "방금 갱신된 입력" 과
    #   "낡은 입력" 을 구분하는 근거다(lineage.verify 의 fresh).
    done: set[str] = set()
    for s in steps:
        name, desc = s.name, s.desc
        print(c(f"── {name}  {desc}", "36"))
        t = time.time()
        # ★ 계보는 파이프라인이 본다. 단계 스크립트는 계보를 모른다.
        #   종전에는 segments.py 안에서 lineage_check 를 불렀고, 그래서
        #   단계마다 손으로 배선해야 했다. --only publish 가 그 구멍으로
        #   빠져나가 z 를 소실시켰다. Step 선언이 이미 reads/writes 를
        #   알고 있으므로 여기서 일괄로 처리한다.
        try:
            lineage.verify(PROCESSED, ROOT, s, expand, STEPS, fresh=done)
        except lineage.LineageError as e:
            print(c(f"\n★ {e}", "31"))
            sys.exit(1)

        # ★ 파일 경로가 아니라 모듈로 부른다(`python -m firelane.ingest`).
        #   종전 `python -m firelane.ingest` 는 cwd 에 의존했고, 무엇보다
        #   사람이 그 명령을 그대로 손으로 칠 수 있었다 — 그러면 대장만
        #   갱신되고 계보 기록은 빠져 다음 실행이 교착했다(HANDOFF §5-5,
        #   08-21 에 세 번). 이제 단계 모듈은 파이프라인이 부르는 대상이지
        #   사람이 치는 명령이 아니다. `-m` 은 그 사실을 표기로 만든다.
        r = subprocess.run([sys.executable, "-m", f"firelane.{s.module}"], cwd=ROOT)
        if r.returncode:
            print(c(f"\n★ {name} 실패. 여기서 멈춘다.", "31"))
            print(f"  고친 뒤: fire-lane --from {name}")
            sys.exit(1)
        lineage.record(PROCESSED, ROOT, s, expand)
        done.add(s.name)
        print(c(f"   {time.time()-t:.1f}s", "90"))

    if not a.no_test:
        print(c("── 계약 테스트", "36"))
        r = subprocess.run([sys.executable, "-m", "pytest",
                            "tests/test_contract.py", "-q"], cwd=ROOT)
        if r.returncode:
            print(c("\n★ 계약 테스트 실패. 머지하지 말 것.", "31"))
            sys.exit(1)

    verify()
    print(f"\n총 {time.time()-t0:.1f}s")
    print("\n지도 확인:  uv run python tools/serve.py")


if __name__ == "__main__":
    main()
