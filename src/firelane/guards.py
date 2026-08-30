#!/usr/bin/env python3
"""
guards.py — 파이프라인 방어 로직 정본.

    python -m firelane.guards lineage      계보 검사만 단독 실행
    python -m firelane.guards coverage     공간 커버리지 검사만 단독 실행

── 왜 이 파일이 생겼나 ─────────────────────────────────────────
이 방어들은 2026-08-18 까지 `tools/stale_guard_20260818.py` 가 ingest.py 와
segments.py 에 **문자열로 주입한 코드 덩어리**였다. 주입된 코드는

    1. 테스트할 수 없다     — segments.py 는 import 만 해도 geopandas 를 끌고 온다
    2. 지워져도 CI 가 모른다 — 누가 그 블록을 날려도 초록불이다
    3. 두 곳에 흩어진다      — 같은 판단이 ingest 와 segments 에 따로 산다

두 번 물린 병(1093 · 1091)을 막는 코드가 정작 회귀 테스트 없이 있었다.
함수로 꺼내 `tests/test_guards.py` 가 직접 호출한다.

── 무엇을 지키나 ───────────────────────────────────────────────
lineage      FAIL 난 단계의 낡은 산출물을 하류가 조용히 먹는 것을 막는다
quarantine   FAIL 시 그 key 의 옛 산출물을 개명해 물리적으로 떼어낸다
             ★ 2026-08-18 이후 이것은 보조다. 개명은 증상 대응이고
               (파일을 옮겨 FileNotFoundError 를 내는 것), 원인 대응은
               `lineage.py` 의 지문 대조다. FAIL 이 아니라 **성공했는데
               내용이 다른** 경우는 개명으로 못 잡는다 — 08-18 의 gpkg
               옛 레이어 잔존이 그것이었다.
coverage     스코프가 폭 소스 폴리곤 밖으로 새는 것을 막는다
             ★ 2026-08-18 V-WORLD 동구 SHP 판이 1:50,000 부모 3561609 대
               12장을 흘려 스코프의 69%(755/1091)가 도로경계 밖이었다.
               건수·컬럼·CRS 검사는 전부 통과했다. 행정구역 단위 취득이
               공간 스코프를 보장하지 않기 때문이다. 손으로 세 번 셌다.
"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# 폭·골격·판정에 실제로 읽히는 핵심 입력.
CRITICAL = ("ngii1k", "road_link", "road_rw", "node_link", "cctv")

# 계보상 통과로 보는 상태. SKIP 은 "이번 실행에서 건드리지 않음"이다.
PASS_STATUS = ("OK", "SKIP")

# segments 가 실제로 여는 파일. key 가 OK 여도 이 중 하나가 옛 실행 것이면
# 판정이 갈린다. 새 입력을 읽기 시작하면 여기에 추가할 것.
#   ★ ngii1k_xsec 는 key 'ngii1k' 의 다섯 산출물 중 하나다. key 층 검사만으로는
#     이것이 낡아도 통과한다 — 그 구멍을 막으려고 파일 층이 있다.
REQUIRED_FILES = (
    "ngii1k_5186.gpkg",
    "ngii1k_xsec_5186.gpkg",
    "road_link_5186.gpkg",
    "road_rw_5186.gpkg",
    "node_link_5186.gpkg",
    "cctv_5186.gpkg",
    "ngii_road_5186.gpkg",
    "building_5186.gpkg",
    "building_entrance_5186.gpkg",
    "boundary_emd_5186.gpkg",
)

# 스코프 구간 중 폭 소스 폴리곤 밖에 있어도 되는 상한.
# 2026-08-18 확정 실행에서 47/1101 = 4.3%. 여유를 두어 10%.
MAX_UNCOVERED = 0.10


class GuardFailure(RuntimeError):
    """방어 위반. 파이프라인은 여기서 멈춘다."""


# ── 1. 계보 ────────────────────────────────────────────────────
def _manifest(processed: Path) -> dict:
    mp = Path(processed) / "_manifest.json"
    if not mp.exists():
        raise GuardFailure("_manifest.json 없음 — ingest 를 먼저 돌려라")
    return json.loads(mp.read_text(encoding="utf-8"))


def manifest_status(processed: Path) -> dict[str, str]:
    """_manifest.json 의 key → status 를 읽는다."""
    return {d.get("key"): d.get("status") for d in _manifest(processed).get("datasets", [])}


def manifest_outputs(processed: Path) -> dict[str, str]:
    """이번 실행이 만든 파일명 → 그것을 만든 key.

    ★ 한 key 가 여러 파일을 낸다. ngii1k 하나가 10개(도로경계·중심선·보도·
      평면교차점·가로등)를 만든다. key 만 보는 검사는 그 10개 중 일부만
      갱신된 상태를 통과시킨다.
    """
    out: dict[str, str] = {}
    for d in _manifest(processed).get("datasets", []):
        if d.get("status") not in PASS_STATUS:
            continue
        for f in d.get("outputs") or []:
            out[f] = d.get("key")
    return out


def lineage_check(processed: Path, critical=CRITICAL, required_files=REQUIRED_FILES) -> None:
    """읽을 입력의 마지막 ingest 가 OK 인지 본다. 아니면 GuardFailure.

    ★ 파일이 존재하는 것과 이번 계보에 속하는 것은 다르다.
      2026-08-17/18 이틀 연속, FAIL 난 ngii1k 의 낡은 gpkg 를 segments 가
      조용히 집어 판정 숫자가 갈렸다. _manifest.json 은 FAIL 을 알고
      있었지만 아무도 읽지 않았다 — 여기서 읽는다.

    검사는 두 층이다.

      1. key 층    핵심 데이터셋의 ingest 가 OK 인가
      2. 파일 층   segments 가 실제로 여는 파일이 **이번 실행의 산출물 목록에
                   있는가**. ★ 2026-08-18 추가.

    파일 층이 왜 필요한가. ngii1k 는 한 번에 10개 파일을 낸다. 그중
    `ngii1k_xsec_5186.gpkg`(평면교차점 4,542건)가 빠져도 key 는 OK 다.
    segments 는 그 파일이 없으면 반경 폴백을 쓴다고 시끄럽게 말하지만,
    **낡은 파일이 남아 있으면 아무 말 없이 그것을 쓴다.** 교차부 제외 형상이
    옛 실행 것으로 바뀌면 폭 표본이 달라지고 판정이 조용히 갈린다.
    key 층만으로는 1093 과 같은 사고가 한 단계 아래에서 그대로 재현된다.
    """
    st = manifest_status(processed)
    bad = [k for k in critical if st.get(k) not in PASS_STATUS]
    if bad:
        detail = ", ".join(f"{k}={st.get(k)}" for k in bad)
        raise GuardFailure(
            f"계보 검사 실패: {detail}\n"
            "  마지막 ingest 가 이 입력들을 만들지 못했다. 디스크에 파일이\n"
            "  있어도 그것은 옛 실행의 잔재다. 낡은 입력으로 판정하지 않는다.\n"
            "  → fire-lane --only ingest 를 먼저 통과시켜라")

    made = manifest_outputs(processed)
    orphan = [f for f in required_files
              if (Path(processed) / f).exists() and f not in made]
    if orphan:
        raise GuardFailure(
            "계보 검사 실패: 이번 실행이 만들지 않은 파일이 남아 있다\n"
            + "".join(f"    {f}\n" for f in orphan)
            + "  디스크에 있지만 마지막 ingest 의 산출물 목록에 없다.\n"
              "  옛 실행의 잔재이며, 읽으면 판정이 조용히 갈린다.\n"
              "  → 지우거나 .stale_ 로 개명한 뒤 ingest 를 다시 통과시켜라")


# ── 2. 낡은 산출물 격리 ────────────────────────────────────────
def quarantine_stale(out: Path, key: str, tag: str | None = None) -> list[str]:
    """key 의 기존 산출물을 <이름>.stale_YYYYMMDD 로 개명한다.

    삭제가 아니라 개명이다 — 진단할 때 옛 파일이 증거가 된다(2026-08-18 실제로).
    하류가 읽으려 하면 FileNotFoundError 로 즉시 죽는다. 조용히 못 집는다.
    """
    out = Path(out)
    tag = tag or datetime.now(UTC).astimezone().date().strftime("%Y%m%d")
    pats = (f"{key}_5186.gpkg", f"{key}.geojson",
            f"{key}_*_5186.gpkg", f"{key}_*.geojson")
    staled: list[str] = []
    for pat in pats:
        for p in sorted(out.glob(pat)):
            dst = p.with_name(p.name + f".stale_{tag}")
            dst.unlink(missing_ok=True)
            p.rename(dst)
            staled.append(p.name)
    return staled


# ── 3. 공간 커버리지 ───────────────────────────────────────────
def uncovered_ratio(lines, polys, buffer_m: float = 1.0) -> tuple[int, int]:
    """폭 소스 폴리곤 밖에 있는 구간 수와 전체 수를 센다.

    lines  구간 지오메트리 시퀀스 (미터 좌표계)
    polys  도로경계 폴리곤 시퀀스 (같은 좌표계)

    ★ 건수·컬럼·CRS 가 전부 맞아도 공간이 안 맞을 수 있다.
      contract.py 의 scope_min 은 "스코프 안에 몇 건 있나"를 보지만,
      그것은 폭 소스가 스코프를 **덮는가**와 다른 질문이다.
    """

    polys = [p for p in polys if p is not None and not p.is_empty]
    lines = [g for g in lines if g is not None and not g.is_empty]
    if not lines:
        return 0, 0
    if not polys:
        return len(lines), len(lines)

    return len(uncovered_indices(lines, polys, buffer_m)), len(lines)


def uncovered_indices(lines, polys, buffer_m: float = 1.0) -> list[int]:
    """폴리곤 밖에 있는 구간의 **인덱스**를 준다.

    ★ 2026-08-18. 종전에는 개수만 셌다. "공간 커버리지 OK · 미커버 3.1%" 가
      매 실행 찍혔고 아무도 어느 구간인지 묻지 않았다. 같은 날 정사영상
      대조로 중심선이 도로를 안 따라가는 구간을 찾았는데, 이 검사가 이미
      그것을 세고 있었다.

      EXPECT.unknown_reason · _manifest.json 의 FAIL · nfa_compare 가 전부
      같은 병이었다 — 측정하고 대조하지 않으면 기록이 아니라 장식이다.
      비율은 게이트고, 목록은 작업 지시다. 둘 다 있어야 한다.
    """
    from shapely.strtree import STRtree

    polys = [p for p in polys if p is not None and not p.is_empty]
    if not polys:
        return list(range(len(lines)))
    tree = STRtree(polys)
    out = []
    for i, g in enumerate(lines):
        if g is None or g.is_empty:
            continue
        probe = g.buffer(buffer_m) if buffer_m else g
        if not any(polys[j].intersects(probe) for j in tree.query(probe)):
            out.append(i)
    return out


def coverage_check(lines, polys, max_uncovered: float = MAX_UNCOVERED,
                   label: str = "폭 소스", buffer_m: float = 1.0) -> float:
    """미커버 비율이 상한을 넘으면 GuardFailure. 넘지 않으면 비율을 반환한다."""
    miss, total = uncovered_ratio(lines, polys, buffer_m)
    if not total:
        raise GuardFailure(f"{label} 커버리지 검사: 구간이 0개다")
    ratio = miss / total
    # ★ 비율만 반환하면 아무도 안 본다. 2026-08-18 에 정사영상 대조로
    #   중심선이 건물을 관통하는 구간을 찾았는데, 이 검사가 이미 그것을
    #   세고 있었다. "OK 미커버 3.1%" 로 통과했을 뿐이다.
    #   측정하고 대조하지 않으면 기록이 아니라 장식이다.
    coverage_check.last_miss = miss
    if ratio > max_uncovered:
        raise GuardFailure(
            f"{label} 커버리지 미달: {miss}/{total} ({ratio:.1%}) 가 폴리곤 밖\n"
            f"  상한 {max_uncovered:.0%}. 취득 범위가 스코프를 덮지 못한다.\n"
            "  ★ 행정구역 단위로 받았다고 공간이 덮이는 것이 아니다.\n"
            "    도엽 목록에 1:50,000 부모가 통째로 빠졌는지 먼저 봐라.")
    return ratio


# ── CLI ────────────────────────────────────────────────────────
def _cli() -> int:
    from firelane.paths import PROCESSED

    cmd = sys.argv[1] if len(sys.argv) > 1 else "lineage"
    try:
        if cmd == "lineage":
            lineage_check(PROCESSED)
            print(f"계보 OK: {' · '.join(CRITICAL)}")
        elif cmd == "coverage":
            import geopandas as gpd
            seg = gpd.read_file(PROCESSED / "segments.geojson").to_crs("EPSG:5186")
            pol = gpd.read_file(PROCESSED / "ngii1k_5186.gpkg")
            L = list(seg.geometry)
            r = coverage_check(L, list(pol.geometry))
            print(f"커버리지 OK: 미커버 {r:.1%}")
            idx = uncovered_indices(L, list(pol.geometry))
            if idx:
                print(f"\n폴리곤 밖 {len(idx)}구간 — 답사·재확인 대상")
                sub = seg.iloc[idx]
                cols = [c for c in ("seg_uid", "road_name", "length_m",
                                    "width_min_m", "width_src", "verdict")
                        if c in sub.columns]
                print(sub[cols].sort_values("length_m", ascending=False)
                      .to_string(index=False))
        else:
            print(f"모르는 명령: {cmd}  (lineage | coverage)")
            return 2
    except GuardFailure as e:
        print(f"★ {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
