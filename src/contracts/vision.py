"""
vision.py — 영상판정 인터페이스. MASTER §19 의 실행 가능한 사본.

── 경계 ────────────────────────────────────────────────────────
    GIS ──[관측점 선정]──▶ 비전     어느 골목의 어느 지점을 찍을지
    GIS ◀──[판정 결과]──── 비전     seg_uid + 통행폭 + 시각

**반대 방향이 없다는 것이 핵심이다**(PLAN §2-1). 비전은 **최소 통행폭
하나**만 넘긴다. 판정(`verdict`)은 넘기지 않는다 — 판정까지 넘어오면
임계값 3.0m 가 두 군데에 박히고, 실측 후 한쪽만 바뀌면 화면과 데이터가
어긋난다.

★ GIS 는 도로폭을 주지 않는다(§19-2). GIS 폭을 먼저 알고 재면 그 값
  근처로 수렴하고, 그러면 영상이 GIS 를 검증하는 의미가 사라진다.
  GIS 폭 자체가 미검증(`width_verified: false`) 이라 물려주면 틀린 값이
  재생산된다. 방향(`bearing_deg`)은 폭이 아니므로 순환하지 않는다.

── ★ 계약은 두 층이다 ──────────────────────────────────────────
    하드 강제   CV 가 무엇을 만들든 안 바뀌는 것. 4개뿐이다
    합의 대기   CV MVP 가 나온 뒤 정한다. 강제하지 않는다

**강제 범위가 넓으면 CV 파트가 계약을 우회하기 시작하고, 그러면 계약
계층 전체가 무력해진다.** 좁게 잡아서 강도를 유지한다.

    하드 4개    seg_uid 형식 · 시간대 필수 · hard >= soft · 판정/임계값 금지
    합의 대기    마스킹 정책 · confidence 산출 · n_frames · 추가 필드

`extra="allow"` 다. CV 가 필드를 붙여가며 실험할 수 있어야 한다.
확정되면 `params_ver` 를 올리고 여기에 등재한다.

IN    없음
OUT   없음 (형)
PARAM PARAMS_VER · SEG_UID_RE · 값 범위 상수
"""
from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ── 상수 ───────────────────────────────────────────────────────
# seg_uid 는 GIS 가 관측점 등록 때 발급한다(segkey.py). seg_id 를 쓰지
# 않는 이유는 파이프라인을 돌릴 때마다 번호가 밀리기 때문이다(§5-2).
PARAMS_VER = "v0"
"""★ v0 은 초안이다. CV MVP 가 나오면 v1 로 올리고 합의 대기 항목을 등재한다.
합의 대기 목록의 정본은 PLAN 이다 — 여기에 적으면 두 곳이 된다(R14)."""

SEG_UID_RE = re.compile(r"^DM-\d{6}-\d{6}-[A-Z0-9]{4}$")
OBS_ID_RE = re.compile(r"^OBS-\d{3,}$")

# 물리적으로 가능한 범위. 판정 임계값이 아니다 — 임계값 정본은
# seg/params.py 이며 여기에 복사하지 않는다(R3).
WIDTH_MAX_M = 60.0          # 교차로 누출 상한. 이보다 크면 계산 오류다
H_RMS_PX_MAX = 20.0         # 이보다 크면 호모그래피를 신뢰할 수 없다


class ObsSpec(BaseModel):
    """GIS → 비전. `GET /obs/{obs_id}` 응답(§19-2).

    ★ 도로폭 필드가 없는 것이 의도다. 추가하지 마라.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    obs_id: str
    seg_uid: str
    bearing_deg: Annotated[float, Field(ge=0.0, lt=360.0)]
    length_m: Annotated[float, Field(gt=0.0)]
    ref_points: list[dict] = Field(default_factory=list)

    @field_validator("seg_uid")
    @classmethod
    def _seg_uid_form(cls, v: str) -> str:
        if not SEG_UID_RE.match(v):
            raise ValueError(
                f"seg_uid 형식이 아니다: {v!r}\n"
                "  DM-192942-283921-YM7N 형태여야 한다. seg_id 를 쓰지 마라 —\n"
                "  파이프라인을 돌릴 때마다 번호가 밀린다(MASTER §5-2).")
        return v

    @field_validator("obs_id")
    @classmethod
    def _obs_id_form(cls, v: str) -> str:
        if not OBS_ID_RE.match(v):
            raise ValueError(f"obs_id 형식이 아니다: {v!r} (OBS-001 형태)")
        return v


class VisionResult(BaseModel):
    """비전 → GIS. §19-1 반환 형식.

    ★ 폭이 둘인 근거는 소방청 기준 문구다. "폭 2m 이하 **또는 이동불가
      장애물**로 진입 불가" 라고 쓴다. 이동 가능한 것은 장애물로 치지
      않으므로 두 값을 나눠 받으면 "지금은 막혔지만 치우면 뚫린다"
      판정이 가능해진다.
    """

    model_config = ConfigDict(extra="allow", frozen=True)
    """★ allow 다. CV 가 실험 중인 필드를 붙여 보낼 수 있다.
    확정되면 여기에 등재하고 `params_ver` 를 올린다."""

    # ── 식별 ──
    obs_id: str
    seg_uid: str

    # ── 측정값 ──
    passable_width_m: Annotated[float, Field(ge=0.0, le=WIDTH_MAX_M)]
    """HARD + VEHICLE 기준. 지금 상태로 지나갈 폭."""

    passable_width_hard_m: Annotated[float, Field(ge=0.0, le=WIDTH_MAX_M)]
    """HARD 만 기준. 차를 빼면 나오는 폭."""

    at_offset_m: Annotated[float, Field(ge=0.0)]
    """최솟값이 나온 위치(구간 시점 기준). 실측 갈 때 쓴다."""

    observed_at: str
    """ISO 8601 + 오프셋. 관측 신선도(PLAN §7-3)의 입력이다."""

    n_frames: Annotated[int, Field(ge=1)]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    """★ 산출 방식 미결. h_rms_px 기반 · 인라이어 비율 · 마스크 품질 중
    무엇으로 낼지는 CV MVP 가 나온 뒤 정한다."""

    masked: bool
    """마스킹 완료 여부.

    ★ 이 값으로 **거부하지 않는다.** 마스킹 시점은 법 요건이 아니라
      정책이며 아직 미결이다 — 개인정보보호법이 요구하는 것은 저장
      시점 마스킹이고, 현재 구조는 CV 가 처리한 뒤 S3 에 적재한다.
      PLAN §5-6 의 "엣지에서 마스킹" 은 발표 방어 논리이지 법 요건이
      아니다. 정책을 스키마에 박으면 정책이 바뀔 때 코드가 막는다.
      미결 정본은 PLAN 이다."""

    # ── 오차 보정 단위 식별 (§19-3) ──
    calib_id: str
    """폰 · 렌즈 · 해상도 · 촬영모드가 다르면 다른 오차다. 섞으면 안 된다.
    ★ 사진과 영상은 다른 calib_id 다(§19-6)."""

    h_id: str
    """호모그래피 세션 식별. H 는 세션당 1회 푼다 — 프레임마다 풀면
    RANSAC 이 매번 다른 인라이어를 골라 결과가 진동한다."""

    params_ver: str
    n_ref: Annotated[int, Field(ge=0)]
    """대응점 수. 4쌍이 수학적 최소이고 실무는 6~8쌍 + RANSAC 이다.
    ★ 하한을 강제하지 않는다 — 촬영 방식이 아직 미확정이다."""

    h_rms_px: Annotated[float, Field(ge=0.0, le=H_RMS_PX_MAX)]

    # ── 검증 ──
    @field_validator("seg_uid")
    @classmethod
    def _seg_uid_form(cls, v: str) -> str:
        if not SEG_UID_RE.match(v):
            raise ValueError(f"seg_uid 형식이 아니다: {v!r}")
        return v

    @field_validator("observed_at")
    @classmethod
    def _tz_aware(cls, v: str) -> str:
        """★ 시간대 없는 시각을 받지 않는다.

        관측 신선도가 `now - observed_at` 으로 계산되는데 시간대가 없으면
        9시간 어긋난 값이 조용히 들어간다. 30분 주기 폴링에서 9시간
        오차는 **모든 판정을 낡음으로 만들거나 전부 최신으로 만든다.**
        """
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"ISO 8601 이 아니다: {v!r}") from e
        if dt.tzinfo is None:
            raise ValueError(
                f"시간대가 없다: {v!r}\n"
                "  '2026-08-20T14:03:00+09:00' 처럼 오프셋을 붙인다.\n"
                "  없으면 관측 신선도 계산이 9시간 어긋난다.")
        return v

    @model_validator(mode="after")
    def _hard_is_not_smaller(self) -> VisionResult:
        """★ 차를 뺀 폭이 지금 폭보다 좁을 수 없다.

        뒤집혀 들어오면 "치우면 더 막힌다" 가 되어 판정이 무의미해진다.
        두 값을 계산하는 코드가 갈려 있으므로 여기서 붙잡는다.
        """
        if self.passable_width_hard_m < self.passable_width_m:
            raise ValueError(
                f"passable_width_hard_m({self.passable_width_hard_m}) 가 "
                f"passable_width_m({self.passable_width_m}) 보다 작다.\n"
                "  HARD 는 차량을 제외한 폭이므로 항상 같거나 크다.\n"
                "  두 값이 뒤바뀌지 않았는지 보라.")
        return self

# ── 집계 규칙 (§19-5) ──────────────────────────────────────────
Aggregation = Literal["median"]
"""프레임 집계는 **중앙값**이다.

최솟값의 최솟값을 취하면 한 프레임 튄 것이 결과가 된다. 중앙값은
우연오차를 억제하고 계통오차는 그대로 남긴다 — 계통오차는 3~5회
ArUco 실측으로 빼면 되지만 우연오차는 못 없앤다(§19-3).

★ 횡단선 폭은 "빈 공간의 합" 이 아니라 **"끊기지 않고 이어지는 빈 구간
  중 제일 긴 것"** 이다. 합산하면 결과가 조용히 낙관 방향으로 틀어지고,
  "막혔는데 통과 가능" 은 소방차가 골목에 갇히는 오류다.
"""

