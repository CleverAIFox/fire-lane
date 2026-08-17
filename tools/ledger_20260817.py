#!/usr/bin/env python3
"""
ledger_20260817.py — 대장을 실물에 맞추고 contract 블록을 채운다.

    uv add ruamel.yaml
    uv run python tools/ledger_20260817.py --check
    uv run python tools/ledger_20260817.py --diff
    uv run python tools/ledger_20260817.py

── 원칙 ───────────────────────────────────────────────────────
대장이 정본이라는 말은 **코드가 대장을 따른다**는 뜻이지 대장이 무조건
맞다는 뜻이 아니다. 대장이 실물과 다르면 대장을 실물에 맞춘다.
아래 값은 전부 raw 를 직접 열어 확인한 것이다(2026-08-17).

── 무엇을 고치나 ──────────────────────────────────────────────
encoding          6곳이 utf-8 로 선언돼 있었으나 실물은 전부 cp949 다.
                  ingest 의 CSV 인코딩 폴백에 가려져 안 터졌을 뿐,
                  대장이 실물을 잘못 서술하고 있었다.

ngii_road         layer NF_A_A01000.shp → N3A_A0010000.shp
                  ★ rvwd(도로폭)가 이 레이어에 없다. 도로중심선으로 옮겨갔다.
                    segments 는 폴리곤 기하로만 쓰므로 폭 산출에는 지장이 없다.
ngii_road_center  신규. N3L_A0020000.shp 의 rvwd·onsd 를 교차검증에 쓴다.
                  1:1,000 A0020000 과 같은 축이라 축척 간 대조가 생긴다.

fire_station      20250701 판은 순번·소방본부·소방서·주소·전화·팩스뿐이다.
                  ★ 좌표도 119안전센터도 없다. csv_points 로는 영구 FAIL.
                  20240901 판(1,216행)으로 되돌린다. 접근 회랑과 D-28
                  시나리오 출발점이 여기서 나온다.
                  x_col=Y좌표 / y_col=X좌표 는 오타가 아니다. 원본 컬럼명이
                  실제로 뒤바뀌어 있다(X좌표=위도, Y좌표=경도).

hydrant_point     jngj_20250917 은 시_군 22개가 전부 전남이고 광주가 0건이다.
                  파싱은 되고 스코프에서 전멸해 OK 0건 으로 통과했다.
                  kr_20240207(전국 표준데이터)로 교체. 50,000행 절단본이나
                  광주는 전량 포함(광주 197 · 동구 31).

hydrant_summary   결손 해소. 동부소방서 관내 지역별 소화전 현황.
                  ★ 기존 note 의 "지상식 431 + 지하식 157 = 588" 은 틀렸다.
                    실물은 418 + 171 = 589 다. 발표 논거의 분모가 바뀐다.
                    저수조 32 · 급수탑 1 · 비상소화장치 32 를 더하면
                    소방용수시설 총계는 654 다. "소화전"과 "소방용수시설"을
                    구분해 말할 것.

enforcement       2022-01~2023-10(85,380) + 2024-01~2024-12(56,176).
                  기간이 겹치지 않아 이어 붙는다. 글롭으로 둘 다 잡는다.

parking           제거. 스코프 안 65개 중 노외 64 · 노상 1 로 유효폭과 무관하고
                  (2026-08-11 전수 확인) building_ledger 주차대수가 같은 자리를
                  훨씬 높은 해상도로 대체한다. retired 에도 두지 않는다 —
                  쓰던 것을 교체한 게 아니라 애초에 쓴 적이 없다.

신규 3종          bin_trash · bin_cloth · building_ledger.
                  raw 에는 있는데 대장에 없어 매 스캔 격리 대상으로 떴다.

ortho             .tif 만 잡아 메타데이터 .xml 4건이 격리로 떴다. 패턴 확장.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources.yaml"

# ── 필드 교체 ────────────────────────────────────────────────
SET: dict[str, dict] = {
    "road_link":         {"encoding": "cp949"},
    "road_rw":           {"encoding": "cp949"},
    "cctv":              {"encoding": "cp949"},
    "streetlight":       {"encoding": "cp949"},
    "fire_access":       {"encoding": "cp949"},
    "enforcement": {
        "encoding": "cp949",
        "file": "gjcity/gjcity_parking_enforce_dongu_*.csv",
        "vintage": 2025,
    },
    "ngii_road": {
        "encoding": "cp949",
        "layer": "N3A_A0010000.shp",
        "vintage": 20260812,
    },
    "fire_station": {
        "encoding": "cp949",
        "file": "safety/safety_firestation_kr_20240901.csv",
        "vintage": 20240901,
    },
    "hydrant_point": {
        "encoding": "cp949",
        "file": "safety/safety_hydrant_point_kr_20240207.csv",
        "vintage": 20240207,
    },
    "hydrant_summary": {
        "encoding": "cp949",
        "file": "safety/safety_hydrant_summary_gj_dong_20250731.csv",
        "vintage": 20250731,
        "kind": "csv_table",
    },
    "ortho": {"file": "ngii/ngii_ortho_gj*.*"},
}

# hydrant_summary 는 결손 해소 — 결손 표시 필드를 지운다
UNSET: dict[str, list[str]] = {
    "hydrant_summary": ["status", "missing_since", "missing_why"],
}

DROP = ["parking"]

# ── contract 블록 (전부 물리 확인값) ─────────────────────────
CONTRACT: dict[str, dict] = {
    "hydrant_point": {
        "encoding": "cp949",
        "required_cols": ["시설번호", "시도명", "시군구명", "위도", "경도",
                          "안전센터명", "소재지도로명주소", "상세위치",
                          "보호틀유무", "설치연도", "관할기관명"],
        "rows": 50000, "rows_tolerance": 0.05,
        "scope_min": 1,
    },
    "fire_station": {
        "encoding": "cp949",
        "required_cols": ["소방서 및 안전센터명", "주소", "X좌표", "Y좌표", "유형"],
        "rows": 1216, "rows_tolerance": 0.30,
        "scope_min": 2,
    },
    "hydrant_summary": {
        "encoding": "cp949",
        "required_cols": ["구분", "계", "소방차진입불가지역", "데이터기준일자"],
        "rows": 5, "rows_tolerance": 0.40,
    },
    "cctv": {
        "encoding": "cp949",
        "required_cols": ["위도", "경도"],
        "scope_min": 1,
    },
    "streetlight": {
        "encoding": "cp949",
        "required_cols": ["위도", "경도"],
        "scope_min": 1,
    },
    "enforcement": {
        "encoding": "cp949",
        "required_cols": ["위반일자", "위반시간", "위반장소명", "과태료"],
    },
    "fire_access": {"encoding": "cp949"},
    "ngii_road":  {"encoding": "cp949", "layer_must_exist": True},
    "road_link":  {"encoding": "cp949", "layer_must_exist": True},
    "road_rw":    {"encoding": "cp949", "layer_must_exist": True},
    "node_link":  {"layer_must_exist": True},
    "node_point": {"layer_must_exist": True},
    "boundary_emd":      {"encoding": "cp949", "layer_must_exist": True},
    "building":          {"encoding": "cp949", "layer_must_exist": True},
    "building_entrance": {"encoding": "cp949", "layer_must_exist": True},
}

# ── 신규 데이터셋 ────────────────────────────────────────────
NEW: dict[str, dict] = {
    "ngii_road_center": {
        "what": "연속수치지도 1:5,000 도로중심선 N3L_A0020000. rvwd(도로폭)·onsd(일방통행)",
        "crs_native": 5179, "crs": "EPSG:5179", "vintage": 20260812,
        "kind": "shp_zip_multi",
        "file": "ngii/ngii_basemap_gj9*.zip",
        "layer": "N3L_A0020000.shp",
        "encoding": "cp949",
        "retrieved": "2026-08-17",
        "feeds": "미투입 — 폭 교차검증",
        "note": ("★ 구 NF_A_A01000 의 rvwd 가 여기로 옮겨왔다. 도로경계면에는 없다.\n"
                 "rvwd 1.5~46.0m · 정수 76%. ROAD_BT(정수 90%, 2.0에 30% 몰림)보다 세분화.\n"
                 "1:1,000 A0020000 도로폭과 같은 축이라 축척 간 대조가 가능하다.\n"
                 "폭 산출 자체는 폴리곤 트랜섹트로 하므로 이것은 검증용이다.\n"),
        "contract": {"encoding": "cp949", "layer_must_exist": True},
    },
    "bin_trash": {
        "what": "동구 쓰레기통 현황. 고정 장애물",
        "crs_native": 4326, "crs": "EPSG:4326", "vintage": 20241130,
        "kind": "csv_points",
        "file": "gjcity/gjcity_bin_trash_dongu_20241130.csv",
        "encoding": "cp949",
        "retrieved": "2026-08-17",
        "feeds": "미투입 — 폭 산출 고정 장애물 차감",
        "note": ("주차 차량과 달리 움직이지 않는다. 영상판정 없이 도면 단계에서 뺄 수 있다.\n"
                 "호모그래피 쪽 HARD/VEHICLE/SOFT 분류의 SOFT 에 대응한다.\n"),
        "contract": {"encoding": "cp949"},
    },
    "bin_cloth": {
        "what": "동구 의류수거함 위치. 고정 장애물",
        "crs_native": 4326, "crs": "EPSG:4326", "vintage": 20250214,
        "kind": "csv_points",
        "file": "gjcity/gjcity_bin_cloth_dongu_20250214.csv",
        "encoding": "cp949",
        "retrieved": "2026-08-17",
        "feeds": "미투입 — 폭 산출 고정 장애물 차감",
        "note": "bin_trash 와 같은 성격. 고정물이라 도면 단계 차감 대상이다.\n",
        "contract": {"encoding": "cp949"},
    },
    "building_ledger": {
        "what": "건축물대장 표제부. 높이·주용도·주차대수·사용승인일",
        "crs_native": "none", "crs": "none", "vintage": 20260817,
        "kind": "csv_table",
        "file": "eais/eais_bldg_ledger_gjdonggu_20260817.csv",
        "encoding": "utf-8-sig",
        "retrieved": "2026-08-17",
        "feeds": "미투입 — 3D 높이 · 대피취약 · 회색 프루닝",
        "note": ("★ BOM 이 붙은 utf-8 이다. 다른 CSV 는 전부 cp949 인데 여기만 다르다.\n"
                 "높이(m) 기재율 25%. 나머지는 지상층수로 추정해야 한다.\n"
                 "주용도 숙박 251 · 교육연구 226 → 대피취약 지표.\n"
                 "주차대수는 회색 구간 상습점유 추정의 입력이다.\n"
                 "★ 조인키가 다르다. 여기는 관리건축물대장PK, building 은 BD_MGT_SN.\n"
                 "  지번 또는 공간조인이 필요하다.\n"),
        "contract": {"encoding": "utf-8-sig"},
    },
}


def main() -> int:
    check = "--check" in sys.argv
    diff = "--diff" in sys.argv
    try:
        from ruamel.yaml import YAML
    except ImportError:
        print("! ruamel.yaml 없음 —  uv add ruamel.yaml")
        return 1

    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    doc = y.load(SRC.read_text(encoding="utf-8"))
    ds = doc["datasets"]

    if "ngii_road_center" in ds:
        print("  이미 적용됨 — 건너뜀")
        return 0

    bad = 0
    for k in list(SET) + list(UNSET) + list(CONTRACT) + DROP:
        if k not in ds:
            print(f"! 대장에 없다: {k}")
            bad += 1
    for k in NEW:
        if k in ds:
            print(f"! 이미 있다: {k}")
            bad += 1
    if bad:
        print(f"\n★ {bad}건 불일치. 아무것도 쓰지 않았다.")
        return 1

    for k, kv in SET.items():
        for a, b in kv.items():
            ds[k][a] = b
    for k, keys in UNSET.items():
        for a in keys:
            ds[k].pop(a, None)
    for k, c in CONTRACT.items():
        ds[k]["contract"] = c
    for k in DROP:
        del ds[k]
    for k, v in NEW.items():
        ds[k] = v

    # inventory 쪽에도 parking 이 있으면 같이 지운다
    inv = (doc.get("inventory") or {}).get("datasets")
    if inv and "parking" in inv:
        del inv["parking"]
        print("  inventory.datasets.parking 제거")

    if check:
        print("앵커 전건 일치. --check 이므로 쓰지 않았다.")
        return 0

    import io
    buf = io.StringIO()
    y.dump(doc, buf)
    out = buf.getvalue()

    if diff:
        import difflib
        old = SRC.read_text(encoding="utf-8").splitlines()
        for line in list(difflib.unified_diff(
                old, out.splitlines(), "before", "after", lineterm=""))[:200]:
            print(line)
        return 0

    shutil.copy2(SRC, SRC.with_suffix(".yaml.bak_20260817"))
    SRC.write_text(out, encoding="utf-8")
    print(f"  교체 {len(SET)} · 결손해소 {len(UNSET)} · 계약 {len(CONTRACT)}"
          f" · 제거 {len(DROP)} · 신규 {len(NEW)}")
    print(f"  백업 {SRC.with_suffix('.yaml.bak_20260817').name}")
    print("\n다음: uv run python src/etl/contract.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
