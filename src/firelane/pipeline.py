#!/usr/bin/env python3
"""
pipeline.py — 파이프라인 단일 진입점.

    uv run fire-lane                       # 전체
    uv run fire-lane --from segments       # 그 단계부터 끝까지
    uv run fire-lane --only terrain ortho
    uv run fire-lane --check               # 실행 없이 상태만

    (동등:  python -m firelane.pipeline ...)

★ 단계를 하나씩 손으로 치면 반드시 빠뜨린다.
  terrain 을 건너뛰면 지형이 안 뜨고, publish_web 을 건너뛰면 지도가 옛 데이터를 본다.
  순서도 중요하다. publish_web 은 terrain/ortho 가 기록한 타일 범위를 읽어 보존한다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from firelane import lineage
from firelane.console import col
from firelane.expectation import verify, verify_ingest, verify_schema
from firelane.paths import PROCESSED, RAW, ROOT, WEB
from firelane.stagerun import ENOMEM_RC as INGEST_ENOMEM_RC

for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8")
    except Exception:  # noqa: S110, BLE001 — 아래 ★
        # ★ 삼키는 사유(§371). `normalize_raw` 와 같은 자리이고 같은 사유다 —
        #   다시 설정할 수 없는 표준출력에서 터뜨리면 파이프라인이 시작도
        #   못 한다. 출력 인코딩 자체는 `encoding_check` 가 든다.
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


#: 읽기만 하고 **절대 안 만드는** 저장소 추적 입력 — 앞 단계 산출도 `RAW` 도 아닌
#: **셋째 갈래**다. `BACKWARD` 는 틀린 집이고(해소 조건이 없다), 양방향 검사가
#: `tests/test_guards.py` 에 있다. 왜 필요했는지는 §426-3.
REPO_INPUTS: tuple[Path, ...] = (ROOT / "web" / "config.js",)   # 판정 색·과장 배수의 정본

P = PROCESSED
# ★ 2026-09-03. 선언을 실물에 맞췄다. 종전에는 STEPS 가 실제 산출물의
#   부분집합이었고, 그래서 이 파일 머리말이 약속한 셋(writes 충돌 ·
#   하류 무효화 · 후진 의존)이 **볼 것이 없어 전부 조용했다.**
#   `tests/test_declaration_reality.py` 가 소스와 대조해 재발을 막는다.
STEPS = [
    Step("ingest", "ingest", "raw → processed",
         P / "_manifest.json",
         reads=(RAW,),
         # 소스를 하나씩 적으면 대장(sources.yaml)과 이중 관리가 되므로
         # 패턴으로 선언한다. matches() 가 풀어준다.
         # ★ 다만 **하류가 이름으로 읽는 것**은 명시한다. 글롭만 두면
         #   test_every_read_is_produced_by_an_earlier_step 이 하류의
         #   reads 를 못 잇는다 — 선언의 목적이 그 연결이다.
         writes=(P / "_manifest.json", P / "*_5186.gpkg", P / "building.geojson",
                 P / "boundary_emd.geojson", P / "fire_station.geojson",
                 P / "hydrant_point.geojson", P / "cctv.geojson",
                 P / "poi_store.geojson", P / "road_intrvl.geojson",
                 # ★ 2026-09-17 (§181). 목적지 색인 원천 — publish 가 이름으로 읽는다
                 P / "navi_build.csv", P / "navi_jibun.csv", P / "civil_office.geojson",
                 # ★ 2026-09-22 (§215-1). 회전제한 표 — publish_navi 가 이름으로 읽는다
                 P / "turn_restriction.csv",
                 # ★ 2026-09-22 (§216-3). publish_context · publish_navi 가 이름으로 읽는다
                 P / "speedbump.csv", P / "speed_cam.csv", P / "nfa_dispatch_119.csv",
                 P / "nfa_rescue.csv", P / "nfa_fire_incident.csv", P / "parking_enforce.csv",
                 # ★ 2026-10-06 (§426-2). **내는 쪽도 빠져 있었다.** 읽는 쪽에
                 #   적자마자 `test_every_read_is_produced_by_an_earlier_step` 이
                 #   이 줄을 요구했다 — 한쪽만 적으면 다른 검사가 대신 운다.
                 P / "enforce_cam.csv")),
    Step("segments", "segments", "노딩 → 폭 → 판정",
         P / "segments.geojson",
         reads=(P / "ngii1k_5186.gpkg", P / "ngii1k_center_5186.gpkg",
                P / "ngii1k_xsec_5186.gpkg",
                P / "road_link_5186.gpkg", P / "road_rw_5186.gpkg",
                P / "node_link_5186.gpkg", P / "cctv_5186.gpkg",
                P / "streetlight_5186.gpkg", P / "road_intrvl.geojson",
                P / "fire_station.geojson",
                P / "_manifest.json"),
         # ★ route_vehicle.csv 가 여기 없어서 publish 가 stale 로 안 잡혔고,
         #   커밋된 web/data/route_vehicle.json 이 이틀 낡은 채 전 게이트를
         #   통과했다(PLAN #70 · DECISIONS §39).
         writes=(P / "segments.geojson", P / "segments_5186.gpkg",
                 P / "segments.schema.json", P / "corridor_5186.gpkg",
                 P / "seg_uid_map.csv",
                 P / "route_vehicle.csv")),
    # ★ 2026-09-25 (PLAN §1 #124). `seg/report.py::nfa_compare` 를 자기 단계로
    #   내렸다. 그 안의 `from firelane import ledger` 한 줄이 ledger · naming ·
    #   scope · kinds = 1,137줄을 판정 지문(= `firelane.segments` import 닫힘)에
    #   넣고 있었다 — **파일명 문법 파서를 고쳐도 판정 게이트가 울었다.**
    #   폐포 21 → 17 파일. 순서는 순방향이다 — segments(판정을 낸다) →
    #   nfa_compare(그것을 외부 자료와 댄다).
    Step("nfa_compare", "nfa_compare", "소방서 지정 구간 ↔ 우리 폭 대조",
         P / "nfa_compare.json",
         reads=(P / "segments_5186.gpkg", P / "road_link_5186.gpkg"),
         writes=(P / "nfa_compare.json",)),
    # ★ 2026-09-23 (PLAN §13 W3-6). `segments._write_scope()` 를 자기 단계로 내렸다.
    #   표출 상수(DISPLAY_BUFFER · DISPLAY_CLOSE)가 `seg/params.py` 에 있으면 판정 지문
    #   (= `firelane.segments` import 닫힘) 안이라, **지도 여백만 고쳐도 판정 게이트가
    #   울고 재잠금이 따라왔다.** 순서는 그대로 순방향이다 —
    #   segments(회랑을 낸다) → scope → ortho · publish(스코프를 읽는다).
    Step("scope", "display_scope", "표출 범위 → scope_5186.gpkg",
         P / "scope_5186.gpkg",
         reads=(P / "boundary_emd_5186.gpkg", P / "corridor_5186.gpkg",
                P / "fire_station.geojson"),
         writes=(P / "scope_5186.gpkg",)),
    # ★ 2026-09-29 (DECISIONS §302 · PLAN W13-8 닫힘). 「streetlight」 단계를 철거했다.
    #   그 단계가 만든 `streetlight_point.geojson` 은 **옛 지도(web/js)의 마커**가
    #   유일한 소비자였고 그 지도는 §218-1 에서 걷혔다. `segments.py:362` 가
    #   「마커 표현은 streetlight.py 가 담당한다」고, `publish_web.py:90` 이
    #   「가로등은 판정(light_count)에만 쓴다」고 적어 둔 그대로다.
    #   구간의 `light_count` 는 `streetlight_5186.gpkg`(ingest 산출)에서 나오므로
    #   **판정에 영향이 없다.** §243 이 이미 publish 의 유령 read 에서 이 파일을 걷었다.
    Step("terrain", "terrain", "공개DEM → Terrain-RGB 타일",
         WEB / "terrain",
         reads=(RAW, P / "segments_5186.gpkg"),
         writes=(WEB / "terrain", P / "dem_scope.tif"),
         # ★ 여기가 z 소실의 자리다. segments.geojson 을 읽어 z 를 덧쓴다.
         # ★ _manifest.json 도 reads 가 아니라 mutates 다. terrain 기록을
         #   덧쓴다. reads 로 적어두면 하류 무효화 경고가 안 뜬다.
         # ★ view.json 은 publish 가 만드는데 여기서 덧쓴다 — 후진 의존이다.
         #   `if vj.exists()` 로 첫 실행을 넘긴다. test_guards.BACKWARD 가 든다.
         # ★ 2026-09-16. `terrain.LAYERS` 의 ingest 산출물 넷에도 z 를 덧쓴다.
         #   선언이 segments 하나뿐이었다 — 모듈이 f"{key}_5186.gpkg" 로 쓰니
         #   리터럴을 훑는 대조가 못 봤다. 샤드 봉인지가 매 실행 찢어져서 알았다
         #   (DECISIONS §165-6). 강제자 test_shardseal::test_terrain_mutations_are_declared
         mutates=(P / "segments.geojson", P / "_manifest.json",
                  WEB / "view.json",
                  P / "segments_5186.gpkg",
                  P / "building.geojson", P / "building_5186.gpkg",
                  P / "cctv.geojson", P / "cctv_5186.gpkg",
                  P / "hydrant_point.geojson", P / "hydrant_point_5186.gpkg",
                  P / "fire_station.geojson", P / "fire_station_5186.gpkg")),
    Step("ortho", "ortho", "항공정사영상 → 배경 타일",
         WEB / "ortho",
         # ★ scope.geojson 은 publish 산출이다. **후진 의존이며 지난 실행의
         #   산출물을 읽는다** — 스코프가 바뀌면 정사영상이 한 실행 늦게
         #   따라온다. test_guards.BACKWARD 와 PLAN 이 든다.
         reads=(RAW, P / "scope_5186.gpkg"),
         writes=(WEB / "ortho",),
         mutates=(WEB / "view.json", P / "_manifest.json")),
    Step("publish", "publish_web", "→ web/data",
         WEB / "segments.geojson",
         # ★ 2026-09-24 (DECISIONS §243). 유령 read 셋을 걷었다 —
         #   `streetlight_point.geojson` · `corridor_5186.gpkg` ·
         #   `ngii1k_light_5186.gpkg`. publish 계열 다섯(web · navi · fleet ·
         #   basemap · context) 어디도 이 셋을 안 연다. 대신 `publish_basemap`
         #   이 실제로 여는 셋이 빠져 있었다. **단계 선언이 곧 영향 분석의
         #   근거**인데 그 근거가 양쪽으로 틀려 있었다.
         reads=(P / "segments.geojson", P / "segments.schema.json",
                P / "boundary_emd.geojson",
                P / "fire_station.geojson", P / "hydrant_point.geojson",
                P / "cctv.geojson", P / "poi_store.geojson",
                P / "building_5186.gpkg",
                P / "route_vehicle.csv", P / "scope_5186.gpkg",
                # ★ publish_basemap 의 SOURCES — road_area · sidewalk 의 재료
                P / "ngii1k_5186.gpkg", P / "road_rw_5186.gpkg",
                P / "ngii1k_walk_5186.gpkg",
                P / "navi_build.csv", P / "navi_jibun.csv", P / "civil_office.geojson",
                # ★ 2026-09-22 (§215-1). 내비 그래프의 통행 규칙 — 일방통행 · 회전 금지
                P / "ngii1k_center_5186.gpkg", P / "node_link_5186.gpkg",
                P / "node_point_5186.gpkg", P / "turn_restriction.csv",
                # ★ 2026-09-22 (§216-3). 주변 사정 · 출동 이력 · 주정차 단속(도로 단위)
                P / "speedbump.csv", P / "speed_cam.csv",
                P / "child_zone_std_5186.gpkg", P / "senior_zone_std_5186.gpkg",
                P / "nfa_dispatch_119.csv", P / "nfa_rescue.csv", P / "nfa_fire_incident.csv",
                P / "parking_enforce.csv",
                # ★ 2026-10-06 (§420-4 · §426-2). **선언 밖에 살던 둘.** 이름으로
                #   읽는데 이 표에 0회였다 — 원본이 바뀌어도 안 잡혔다. 바로 위
                #   `parking_enforce.csv` 는 적혀 있었고 **하나만 빠졌다**(§243).
                P / "enforce_cam.csv", ROOT / "web" / "config.js"),
         # ★ web/data/_manifest.json 은 publish 가 마지막에 쓰는 계보다.
         #   종전에는 tools/web_manifest.py 를 사람이 따로 돌려야 했고
         #   아무도 안 돌렸다(2026-08-22 CI 가 처음 잡음).
         writes=(WEB / "segments.geojson", WEB / "segments.schema.json",
                 WEB / "_manifest.json", WEB / "buildings.geojson",
                 WEB / "hydrants.geojson", WEB / "stations.geojson",
                 WEB / "cctv.geojson", WEB / "poi.geojson",
                 WEB / "vehicle_spec.json", WEB / "route_vehicle.json",
                 WEB / "navi_graph.json", WEB / "dest.geojson",
                 WEB / "context.geojson", WEB / "history.geojson",
                 # ★ 2026-09-24. 발행되는데 선언에 없던 셋.
                 #   `fleet.json`(publish_fleet) · `road_area.geojson` ·
                 #   `sidewalk.geojson`(publish_basemap).
                 WEB / "fleet.json", WEB / "road_area.geojson",
                 WEB / "sidewalk.geojson"),
         # ★ view.json 은 terrain·ortho 가 구운 범위를 넣어둔 것을 읽어
         #   보존하고 다시 쓴다. writes 가 아니라 mutates 다.
         mutates=(WEB / "view.json",)),
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

def check_only():
    from firelane import paths as _paths

    print(f"RAW        {RAW}")
    # ★ 마운트가 끊기면 `is_dir()` 이 예외를 던진다(§104).
    if _paths.alive(RAW):
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"           {n}개 파일 · {sz:.2f} GB")
    else:
        print(col("           없다. FIRE_LANE_DATA 설정 또는 normalize_raw 실행", "y"))
    print()
    for s in STEPS:
        name, desc, out = s.name, s.desc, s.out
        ok = out.exists()
        mark = col("OK  ", "g") if ok else col("없음", "y")
        extra = ""
        if ok and out.is_dir():
            extra = f"  ({sum(1 for _ in out.rglob('*') if _.is_file())}개)"
        print(f"  {mark} {name:9s} {desc:28s} {out.relative_to(ROOT)}{extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", choices=[s.name for s in STEPS],
                    help="이 단계부터 끝까지")
    ap.add_argument("--only", nargs="+", choices=[s.name for s in STEPS],
                    help="이 단계만")
    ap.add_argument("--check", action="store_true", help="실행 없이 상태만")
    ap.add_argument("--no-test", action="store_true", help="계약 테스트 생략")
    # ★ PLAN #15. ingest 를 소스별 자식 프로세스로 돌린다. 사유는
    #   `ingest._spawn` 에 있다.
    # ★ 환경변수로 안 한다. `os.environ` 독자는 `paths.py` 하나라는 것이
    #   축이고(`env_check`), 여기서 읽으면 그 축이 는다. 플래그가 맞다 —
    #   누가 켰는지가 명령줄에 남는다.
    # ★ 기본값이 아닌 이유 — 실측 2m45 → 3m59 다. 74초는 자식마다
    #   `geopandas`·`pyproj` 를 다시 import 하는 값이고(import 만 0.85초
    #   × 40종) 코드로는 못 줄인다. 평소 실행은 빠른 쪽이 맞고,
    #   `verify.sh` 처럼 **앞 단계가 이미 메모리를 먹은 맥락**에서만 켠다.
    #   그 맥락이 정확히 `Errno 12` 가 나는 자리다.
    ap.add_argument("--split", action="store_true",
                    help="ingest 를 소스별 자식 프로세스로 (메모리 반납)")
    ap.add_argument("--reset-lineage", action="store_true",
                    help="계보 기록을 지우고 시작한다 (교착 탈출구)")
    a = ap.parse_args()

    # ★ 2026-10-08 (PLAN #122 · DECISIONS §431). **여기가 합성 루트다.**
    #   `fire-lane = firelane.pipeline:main` 이고, 도메인(`seg/vehicle.py`)은
    #   대장을 직접 안 읽는다 — 읽는 것은 인프라의 일이고 주입은 진입점의 일이다.
    #
    #   ★ **`segments.py` 에 넣으면 안 된다.** 이 파일 위쪽이 적어 뒀듯
    #     「판정 지문 = `firelane.segments` import 닫힘」이고, 거기에 `ledger` 가
    #     들어오면 **대장을 고칠 때마다 판정 지문이 더러워진다.** 그 폐포를
    #     21 → 17 로 줄인 결정을 되돌리는 꼴이다.
    #
    #   ★ 없으면 **안 죽는다.** 제원이 없는 것은 `segments` 가 이미 다루는
    #     사실이고(경로만 건너뛴다), 여기서 죽이면 발행까지 못 간다.
    from firelane import ledger as _led
    from firelane.seg import vehicle as _V
    try:
        _V.use(_led.vehicle_spec())
    except _V.SpecMissing:
        pass

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
        print(col(f"★ raw 가 비어 있다: {RAW}", "r"))
        print("  export FIRE_LANE_DATA=<raw 상위 폴더> 또는")
        print("  python -m firelane.normalize_raw <다운로드폴더>")
        if "ingest" in [s.name for s in steps]:
            sys.exit(1)

    # ★ 하류 무효화. --only / --from 으로 일부만 돌리면 그 산출물에
    #   의존하는 뒤쪽 단계의 결과가 낡는다. 2026-08-18 에 `--only publish`
    #   만 돌려 terrain 이 넣던 z 가 빠진 채 커밋됐다.
    skipped = downstream({s.name for s in steps}) if len(steps) < len(STEPS) else []
    if skipped:
        print(col("★ 하류가 낡는다 — 아래 단계도 돌려야 한다", "y"))
        for s in skipped:
            why = [str(r.name) for r in s.consumes
                   if any(r in q.produces for q in steps)]
            print(f"    {s.name:11s} ← {' · '.join(why)}")
        print(col(f"  권장:  --from {min(skipped, key=lambda s: [x.name for x in STEPS].index(s.name)).name}\n", "y"))

    print(f"실행 {len(steps)}단계: {' → '.join(s.name for s in steps)}\n")
    t0 = time.time()
    # ★ 이번 실행에서 성공한 단계. 계보 검사가 "방금 갱신된 입력" 과
    #   "낡은 입력" 을 구분하는 근거다(lineage.verify 의 fresh).
    done: set[str] = set()
    for s in steps:
        name, desc = s.name, s.desc
        print(col(f"── {name}  {desc}", "c"))
        t = time.time()
        # ★ 계보는 파이프라인이 본다. 단계 스크립트는 계보를 모른다.
        #   종전에는 segments.py 안에서 lineage_check 를 불렀고, 그래서
        #   단계마다 손으로 배선해야 했다. --only publish 가 그 구멍으로
        #   빠져나가 z 를 소실시켰다. Step 선언이 이미 reads/writes 를
        #   알고 있으므로 여기서 일괄로 처리한다.
        try:
            lineage.verify(PROCESSED, ROOT, s, expand, STEPS, fresh=done)
        except lineage.LineageError as e:
            print(col(f"\n★ {e}", "r"))
            sys.exit(1)

        # ★ 파일 경로가 아니라 모듈로 부른다(`python -m firelane.ingest`).
        #   종전 `python -m firelane.ingest` 는 cwd 에 의존했고, 무엇보다
        #   사람이 그 명령을 그대로 손으로 칠 수 있었다 — 그러면 대장만
        #   갱신되고 계보 기록은 빠져 다음 실행이 교착했다(HANDOFF §5-5,
        #   08-21 에 세 번). 이제 단계 모듈은 파이프라인이 부르는 대상이지
        #   사람이 치는 명령이 아니다. `-m` 은 그 사실을 표기로 만든다.
        _extra = []
        # ★ 2026-08-23. ingest 는 `.work` 를 남긴다. 매번 지웠더니
        #   `캐시 0` 이 매 실행 떴고, ingest 180초의 대부분이 재압축이었다.
        #   실패하면 ingest 가 스스로 지운다(반쯤 풀린 것이 오염을 만든다).
        if s.module == "ingest":
            _extra.append("--keep-work")
            if a.split:
                _extra.append("--split")
        # ★ 2026-08-31. `FIRE_LANE_STAGE` 로 "파이프라인이 부른 것" 을 표시한다.
        #   단계 모듈이 이 값을 보고 직접 호출 경고를 낸다(guards.warn_direct_call).
        r = subprocess.run([sys.executable, "-m", f"firelane.{s.module}", *_extra],
                           cwd=ROOT,
                           env={**os.environ, "FIRE_LANE_STAGE": s.name})
        if not r.returncode and s.name == "terrain":
            # ★ 2026-09-16. terrain 이 ingest 산출물에 z 를 덧썼으니 샤드 봉인지의
            #   `out` 칸만 새 실물로 고친다. raw · cfg · code 는 ingest 시점 값을 둔다 —
            #   그래야 `--from` 으로 일부만 돌려도 옛 산출물이 거짓 봉인되지 않는다.
            #   안 하면 다음 실행에서 네 샤드가 찢어지고, 다시 빌드되고, 또 덧써진다.
            r = subprocess.run([sys.executable, "-m", "firelane.ingest", "--reseal-out"],
                               cwd=ROOT, env={**os.environ, "FIRE_LANE_STAGE": "terrain"})
        if r.returncode:
            print(col(f"\n★ {name} 실패. 여기서 멈춘다.", "r"))
            # ★ 2026-09-23 (DECISIONS §224-3). **안내를 조건 없이 찍지 않는다.**
            #   종전에는 ingest 가 어떻게 죽었든 `--retry-failed` 를 찍었다.
            #   2026-09-23 에 OOM 으로 죽었는데 그 명령이 "실패한 소스가 없다"
            #   를 내놓았다 — 안내가 거짓이었고 사람이 그 말을 따라 헛돌았다.
            #   이 저장소가 가장 싫어하는 1족이다(MASTER §17).
            # ★ 종료코드로 가른다. 출력을 파싱하면 문구를 다듬는 순간 죽는다.
            if s.module == "ingest" and r.returncode in (INGEST_ENOMEM_RC, 137):
                print(col("  ★ 메모리로 죽었다 — 소스가 실패한 것이 아니다."
                        " `--retry-failed` 는 할 일이 없다고 답한다.", "r"))
                print(col("    wsl --shutdown          (Windows PowerShell) VM 메모리 반납", "c"))
                print(col("    ~/.wslconfig            [wsl2] memory=12GB", "c"))
                print(col("    uv run fire-lane --from ingest --split"
                        "   소스마다 자식 프로세스 (메모리 반납)", "c"))
                print(col("  ★ 봉인이 코드 때문에만 찢어졌고 산출물이 그대로라면"
                        " 다시 빌드할 필요가 없다:", "y"))
                print(col("    uv run python -m firelane.ingest --reseal-code", "c"))
            elif s.module == "ingest":
                # ★ 19종 중 몇 종만 실패했을 것이다. 200초를 다시 태우지 마라.
                print(col("  실패한 소스만:  uv run python -m firelane.ingest "
                        "--retry-failed", "c"))
            # ★ 2026-09-04. 실패하면 하류를 막으려고 옛 산출물을
            #   `.stale_<날짜>` 로 격리한다(ingest.py:613). 그것이 남으면
            #   `data/processed` 에 27MB 씩 쌓이는데 안내가 없어서
            #   사람이 알아채지 못했다 — 2026-09-03 에 jijeok OOM 으로
            #   두 개가 남았고 손으로 지웠다.
            print(col("  격리된 옛 산출물이 남았을 수 있다:", "y"))
            print(col("    uv run python tools/tidy.py          무엇이 남았나", "c"))
            print(col("    uv run python tools/tidy.py --yes    지운다", "c"))
            print(f"  고친 뒤: uv run fire-lane --from {name}")
            sys.exit(1)
        lineage.record(PROCESSED, ROOT, s, expand)
        done.add(s.name)
        print(col(f"   {time.time()-t:.1f}s", "d"))

    if not a.no_test:
        print(col("── 계약 테스트", "c"))
        r = subprocess.run([sys.executable, "-m", "pytest",
                            "tests/test_contract.py", "-q"], cwd=ROOT)
        if r.returncode:
            print(col("\n★ 계약 테스트 실패. 머지하지 말 것.", "r"))
            sys.exit(1)

    bad = verify() + verify_ingest() + verify_schema()
    print(f"\n총 {time.time()-t0:.1f}s")
    if bad:
        print(col("\n★ 계약 위반 — 산출물을 믿지 마라", "r"))
        for b in bad:
            print(f"    {b}")
        print("  원본이 정말 바뀌었으면 expectation.INGEST_EXPECT 를 고치고")
        print("  커밋 메시지에 근거를 남겨라. 그 전에는 판정을 쓰지 않는다.")
        sys.exit(1)
    print("\n지도 확인:  uv run python tools/serve.py")


if __name__ == "__main__":
    main()
