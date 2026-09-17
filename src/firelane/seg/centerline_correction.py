"""사람이 승인한 도로 중심선 위치 보정.

도로명주소 ``road_link``는 그래프의 뼈대지만, 일부 골목은 선이 실제 도로가
아닌 건물 위를 지난다. 이 모듈은 그런 오정합을 가까운 선으로 자동 치환하지
않는다. 원본 행과 NGII 1:1,000 중심선 조각을 지문으로 고정해 둔 승인 건만
메모리에서 바꾼다. 원본이나 후보가 달라지면 조용히 추측하지 않고 실패한다.

폭은 여기서 복사하지 않는다. 보정된 위치에서 기존 폭 엔진과 판정 규칙을
다시 실행해야 한다.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import linemerge, substring, unary_union

CRS_EPSG = 5186


@dataclass(frozen=True)
class RoadKey:
    sig_cd: str
    rds_man_no: int
    rn_cd: str
    road_name: str


@dataclass(frozen=True)
class BranchTrim:
    road: RoadKey
    source_geometry_sha256: str
    expected_trim_m: float


@dataclass(frozen=True)
class CorrectionSpec:
    correction_id: str
    target: RoadKey
    source_geometry_sha256: str
    centerline_ids: tuple[str, ...]
    branches: tuple[BranchTrim, ...]
    anchor: RoadKey
    expected_length_m: float
    max_start_shift_m: float
    max_end_shift_m: float


@dataclass(frozen=True)
class CorrectionReport:
    correction_id: str
    target_rds_man_no: int
    source_length_m: float
    corrected_length_m: float
    trimmed_branches_m: tuple[tuple[int, float], ...]


PILMUN_289 = CorrectionSpec(
    correction_id="pilmun-daero-289-rds-1109",
    target=RoadKey("12210", 1109, "4277263", "필문대로289번길"),
    # ★ 2026-09-16 재승인(§170-2). 지문만 바꾸고 나머지 가드 — 대체선 95.780m · 절단 4.2124266 ·
    #   6.6067651m · 바뀐 행 [1109, 2888, 2889] · 그래프 2877·3470 — 가 원판 승인값과 전부 같았다.
    source_geometry_sha256=(
        "99AD7595B7998201C5DBE6D05C83D81260B2C723231CD4352B17AFB4AE6E3890"
    ),
    # F8B3DA6F96C8(34.922m)는 기존 1109 종점을 지나가는 별도 연장 후보다.
    # 이번 위치 교정에는 기존 양 끝과 대응하는 아래 5조각만 쓴다.
    centerline_ids=(
        "NC-D40C1E1FB60F",
        "NC-4947589FE657",
        "NC-454DFA24F99C",
        "NC-CC8B76146EA6",
        "NC-F8847C0EA4B3",
    ),
    branches=(
        BranchTrim(
            RoadKey("12210", 2888, "4277263", "필문대로289번길"),
            "5398294E9AB3572698CF6EA4B2272445521A25DFF053249D82A4469821E7BC1B",
            4.2124266,
        ),
        BranchTrim(
            RoadKey("12210", 2889, "4277263", "필문대로289번길"),
            "464B35970F7288D9C76929D442E0A2702AFD54413A858250E29D0807EA76112A",
            6.6067651,
        ),
    ),
    anchor=RoadKey("12210", 303, "4277263", "필문대로289번길"),
    expected_length_m=95.780,
    max_start_shift_m=0.5,
    max_end_shift_m=6.0,
)

APPROVED_CORRECTIONS = (PILMUN_289,)


def _as_text(value: object) -> str:
    return "" if value is None or bool(pd.isna(value)) else str(value)


# ★ 2026-09-16. 지문을 mm 격자에서 뜬다(fire-lane DECISIONS §170-2). 원판은 WKB 를 그대로
#   해시했다. road_link 는 5179 → 5186 재투영을 거치는데, 라이브러리 판 · 원본 sha 가 같아도
#   기계가 다르면 좌표 말단 비트가 갈려 승인 지문 셋이 전부 불일치했다 — 길이는 mm 까지,
#   승인 중심선 5조각은 비트까지 같았다. 비트 지문은 **한 기계에서만 재현되는** 지문이다.
#   1mm 격자는 승인한 위치를 여전히 고정하고(1mm 넘게 옮기면 다른 지문) 말단 비트에만 무디다.
GRID_M = 0.001


def geometry_sha256(geometry) -> str:
    """좌표 순서와 무관한 선형 지문. 1mm 격자로 반올림한 뒤 뜬다."""
    return hashlib.sha256(shapely.set_precision(geometry, GRID_M).normalize().wkb).hexdigest().upper()


def centerline_fingerprint(row: pd.Series) -> str:
    """검수·보정이 함께 쓰는 NGII 중심선 전체 지문.

    ★ 2026-09-16. 여기는 격자를 안 건다. ngii1k_center 는 원본이 5186 이라 재투영이 없고
      두 기계에서 비트까지 일치했다(§170-2). 격자를 걸면 승인 ID(`NC-…`) 다섯이 전부 바뀐다 —
      재승인할 근거 없이 ID 를 옮기지 않는다. 원본 좌표계가 바뀌면 이 함수도 격자로 옮긴다.
    """
    attributes = "|".join(
        _as_text(row.get(name))
        for name in ("도로명", "도로폭", "차로수", "포장재질", "일방통행")
    )
    payload = row.geometry.normalize().wkb + attributes.encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def centerline_id(row: pd.Series) -> str:
    """검수 화면과 보정 레지스트리가 공유하는 NGII 중심선 안정 ID."""
    return "NC-" + centerline_fingerprint(row)[:12]


def _require_metric_crs(frame, label: str) -> None:
    crs = getattr(frame, "crs", None)
    if crs is None or crs.to_epsg() != CRS_EPSG:
        raise ValueError(f"{label} CRS는 EPSG:{CRS_EPSG}이어야 합니다: {crs}")


def _one_road(frame, key: RoadKey):
    required = {"SIG_CD", "RDS_MAN_NO", "RN_CD", "RN", "geometry"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"road_link 필드가 없습니다: {', '.join(missing)}")
    rds = pd.to_numeric(frame["RDS_MAN_NO"], errors="coerce")
    mask = (
        frame["SIG_CD"].astype(str).eq(key.sig_cd)
        & rds.eq(key.rds_man_no)
        & frame["RN_CD"].astype(str).eq(key.rn_cd)
        & frame["RN"].astype(str).eq(key.road_name)
    )
    found = list(frame.index[mask])
    if len(found) != 1:
        raise ValueError(
            f"road_link 대상이 1행이 아닙니다: RDS_MAN_NO={key.rds_man_no}, {len(found)}행"
        )
    return found[0]


def _candidate_rows(centers, ids: tuple[str, ...]) -> list[pd.Series]:
    required = {"도로명", "도로폭", "geometry"}
    missing = sorted(required - set(centers.columns))
    if missing:
        raise ValueError(f"NGII 중심선 필드가 없습니다: {', '.join(missing)}")
    wanted = set(ids)
    found: dict[str, list[pd.Series]] = {key: [] for key in ids}
    for _, row in centers.iterrows():
        key = centerline_id(row)
        if key in wanted:
            found[key].append(row)
    bad = {key: len(rows) for key, rows in found.items() if len(rows) != 1}
    if bad:
        detail = ", ".join(f"{key}={count}행" for key, count in bad.items())
        raise ValueError(f"승인한 NGII 중심선 후보가 달라졌습니다: {detail}")
    return [found[key][0] for key in ids]


def _replacement_line(rows: list[pd.Series], source: LineString, spec: CorrectionSpec):
    merged = linemerge(unary_union([row.geometry for row in rows]))
    if not isinstance(merged, LineString):
        raise ValueError(
            f"{spec.correction_id}: 승인 중심선 {len(rows)}조각이 한 선으로 연결되지 않습니다."
        )
    if abs(merged.length - spec.expected_length_m) > 0.02:
        raise ValueError(
            f"{spec.correction_id}: 중심선 길이가 바뀌었습니다 "
            f"({merged.length:.3f}m != {spec.expected_length_m:.3f}m)."
        )
    source_start = Point(source.coords[0])
    if Point(merged.coords[-1]).distance(source_start) < Point(merged.coords[0]).distance(
        source_start
    ):
        merged = LineString(list(merged.coords)[::-1])
    start_shift = Point(merged.coords[0]).distance(source_start)
    end_shift = Point(merged.coords[-1]).distance(Point(source.coords[-1]))
    if start_shift > spec.max_start_shift_m or end_shift > spec.max_end_shift_m:
        raise ValueError(
            f"{spec.correction_id}: 승인 범위 밖의 끝점 이동입니다 "
            f"(시작 {start_shift:.3f}m, 끝 {end_shift:.3f}m)."
        )
    return merged


def apply_centerline_correction(road, centers, spec: CorrectionSpec):
    """보정 한 건을 적용하고 새 GeoDataFrame과 감사 기록을 반환한다."""
    _require_metric_crs(road, "road_link")
    _require_metric_crs(centers, "ngii1k_center")
    corrected = road.copy()

    target_idx = _one_road(corrected, spec.target)
    source = corrected.at[target_idx, "geometry"]
    if not isinstance(source, LineString):
        raise ValueError(f"{spec.correction_id}: 대상 road_link가 LineString이 아닙니다.")
    if geometry_sha256(source) != spec.source_geometry_sha256:
        raise ValueError(f"{spec.correction_id}: 대상 road_link 원본 geometry가 달라졌습니다.")

    rows = _candidate_rows(centers, spec.centerline_ids)
    replacement = _replacement_line(rows, source, spec)

    # 기존 시작점은 RDS 303 본선 중간의 T접속이다. 보정 후에도 0.5m 스냅
    # 범위 안이어야 하며, 기존 종점은 다른 도로와 연결되지 않은 끝길이어야 한다.
    anchor_idx = _one_road(corrected, spec.anchor)
    anchor = corrected.at[anchor_idx, "geometry"]
    if anchor.distance(Point(replacement.coords[0])) > spec.max_start_shift_m:
        raise ValueError(f"{spec.correction_id}: 보정선 시작점이 기존 본선에 접속하지 않습니다.")
    old_end = Point(source.coords[-1])
    other = corrected.drop(index=target_idx)
    if any(geometry.distance(old_end) <= spec.max_start_shift_m for geometry in other.geometry):
        raise ValueError(f"{spec.correction_id}: 기존 종점이 끝길이 아니어서 자동 이동할 수 없습니다.")
    new_end = Point(replacement.coords[-1])
    if any(geometry.distance(new_end) <= spec.max_start_shift_m for geometry in other.geometry):
        raise ValueError(f"{spec.correction_id}: 새 종점이 승인하지 않은 도로에 접속합니다.")
    expected_crossings = {
        spec.anchor.rds_man_no,
        *(branch.road.rds_man_no for branch in spec.branches),
    }
    actual_crossings = {
        int(rds)
        for idx, rds, geometry in zip(
            corrected.index,
            pd.to_numeric(corrected["RDS_MAN_NO"], errors="coerce"),
            corrected.geometry,
            strict=True,
        )
        if idx != target_idx and pd.notna(rds) and geometry.intersects(replacement)
    }
    if actual_crossings != expected_crossings:
        raise ValueError(
            f"{spec.correction_id}: 보정선의 교차 도로가 승인 목록과 다릅니다 "
            f"(현재 {sorted(actual_crossings)}, 승인 {sorted(expected_crossings)})."
        )

    trimmed: list[tuple[int, float]] = []
    for branch in spec.branches:
        idx = _one_road(corrected, branch.road)
        geometry = corrected.at[idx, "geometry"]
        if not isinstance(geometry, LineString):
            raise ValueError(f"{spec.correction_id}: RDS {branch.road.rds_man_no}가 LineString이 아닙니다.")
        if geometry_sha256(geometry) != branch.source_geometry_sha256:
            raise ValueError(
                f"{spec.correction_id}: RDS {branch.road.rds_man_no} 원본 geometry가 달라졌습니다."
            )
        if Point(geometry.coords[0]).distance(source) > 0.01:
            raise ValueError(
                f"{spec.correction_id}: RDS {branch.road.rds_man_no}의 기존 접속점이 대상선에 없습니다."
            )
        hit = geometry.intersection(replacement)
        if not isinstance(hit, Point):
            raise ValueError(
                f"{spec.correction_id}: RDS {branch.road.rds_man_no}의 새 교차점이 "
                f"하나의 Point가 아닙니다: {hit.geom_type}"
            )
        cut = geometry.project(hit)
        if abs(cut - branch.expected_trim_m) > 0.02:
            raise ValueError(
                f"{spec.correction_id}: RDS {branch.road.rds_man_no} 절단 길이가 달라졌습니다 "
                f"({cut:.3f}m != {branch.expected_trim_m:.3f}m)."
            )
        remainder = substring(geometry, cut, geometry.length)
        if not isinstance(remainder, LineString) or remainder.length <= 0:
            raise ValueError(f"{spec.correction_id}: RDS {branch.road.rds_man_no} 잔여선이 없습니다.")
        corrected.at[idx, "geometry"] = remainder
        trimmed.append((branch.road.rds_man_no, cut))

    corrected.at[target_idx, "geometry"] = replacement
    return corrected, CorrectionReport(
        correction_id=spec.correction_id,
        target_rds_man_no=spec.target.rds_man_no,
        source_length_m=source.length,
        corrected_length_m=replacement.length,
        trimmed_branches_m=tuple(trimmed),
    )


def apply_approved_centerline_corrections(road, centers):
    """등록된 승인 보정을 순서대로 적용한다."""
    corrected = road
    reports: list[CorrectionReport] = []
    for spec in APPROVED_CORRECTIONS:
        corrected, report = apply_centerline_correction(corrected, centers, spec)
        reports.append(report)
    return corrected, tuple(reports)
