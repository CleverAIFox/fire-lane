#!/usr/bin/env python3
"""
normalize_raw.py — 다운로드 폴더의 원본을 명명규칙에 맞게 data/raw 로 배치한다.

    python -m firelane.normalize_raw                      # 기본 다운로드 폴더 탐색
    python -m firelane.normalize_raw /mnt/c/Users/Fox/Downloads
    python -m firelane.normalize_raw <폴더> --move        # 복사 대신 이동
    python -m firelane.normalize_raw <폴더> --in-place    # 그 자리에서 이름만 정리
    python -m firelane.normalize_raw <폴더> --dry-run

명명규칙 (MASTER §18-2)
    {기관}_{데이터}_{범위}_{기준일}.{확장자}
    폴더명 = 기관명

기관별 폴더
    juso ngii its sbiz safety gjcity nsdi
★ 예외 한 곳. 폴더명 = 기관명 규칙을 깬다. 코드가 이 경로를 직접 읽으므로 고정이다.
    ngii1k        ngii1k.py 가 폴더를 rglob. ngii/ 로 합치면 연속수치지도까지 집는다
  파일명 접두사는 규칙대로 기관명(ngii_ · gjcity_)을 쓴다.

★ 기준일은 다운로드일이 아니라 데이터 기준일이다.
  원본 파일명이나 메타데이터에서 읽어 쓴다. 알 수 없으면 물어본다.

★ 확장자도 정규화 대상이다.
      .zip   SHP 세트 · 다중 파일 묶음
      .csv   모든 표 (json 으로 와도 여기서 변환한다)
      .tif   래스터 (+ 같은 이름의 .xml 메타데이터)
      .ngi   1:1,000 수치지형도 (+ .nda 속성). NGI 포맷은 변환하지 않는다
  같은 데이터셋이 csv 였다가 json 으로 내려오는 일이 흔하다.
  그때마다 ingest 의 kind 를 바꾸면 파이프라인이 흔들리므로 여기서 맞춘다.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from firelane.paths import RAW

for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 원본 파일명 패턴 → (폴더, 목적지 파일명)
# 정규식은 소문자 변환 후 매칭한다. 괄호는 브라우저가 &#40; 로 바꾸기도 해서 느슨하게 본다.
# FL_HYPHEN_SCOPE
# ★ 2026-08-27. 패스스루 규칙이 `\w+` 를 쓰고 있었는데 `\w` 는 하이픈을
#   포함하지 않는다. 스코프 별칭이 `jngj-dong` 으로 바뀌면서 **규칙이
#   자기가 만든 파일을 못 잡게 됐다.** 재취득하면 landing 에 갇힌다 —
#   2026-08-23 의 `동구_불법 주정차_20250226.csv` 2.9MB 와 같은 사고다.
#
#   `test_every_required_file_is_reachable_by_rules` 가 잡았다.
#   별칭 문법을 바꿀 때 그것을 읽는 곳을 전부 세지 않은 결과다.
RULES: list[tuple[str, str, str]] = [
    # ── 2026-08-17 소방 계열 3종 재확보 ──────────────────────
    #   ★ 아래 세 줄이 위쪽 기존 규칙보다 먼저 매칭돼야 한다.
    #     "소방용수시설.?현황" 이 전남 판 좌표 파일을 summary 로 오분류했었다.
    #
    # 소화전 좌표. 전국 표준데이터 50,000행 절단본이나 광주는 전량 포함
    # (광주 197 · 동구 31 · 데이터기준일자 2024-02-07).
    # 전남 판(jngj_20250917)에는 광주가 0건이라 이것 말고 대안이 없다.
    (r"전국소방용수시설표준데이터\.(csv|json)$",
     "safety", "safety_hydrant_point_kr_20240207.csv"),
    # 소화전 집계표. 좌표는 없고 총량만 있다. 지상418+지하171 = 589.
    # "588 중 31" 공개율 논거의 분모가 이것이다. 소방차진입불가지역 컬럼도 있다.
    (r"동부소방서.*소화전.?현황",
     "safety", "safety_hydrant_summary_gj_dong_20250731.csv"),
    # 소방서·119안전센터 좌표. X좌표=위도 · Y좌표=경도 (뒤바뀐 이름이 원본 그대로다).
    # 접근 회랑과 D-28 시나리오 출발점이 여기서 나온다.
    #   대인119안전센터 35.1545794 126.9147654
    #   지산119안전센터 35.1499634 126.9385315
    # 좌표 없는 "시도 소방서 현황"(20250701)은 규칙을 두지 않는다. landing 에 남긴다.
    (r"전국소방서.?좌표현황",
     "safety", "safety_firestation_kr_20240901.csv"),
    # ── juso · 도로명주소 ────────────────────────────────────
    # 전자지도 zip 하나에 5종이 들어 있다.
    # TL_SPRD_MANAGE(도로구간) TL_SPRD_RW(실폭도로) TL_SCCO_EMD(경계)
    # TL_SPBD_BULD(건물) TL_SPBD_ENTRC(출입구)
    (r"^전남광주통합특별시_동구\.zip$",   "juso", "juso_elctrnmap_jngj_20260711.zip"),
    (r"사물주소도형.*동구\.zip$",         "juso", "juso_spotaddr_geom_jngj_20260801.zip"),
    (r"사물주소기준점.*동구\.zip$",       "juso", "juso_spotaddr_ref_jngj_20260801.zip"),
    (r"^juso_(elctrnmap|spotaddr_\w+)_jngj_\d{8}\.zip$", "juso", None),

    # ── its · 국가교통정보센터 ───────────────────────────────
    # ★ 258MB 전국이다. 광주 절단은 norm 이후 단계에서 한다.
    #   raw 는 원본 보존이 원칙이므로 여기서 자르지 않는다.
    (r"nodelinkdata\.zip$",  "its", "its_nodelink_kr_20260812.zip"),
    # ★ 2026-08-23. 소방장비 기본규격. 차량 제원의 유일한 공식 출처다.
    #   파일명이 소방청 게시판에서 받은 그대로라 규칙으로 정규화한다.
    # ★ 2026-08-24. 이 두 줄이 `KFS` 대문자로 쓰여 있었다. 매칭은
    #   `low = f.name.lower()` 로 하므로 **영원히 안 걸린다.** RULES 40줄
    #   중 대문자를 포함한 정규식이 이 둘뿐이었고, MISSING 도 정확히 이
    #   둘이었다(kfs_pumptruck · kfs_ladder_small). mas 두 종은 규칙이 전부
    #   한글이라 통과했다 — 그래서 같은 날 같은 폴더에 받았는데 한쪽만
    #   raw 에 들어갔다.
    #
    #   3주 동안 안 보인 이유는 `규칙에 없는 파일 N건 (건너뜀)` 이 종료코드
    #   0 이기 때문이다. `tests/test_normalize_rules.py` 가 이제 규칙 전수를
    #   본다 — 대문자 금지 · 대표 파일명 매칭 · 왕복 멱등.
    (r"소방펌프차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_pumptruck_20251224.{0}"),
    (r"소형사다리차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_ladder_small_20251224.{0}"),
    # ★ 2026-08-24. KFS 5종 추가. 소방청 게시판 파일명은
    #   `75. 기본규격 영문화 소방물탱크차(KFS-1-0075-2025-00).hwpx` 처럼
    #   **번호 접두어**가 붙는다. 차종명만 잡으면 그것까지 함께 걸린다.
    #   규칙은 반드시 소문자로 쓴다 — `low = f.name.lower()` 로 매칭한다.
    (r"소방물탱크차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_watertank_20251224.{0}"),
    (r"소방화학차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_chemical_20251224.{0}"),
    (r"소방굴절차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_ladder_articulated_20251224.{0}"),
    (r"구조차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_rescue_20251224.{0}"),
    (r"특수구급차[_ ]?\(?kfs.*\.(hwpx?|pdf)$",
     "safety", "safety_kfs_ambulance_special_20251224.{0}"),
    (r"소방자동차.*다수공급자.*차종별.*\.(hwpx?|pdf)$",
     "safety", "safety_mas_vehicle_spec_20241111.{0}"),
    # ★ 2026-08-24. mas_optional 규칙을 지웠다. 본문 전수 확인 결과
    #   축거·축간거리·회전반경·최소회전반경·전장·전폭·전고가 **전부 0건**
    #   이다. 선택장비 목록이고 차종별 제작규격은 mas_vehicle_spec 이다.
    #   retired 에 사유를 적었으므로 규칙도 같이 내린다 — 대장이 정본이다.

    (r"^내역서\.csv$",       "its", "its_nodelink_changelog_20260812.csv"),
    (r"^its_nodelink_(kr|changelog)_\d{8}\.(zip|csv)$", "its", None),

    # ── ngii · 국토정보플랫폼 ────────────────────────────────
    # ★ (B020)(B060)(B080) 접두는 정규식에 넣지 않는다.
    #   브라우저가 괄호를 인코딩해 내려주는 경우가 있다.
    (r"연속수치지도_(\d{8})(\d{4})\.zip$",      "ngii", "ngii_basemap_gj{1}_{0}.zip"),
    (r"정사영상_(\d{4})_35616(\d{3})\.tif$",    "ngii", "ngii_ortho_gj{1}_{0}1231.tif"),
    (r"정사영상메타데이터_\d+35616(\d{3})\.xml$", "ngii", "ngii_ortho_gj{0}_20251231.xml"),
    (r"공개dem_35616.*\.zip$",                   "ngii", "ngii_dem_gj35616_20251117.zip"),
    (r"^ngii_(basemap|ortho|dem)_gj[\w-]+_\d{8}\.(zip|tif|xml)$", "ngii", None),

    # ── vworld · 브이월드 ────────────────────────────────────
    # ★ ngii 와 폴더를 나눈다. 같은 수치지형도라도 원천이 다르면 폴더가 다르다.
    #   섞으면 어느 판인지 파일명만으로 구분되지 않는다. (2026-08-17)
    # ★ 도엽 zip 74개가 상위 zip 안에 중첩돼 있다. 이중 해제는 ingest 담당.
    (r"^2map1000_shp_광주_동구\.zip$", "vworld", "vworld_map1k_gjdonggu_20260307.zip"),
    (r"^vworld_map1k_gjdonggu_\d{8}\.zip$", "vworld", None),
    # ★ 2026-08-18. 같은 브이월드 동구 상품의 NGI 포맷판을 함께 받는다.
    #   SHP 판(74도엽)은 1:5,000 부모 3561609 대(동명동 북부 12도엽)를 통째로
    #   흘린다. 행정구역 수출이 1:50,000 경계에 걸친 도엽을 빠뜨리는 것으로
    #   보인다 — 북·남·서구 상품도 그 띠를 비껴가 세 묶음 합쳐 교차 0장이었다.
    #   스코프 1,091구간 중 755개(69%)의 중점이 SHP 판 폴리곤 밖이었고,
    #   그래서 폭 채택이 silpok 폴백으로 몰렸다(ngii1k 885 → 319).
    #   NGI 판에 356160983~988 · 993~998 이 있어 그 띠를 정확히 메운다.
    #   같은 도엽이 양쪽에 있으면 파서가 SHP 를 우선한다(ngii1k.collect).
    (r"^2map1000_ngi_광주_동구\.zip$", "vworld", "vworld_map1k_ngi_gjdonggu_20260307.zip"),
    (r"^vworld_map1k_ngi_gjdonggu_\d{8}\.zip$", "vworld", None),

    # ── safety · 공공데이터포털(안전) ────────────────────────
    (r"^전남광주통합특별시_cctv_(\d{8})\.csv$",     "safety", "safety_cctv_jngj_{0}.csv"),
    (r"소방통로확보대상.*_(\d{8})\.csv$",           "safety", "safety_fire_access_gj_dong_{0}.csv"),
    # ★ 2026-08-24. 폐기 등재분 두 규칙을 지웠다.
    #   `sources.yaml` 의 `retired` 에 사유까지 적어놓고도 정규화기가
    #   계속 raw 로 끌어왔다 — 대장은 "폐기", 규칙은 "편입" 이었다.
    #
    #       firestation_kr_20250701      좌표 없음. 활성판은 XY 를 갖는다
    #       hydrant_point_jngj_20250917  전남 판. 광주 0건
    #
    #   이 파일의 위쪽 주석은 *"좌표 없는 시도 소방서 현황(20250701)은
    #   규칙을 두지 않는다"* 라고 적고 있었다. 주석과 코드가 반대였다.
    #   `test_rules_do_not_reimport_retired_files` 가 대장과 대조한다.
    (r"^safety_[\w-]+_\d{8}\.csv$", "safety", None),

    # ── gjcity · 공공데이터포털(광주 동구) ───────────────────
    # ★ enforcement 가 safety 에서 여기로 옮겨왔다.
    #   폴더 = 제공기관 원칙. 불법주정차 단속은 광주 동구가 제공한다.
    (r"동구_가로등현황_(\d{8})\.csv$",              "gjcity", "gjcity_streetlight_dongu_{0}.csv"),
    # ★ 2026-08-23. `단속현황` 을 선택으로 바꿨다. 제공기관이 2025-02-26 판부터
    #   그 말을 뺐다 — `동구_불법 주정차_20250226.csv`. 규칙이 안 잡아서
    #   landing 에 2.9MB 가 편입 안 된 채 남아 있었고, 획득 게이트를 만들고
    #   나서야 보였다. 파일명은 제공기관 마음대로 바뀐다는 전제로 써야 한다.
    (r"동구_불법\s*주정차(?:\s*단속현황)?_(\d{8})\.csv$", "gjcity", "gjcity_parking_enforce_dongu_{0}.csv"),
    (r"동구_쓰레기통현황_(\d{8})\.csv$",            "gjcity", "gjcity_bin_trash_dongu_{0}.csv"),
    (r"동구_의류수거함위치_(\d{8})\.csv$",          "gjcity", "gjcity_bin_cloth_dongu_{0}.csv"),
    (r"동구_주차장정보.*(\d{8})\.csv$",             "gjcity", "gjcity_parking_dongu_{0}.csv"),
    (r"^gjcity_[\w-]+_[\w-]+_\d{8}\.csv$", "gjcity", None),

    # ── sbiz · 소상공인시장진흥공단 ──────────────────────────
    # ★ 다운로드 사이트가 괄호를 HTML 엔티티로 준다(&#40; &#41;).
    #   쉘·경로에서 계속 문제를 일으키므로 여기서 흡수한다.
    (r"소상공인시장진흥공단_상가.*(\d{8})\.zip$", "sbiz", "sbiz_store_kr_{0}.zip"),
    (r"^sbiz_store_[\w-]+_\d{8}\.zip$", "sbiz", None),

    # ── eais · 건축HUB ───────────────────────────────────────
    # ★ 원본이 "03. 표제부_20260817013434.csv" 다. 앞의 03 은 서식 번호이고
    #   뒤 14자리는 다운로드 시각이다. 데이터 기준일이 아니므로 앞 8자리만 쓴다.
    (r"표제부_(\d{8})\d{6}\.csv$", "eais", "eais_bldg_ledger_gjdonggu_{0}.csv"),
    (r"^eais_bldg_ledger_[\w-]+_\d{8}\.csv$", "eais", None),
]

# 없으면 파이프라인이 도는 데 지장이 있는 것
#
# ★ 2026-08-26. 종전에는 옛 파일명 15개를 하드코딩했다. 개명 뒤 9건이
#   "★없음 — 재취득할 것" 으로 떴는데 **전부 오탐**이었다. 실물은 있고
#   목록만 낡았다. 잘못된 경보는 진짜 경보를 못 믿게 만든다.
#
#   대장에서 유도한다. 대장의 `file` 이 정본이고, 그것은 개명과 함께 움직인다.
def _required() -> list[str]:
    import yaml

    from firelane.paths import ROOT as _R
    try:
        d = yaml.safe_load((_R / "sources.yaml").read_text(encoding="utf-8")) or {}
    except OSError:
        return []
    out = []
    for e in (d.get("datasets") or {}).values():
        if e.get("kind") in (None, "raw_only"):
            continue                       # 문서·참고자료는 필수가 아니다
        for pat in (e.get("files") or ([e["file"]] if "file" in e else [])):
            pat = str(pat)
            # ★ 글롭은 뺀다. 이 목록은 **규칙이 배치할 수 있는가**를
            #   검사하는 데 쓰이는데(`test_every_required_file_is_
            #   reachable_by_rules`), 글롭은 실물 이름이 아니라 패턴이라
            #   `place()` 에 넣을 수 없다. 도엽 묶음처럼 여러 장인 소스는
            #   글롭이 정상이므로 목록에서 빼는 것이 맞다 —
            #   그 실물들은 acquire 의 세 판정이 따로 본다.
            if any(c in pat for c in "*?["):
                continue
            out.append(pat)
    return sorted(set(out))


# ★ 이름은 그대로 둔다. `test_normalize_rules` 가 이 이름으로 참조하고,
#   MASTER 도 그렇게 적는다. **바뀐 것은 값의 출처이지 계약이 아니다.**
REQUIRED = _required()

# 이번 재확보에서 못 받은 것. 결손이지 폐기가 아니다(MASTER §18-12).
# 지우면 잊는다. 목록에 남겨야 다음에 받을 때 뜬다.
MISSING = [
    "gjcity/gjcity_parking_dongu_*.csv",             # 광주 동구 주차장
    "safety/safety_hydrant_summary_jngj_*.csv",      # 소화전 집계표
]


def assert_rules_are_lowercase() -> list[str]:
    """규칙에 대문자 ASCII 가 들어 있으면 영원히 안 걸린다.

    매칭이 `f.name.lower()` 이므로 규칙도 소문자여야 한다. 이 불변식을
    깬 것이 kfs 2종 누락의 원인이었다. 테스트가 이 함수를 부른다.
    """
    return [pat for pat, _, _ in RULES if re.search(r"[A-Z]", pat)]


def _sha(p: Path, chunk: int = 1 << 20) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _same(a: Path, b: Path) -> bool:
    """내용이 같은가. 크기가 다르면 sha 를 뜨지 않는다(2.4GB 를 매번 훑지 않게).

    ★ 크기 비교만으로 "같다" 를 말하면 안 된다. 그것이 2026-08-23 까지의
      동작이었고, 손상본을 조용히 통과시킨다.
    """
    if a.stat().st_size != b.stat().st_size:
        return False
    return _sha(a) == _sha(b)


def convert(src: Path, dst: Path) -> bool:
    """확장자가 바뀌는 경우 내용을 변환한다. 아니면 False.

    표(csv/json)는 csv 로 통일한다. 공공데이터포털 표준데이터가
    csv 였다가 json 으로 바뀌어 내려오는 일이 흔한데, 그때마다
    ingest 의 kind 를 바꾸면 파이프라인이 흔들린다.
    """
    if src.suffix.lower() == ".json" and dst.suffix.lower() == ".csv":
        import csv as _csv
        import json as _json
        d = _json.loads(src.read_text(encoding="utf-8"))
        rows = d.get("records", d if isinstance(d, list) else [])
        if not rows:
            return False
        with dst.open("w", encoding="utf-8-sig", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return True
    return False


def find_downloads() -> Path | None:
    for c in (Path.home() / "Downloads",
              Path("/mnt/c/Users") ):
        if c.name == "Downloads" and c.is_dir():
            return c
        if c.is_dir():
            for u in c.iterdir():
                d = u / "Downloads"
                if d.is_dir() and any(d.iterdir()):
                    return d
    return None



def _entry_for(rel: str) -> dict | None:
    """이 상대경로가 어느 대장 항목인가. **조회다. 역산이 아니다.**

    ★ 종전에는 대장 `file` 에서 정규식으로 provider_dataset 을 역산했고,
      그 규칙이 `migrate_names` 와 달라 12건이 개명되지 않았다(08-27).
      `firelane.ledger.entry_of` 하나로 합쳤다.
    """
    from firelane.ledger import entry_of
    return entry_of(rel)[1] or None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", help="다운로드 폴더")
    ap.add_argument("--move", action="store_true", help="복사 대신 이동")
    ap.add_argument("--in-place", action="store_true",
                    help="폴더로 옮기지 않고 그 자리에서 이름만 바꾼다(보관용 원본 정리)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    src = Path(a.src).expanduser() if a.src else find_downloads()
    if not src or not src.is_dir():
        print("다운로드 폴더를 찾지 못했다. 경로를 직접 넘길 것")
        return
    print(f"원본  {src}")
    print(f"대상  {RAW}\n")

    # ★ 이미 규칙에 맞는 이름이면 그대로 배치한다.
    #   --in-place 로 한 번 정리한 폴더를 다시 원본으로 쓸 수 있어야 한다.
    # ★ 2026-08-24. 목록이 세 곳에서 달랐다 — MASTER §18-2a 는 8종(nsdi 없음),
    #   여기는 7종(vworld·eais 없음). `vworld`·`eais` 는 명시 규칙이 따로 있어
    #   **우연히** 돌고 있었다. MASTER 를 아홉으로 통일하고 여기를 맞춘다.
    ORG = {"juso", "ngii", "its", "sbiz", "safety", "gjcity",
           "nsdi", "vworld", "eais"}
    # ★ 확장자 화이트리스트에 hwp·pdf·ngi·nda 가 없었다. 그래서 규칙명으로
    #   한 번 정리한 `safety_kfs_pumptruck_20251224.hwp` 를 다시 넣으면
    #   "규칙에 없는 파일" 로 떨어졌다 — 위 주석이 약속한 왕복 멱등이
    #   hwp·pdf 에 대해 거짓이었다.
    EXT = "zip|csv|tif|xml|hwpx?|pdf|ngi|nda|geojson"
    # ★ RULES 는 모듈 전역이다. main() 안에서 append 하면 같은 프로세스에서
    #   두 번 부를 때 규칙이 중복 누적된다. 지역 사본에 붙인다.
    rules = RULES + [(rf"^{org}_[a-z0-9_]+_\d{{8}}\.({EXT})$", org, None)
                     for org in sorted(ORG)]

    files = [f for f in src.iterdir() if f.is_file()]
    done, skip = [], []
    for f in files:
        low = f.name.lower()
        for pat, folder, tmpl in rules:
            m = re.search(pat, low)
            if not m:
                continue
            name = f.name if tmpl is None else (tmpl.format(*m.groups()) if m.groups() else tmpl)
            # ── FL_CANON_POST ────────────────────────────────
            # ★ RULES 의 템플릿은 **옛 이름**을 만든다
            #   (`safety_kfs_pumptruck_{0}.hwpx` — 스코프 토큰이 없다).
            #   `naming.canonical` 이 새 이름을 만든다. 규칙이 두 곳에 있으면
            #   **무한 왕복**이 난다 — acquire 가 옛 이름으로 넣고,
            #   migrate_names 가 새 이름으로 고치고, 다음 acquire 가 되돌린다.
            #   2026-08-26 에 실제로 12건이 그렇게 되돌아갔다.
            #
            #   RULES 는 "어느 소스인가" 만 정하고 **파일명은 canonical 이
            #   정한다.** 정본은 하나다.
            from firelane import naming as _nm
            _rel = f"{folder}/{name}"
            _ent = _entry_for(_rel)
            _canon = _nm.canonical(_rel, _ent) if _ent is not None else None
            if _canon:
                folder, name = _canon.split("/", 1)
            dst = (src / name) if a.in_place else (RAW / folder / name)
            # ★ 2026-08-23. 여기가 **크기만** 보고 있었다.
            #     if dst.exists() and dst.stat().st_size == f.stat().st_size:
            #   313MB 정사영상이 전송 중 잘려도, 같은 크기의 다른 판이 와도
            #   "이미 있음" 으로 통과한다. 실증했다 — 같은 크기 · 다른 sha 두
            #   파일을 놓으면 그대로 넘어간다.
            #
            #   §18-8 이 백업에 대해 적은 것과 같은 병이다:
            #   "문제는 백업이 없어서가 아니라 백업이 깨진 걸 몰랐던 것."
            #   획득 쪽에 그 구멍이 그대로 있었다.
            #
            #   크기가 같을 때만 sha 를 뜬다. 다르면 어차피 다른 파일이고,
            #   같으면 내용까지 봐야 "이미 있다" 를 말할 수 있다.
            if dst == f or (dst.exists() and _same(f, dst)):
                skip.append((f.name, name if a.in_place else f"{folder}/{name}"))
                break
            size = f.stat().st_size      # ★ move 하면 원본이 사라지므로 먼저 잰다
            if not a.dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                if convert(f, dst):
                    f.unlink()               # 변환했으면 원본 포맷은 남기지 않는다
                elif a.in_place or a.move:
                    shutil.move(str(f), str(dst))
                else:
                    # ★ copy2 는 utime, copy 는 chmod 를 복사하는데
                    #   exFAT/9p(WSL 외장) 에서 EPERM 이 난다. copyfile 은 내용만 복사한다.
                    shutil.copyfile(str(f), str(dst))
            done.append((f.name, name if a.in_place else f"{folder}/{name}", size))
            break

    for o, n, sz in done:
        print(f"  {'→' if not a.dry_run else '·'} {n:52s} {sz/1e6:8.1f} MB   ← {o[:38]}")
    if skip:
        print(f"\n  이미 있음 {len(skip)}건")
    unmatched = [f.name for f in files
                 if not any(f.name == o for o, _, _ in done)
                 and not any(f.name == o for o, _ in skip)]
    if unmatched:
        print(f"\n  규칙에 없는 파일 {len(unmatched)}건 (건너뜀)")
        for u in unmatched[:12]:
            print(f"    {u}")

    if a.in_place:
        print("\n제자리 정리 완료. 파일명·확장자가 규칙에 맞다.")
        print(f"작업용 사본을 만들려면:  python -m firelane.normalize_raw {src}")
        return

    print("\n[필수 파일 점검]")
    miss = []
    for r in _required():
        ok = (RAW / r).exists()
        print(f"  {'OK  ' if ok else '★없음'} {r}")
        if not ok:
            miss.append(r)
    if miss:
        print(f"\n  {len(miss)}건 부족. sources.yaml 의 url 로 재취득할 것")
    else:
        print("\n  전부 확보. python -m firelane.ingest 로 진행")

    if RAW.is_dir():
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"\ndata/raw  {n}개 파일 · {sz:.2f} GB")


if __name__ == "__main__":
    main()
