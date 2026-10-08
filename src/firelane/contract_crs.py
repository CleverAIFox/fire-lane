"""
contract_crs.py — **선언 좌표계가 실물과 맞는가.** 두 판정을 나눠 든다.

── 왜 떼어 냈나 (2026-10-08 · DECISIONS §433) ─────────────────
`contract.py` 가 `_datum_shift_only` 하나에 **606** 으로 상한을 넘었다.
예외를 올리는 대신 쪼갰다 — 이 묶음은 「선언 좌표계가 실물과 맞는가」
한 물음이고, `tests/test_crs_gate.py` 가 **이미 그것을 한 묶음으로**
물고 있었다. 시험이 먼저 경계를 알고 있었던 셈이다.

★ 판정이 둘이다. `krgis` 의 첫 원칙이 「추측하지 말고 측정한다」다 —

    ① 선언 ↔ `.prj`      메타데이터끼리. 국내 SHP 는 이것이 없거나 틀리다
    ② 선언 ↔ 좌표 실측    좌표 한 점을 후보 전부로 역변환해 본다

  ②가 ①보다 세다. `.prj` 가 틀렸을 때 ①만 있으면 **틀린 것끼리 맞는다.**
  ①′ 가 2026-10-08 에 생겼다 — `.prj` 가 같은 좌표계에 **datum 변환만 더
  적은** 경우다. 그것을 실패로 내면 옳은 선언이 울고, 통과로 내면 재투영이
  갈려도 조용하다. 답은 **경고 + 잰 수**다.

IN    선언 문자열 · `.prj` 글 · 좌표 한 점
OUT   `(수준, 할 말)` 또는 `None`(일치)
PARAM `EPSG_CONFIDENCE` · `DATUM_SHIFT_TOL_M`
밖    **순수 함수다.** 레이크가 없는 곳에서도 판정 자체를 시험할 수 있어야
      한다 — 합성 `.prj` 와 합성 좌표로 문다. 실물 raw 를 여는 것은
      `prj_in` 하나뿐이고 그것도 경로를 받아서 연다.
      그리고 **어느 쪽이 옳은지는 안 말한다** — 선언과 실물이 다르다는 것까지다.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

#: 계약 판정의 어휘. **정본이 여기 있는 이유는 고리다** —
#: `contract` 가 이 파일을 들이므로 이 파일이 `contract` 를 들이면 순환이다
#: (`tests/test_layering.py::test_순환_의존이_없다` 가 늦은 import 도 센다).
#: 그래서 어휘는 **아래쪽 집**에 둔다. 2026-10-08 (DECISIONS §433).
#: ★ `firelane.ledger` 의 `FAIL`·`WARN` 은 **다른 값**(`"FAIL"`·`"WARN"`)이고
#:   다른 어휘다. 합치지 않는다 — 두 관문이 사람에게 다르게 말한다.
OK, WARN, FAIL = "OK", "경고", "★실패"

# ★ 이 관문은 **선언만 있고 구현이 없었다.** `krgis/crs.py` 는 자기 래퍼 셋을
#   지우면서 그 근거로 「contract.py 가 선언과 실물을 대조하며」 를 들었고,
#   `contract.py` 머리말은 「선언 CRS 와 실물 .prj 대조」 를 적어 두었다.
#   **둘이 서로를 가리키고 실제로 하는 쪽이 없었다**(§284-2).
#
# ★ 두 판정을 나눈다. `krgis` 의 첫 원칙이 「추측하지 말고 측정한다」다 —
#     ① 선언 ↔ `.prj`      메타데이터끼리. 국내 SHP 는 이것이 없거나 틀리다
#     ② 선언 ↔ 좌표 실측    좌표 한 점을 후보 전부로 역변환해 본다
#   ②가 ①보다 세다. `.prj` 가 틀렸을 때 ①만 있으면 틀린 것끼리 맞는다.
#
# ★ **②의 한계를 적어 둔다.** 좌표 실측은 bbox 안에 떨어지는가로 본다.
#   `5181`(중부 y+50만) 과 `5174`(보정중부 Bessel) 는 지상 300m 차이라
#   광주 bbox 안에 나란히 떨어진다 — **좌표만으로는 못 가른다.** 실측으로
#   확인했고 그 쌍이 유일하다. 그래서 ②는 그 경우 경고를 내고 ①에게
#   넘긴다. 둘이 서로의 사각지대를 덮는다.
#
# ★ 순수 함수로 둔다. 레이크가 없는 곳에서도 **판정 자체**는 시험할 수 있어야
#   한다 — 합성 `.prj` 와 합성 좌표로 문다(`tests/test_crs_gate.py`).
#: `.prj` → EPSG 되찾기 문턱. **기본값 70 으로는 안 된다.**
#: ★ 실측 2026-09-28. 실물 `.prj` 는 GDAL 이 쓴 WKT1 이고, 그 글을 다시
#:   읽으면 `to_epsg()` 가 한국 좌표계 전부에서 `None` 을 낸다 —
#:   5186 · 5181 · 5174 · 5179 · 5187 다. 문턱을 25 로 내리면 전부 되찾는다.
#:   이것을 안 쓰면 **옳은 `.prj` 를 틀렸다고 우는 관문**이 되고, 그러면
#:   사람이 관문을 끈다. 우는 관문은 없는 관문보다 나쁘다.
EPSG_CONFIDENCE = 25

#: `.prj` 가 **datum 변환 7변수를 명시**해서 생기는 지상 이동의 상한(m).
#: 이 밑이면 경고, 넘으면 실패다.
#:
#: ★ 실측 2026-10-08 (DECISIONS §433). `vworld_uq153` 의 `.prj` 에서 **0.07m** 다 —
#:   `pyproj` 의 기본 5174 파이프라인이 사실상 같은 7변수를 쓴다. 5186 으로
#:   보낸 좌표도 2cm · 7cm 차이다.
#: ★ 값의 근거는 `seg/params.NODE_TOL`(0.5m · 끝점을 한 노드로 묶는 거리)다.
#:   그보다 작은 이동은 **그래프를 못 움직인다** — 노드가 같은 자리로 묶인다.
#:   넘으면 움직일 수 있고 그때는 사람이 본다.
#: ★ **import 하지 않는다.** `contract` 가 판정 상수에 매이면 그 상수를 고칠 때
#:   관문이 같이 흔들린다. 둘이 같은지는 `tests/test_crs_gate.py` 가 **대조한다** —
#:   같은 수를 두 집에 두되 어긋나면 우는 쪽을 고른다(§232 가 적은 거래).
DATUM_SHIFT_TOL_M = 0.5

#: `.prj` 의 datum 변환 항. WKT1 은 중첩 괄호가 없어 한 겹으로 떨어진다.
_TOWGS84 = re.compile(r",\s*TOWGS84\[[^\]]*\]", re.I)


def prj_verdict(declared: str, prj_text: str) -> tuple[str, str] | None:
    """선언 좌표계 ↔ 실물 `.prj`. (수준, 메시지) 또는 None(일치)."""
    from pyproj import CRS as _CRS
    from pyproj.exceptions import CRSError as _CRSError


    if not declared:
        return None
    if not (prj_text or "").strip():
        return (WARN, "`.prj` 가 없다 — 선언을 믿고 간다. 국내 SHP 의 흔한 꼴이다")
    try:
        want, got = _CRS.from_user_input(declared), _CRS.from_wkt(prj_text)
    except (_CRSError, ValueError) as ex:
        return (WARN, f"`.prj` 를 못 읽었다 — {type(ex).__name__}")
    w_epsg = want.to_epsg(min_confidence=EPSG_CONFIDENCE)
    g_epsg = got.to_epsg(min_confidence=EPSG_CONFIDENCE)
    if w_epsg is not None and w_epsg == g_epsg:
        return None
    if want.equals(got, ignore_axis_order=True):
        return None
    if (hit := _datum_shift_only(declared, prj_text, want)) is not None:
        return hit
    return (FAIL, f"좌표계 선언 {declared} 인데 `.prj` 는 "
                  f"{f'EPSG:{g_epsg}' if g_epsg else got.name} 다")


def _datum_shift_only(declared: str, prj_text: str, want) -> tuple[str, str] | None:
    """**같은 좌표계인데 `.prj` 가 datum 변환만 더 적은 경우인가.** 아니면 None.

    ── 왜 생겼나 (2026-10-08 · DECISIONS §433) ──────────────────
    `vworld_uq153` 의 `.prj` 는 **스스로 `AUTHORITY["EPSG","5174"]` 라고 적고**
    투영 변수가 선언과 **글자까지 같다.** 다른 것은 `TOWGS84` 일곱 수 하나뿐인데
    그 항이 `to_epsg()` 를 모든 신뢰도에서 `None` 으로 만들고 `equals()` 를
    거짓으로 만든다. 그래서 관문이 **옳은 선언을 틀렸다고 울었다.**

    ★ **이름으로 안 민다.** `TOWGS84` 항만 떼고 `EPSG_CONFIDENCE` 로 다시
      되찾아 본다 — 그 문턱은 이미 「GDAL WKT1 에서 한국 좌표계를 되찾는
      값」이라고 선언돼 있고, 막고 있던 것이 바로 이 항이었다.
      ★ 떼고 `equals()` 를 묻는 것으로는 **안 된다** — 실측하면 그래도 거짓이다.
        되찾기(`to_epsg`)가 가르고 비교가 못 가른다.

    ★ 그리고 **잰다.** 7변수는 재투영 결과를 움직일 수 있다 — 안 움직인다고
      말하려면 수가 있어야 한다(`krgis` 의 첫 원칙). 상한 밑이면 경고,
      넘으면 실패다. 경고로 내리는 것은 「틀렸다」가 아니라 「사람이 본다」다.

    밖  **어느 쪽이 옳은지는 안 말한다.** `.prj` 의 7변수가 더 정확한지
        EPSG 의 기본 파이프라인이 더 정확한지는 이 함수가 모른다. 드는 것은
        「둘이 같은 좌표계인가」와 「그 차이가 몇 m 인가」 둘이다.
    """
    from pyproj import CRS as _CRS
    from pyproj import Transformer as _TF
    from pyproj.exceptions import CRSError as _CRSError

    from firelane.krgis.crs import REF_WGS84, offset_between

    bare = _TOWGS84.sub("", prj_text)
    if bare == prj_text:
        return None                      # 7변수가 애초에 없다 — 다른 사유다
    try:
        if _CRS.from_wkt(bare).to_epsg(min_confidence=EPSG_CONFIDENCE) \
                != want.to_epsg(min_confidence=EPSG_CONFIDENCE):
            return None                  # 떼도 다른 좌표계다 — 진짜 어긋남이다
        x, y = _TF.from_crs("EPSG:4326", declared, always_xy=True).transform(*REF_WGS84)
        gap = offset_between(x, y, declared, prj_text)
    except (_CRSError, ValueError, TypeError):
        return None
    if gap > DATUM_SHIFT_TOL_M:
        return (FAIL, f"`.prj` 가 {declared} 에 datum 변환 7변수를 더 적었고 "
                      f"그것이 지상 **{gap:,.2f}m** 를 움직인다 — 상한 "
                      f"{DATUM_SHIFT_TOL_M}m 를 넘는다. 어느 쪽으로 읽을지 사람이 정한다")
    return (WARN, f"`.prj` 가 {declared} 에 datum 변환 7변수를 더 적었다 — "
                  f"같은 좌표계이고 지상 이동은 {gap:,.2f}m 다(상한 "
                  f"{DATUM_SHIFT_TOL_M}m). 재투영 결과는 사실상 같다")


def coord_verdict(declared: str, x: float, y: float) -> tuple[str, str] | None:
    """★ **측정한다.** 좌표 한 점이 선언 좌표계로 광주 안에 떨어지나."""
    from firelane.krgis.crs import offset_between, probe_crs

    if not declared:
        return None
    hits = [r.epsg for r in probe_crs(x, y) if r.inside_target]
    if not hits:
        return (WARN, f"좌표 ({x:,.1f}, {y:,.1f}) 가 어느 후보로도 광주 안에 "
                      f"안 떨어진다 — 대상 지역 밖 데이터일 수 있다")
    if declared in hits:
        # ★ 실측 2026-09-28. 후보가 둘 이상 맞는 경우는 **정확히 하나** —
        #   `5181`(중부 y+50만) 과 `5174`(보정중부 Bessel) 쌍이다. 둘은
        #   지상 300m 차이라 광주 bbox 안에 나란히 떨어진다. 나머지 아홉은
        #   전부 후보 하나만 맞는다. 그래서 이 경고는 **위험한 그 쌍에서만**
        #   울고 잡음이 없다. 좌표로는 여기까지고, 가르는 것은 `.prj` 다.
        if len(hits) > 1:
            return (WARN, f"좌표만으로는 {' · '.join(hits)} 를 못 가른다 "
                          f"(지상 {offset_between(x, y, *hits[:2]):,.0f}m 차이) — "
                          f"`.prj` 가 판정한다. 선언은 {declared}")
        return None
    try:
        gap = offset_between(x, y, declared, hits[0])
    except Exception:
        gap = float("nan")
    return (FAIL, f"좌표계 선언 {declared} 인데 실측은 {' · '.join(hits[:3])} 다 — "
                  f"{gap:,.0f}m 어긋난다")


def prj_in(path: Path, layer: str | None = None) -> str:
    """zip 또는 폴더에서 `.prj` 글을 꺼낸다. 없으면 빈 글."""
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                prjs = [n for n in z.namelist() if n.lower().endswith(".prj")]
                if layer:
                    stem = Path(layer).stem.lower()
                    prjs = [n for n in prjs
                            if Path(n).stem.lower() == stem] or prjs
                return z.read(prjs[0]).decode("utf-8", "replace") if prjs else ""
        except (zipfile.BadZipFile, KeyError, OSError):
            return ""
    sib = path.with_suffix(".prj")
    return sib.read_text(encoding="utf-8", errors="replace") if sib.is_file() else ""
