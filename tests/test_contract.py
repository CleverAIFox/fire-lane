"""
test_contract.py — GIS ↔ UI 계약 검증

UI(web/navi — 내비 · 관제 ?view=ops)가 의존해도 되는 것만 여기서 고정한다.
값은 실측 후 바뀐다. 구조는 안 바뀐다. 그 경계가 이 파일이다.

깨지면: GIS 쪽이 UI를 말없이 부순 것이다. 머지하기 전에 UI 담당과 합의할 것.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "data"

VERDICTS = {"clear", "needs_cv", "blocked", "unknown"}
REQUIRED = {
    "seg_uid": str,
    "seg_id": str,
    "width_min_m": (float, int, type(None)),
    "width_max_m": (float, int, type(None)),
    "verdict": str,
    "width_verified": bool,
    "midpoint_fallback": bool,
    "inherited": bool,
    "route_usage": int,
    "length_m": (float, int),
}


@pytest.fixture(scope="module")
def seg():
    return json.loads((WEB / "segments.geojson").read_text(encoding="utf-8"))


def test_files_exist():
    for n in ["segments", "buildings", "hydrants", "stations"]:
        assert (WEB / f"{n}.geojson").exists(), f"web/data/{n}.geojson 없음 → publish_web.py 실행"


def test_crs_is_4326(seg):
    """좌표계는 4326으로 고정. 5186으로 내보내면 지도가 아프리카 앞바다로 간다."""
    for f in seg["features"][:200]:
        for lon, lat in _coords(f["geometry"]):
            assert 126.8 < lon < 127.1, f"경도 이탈 {lon} — CRS가 4326이 아니다"
            assert 35.0 < lat < 35.3, f"위도 이탈 {lat} — CRS가 4326이 아니다"


def test_fields_present_and_typed(seg):
    """UI가 읽는 필드는 이름도 타입도 바뀌지 않는다."""
    for f in seg["features"]:
        p = f["properties"]
        for k, t in REQUIRED.items():
            assert k in p, f"{p.get('seg_id')}: 필드 '{k}' 누락"
            assert isinstance(p[k], t), f"{p.get('seg_id')}: '{k}' 타입 {type(p[k])}"


def test_verdict_vocabulary(seg):
    """판정 문자열은 이 4개뿐이다. 늘리면 UI 색 매핑에 구멍이 난다."""
    got = {f["properties"]["verdict"] for f in seg["features"]}
    assert got <= VERDICTS, f"미정의 verdict: {got - VERDICTS}"


def test_seg_id_unique(seg):
    ids = [f["properties"]["seg_id"] for f in seg["features"]]
    assert len(ids) == len(set(ids)), "seg_id 중복. 불변 키가 깨졌다"


def test_width_band_is_ordered(seg):
    """하한 <= 상한. 뒤집히면 폭 산출 로직이 잘못된 것이다."""
    bad = [p["seg_id"] for f in seg["features"] if (p := f["properties"])
           and p["width_min_m"] is not None and p["width_max_m"] is not None
           and p["width_min_m"] > p["width_max_m"] + 0.01]
    assert not bad, f"width_min > width_max: {bad[:5]}"


def test_schema_matches_data(seg):
    s = json.loads((WEB / "segments.schema.json").read_text(encoding="utf-8"))
    assert s["count"] == len(seg["features"]), "schema.count 와 실제 건수 불일치"
    assert s["crs"] == "EPSG:4326"
    assert set(s["fields"]) >= set(REQUIRED)


def test_buildings_have_height():
    """3D extrusion 재료. h 가 없거나 0이면 건물이 납작해진다."""
    b = json.loads((WEB / "buildings.geojson").read_text(encoding="utf-8"))
    for f in b["features"]:
        assert f["properties"]["h"] >= 3.3, "0층 건물은 1층(3.3m)으로 클리핑되어야 한다"


def _coords(g):
    t, c = g["type"], g["coordinates"]
    if t == "Point":
        yield c
    elif t in ("LineString", "MultiPoint"):
        yield from c
    elif t in ("Polygon", "MultiLineString"):
        for r in c:
            yield from r
    elif t == "MultiPolygon":
        for p in c:
            for r in p:
                yield from r


# ── 웹 정적 검증 ──────────────────────────────────────────────
# ★ 2026-09-22. 옛 GIS 지도(web/index.html · web/js 30모듈 · style.css)를 걷어냈다.
#   관제 화면(web/navi ?view=ops)이 넘겨받았다. 지도 DOM id · 토글 · 마커 팝업 · 툴팁 CSS
#   를 보던 검사 여덟은 대상이 사라져 함께 지웠다. 화면 쪽 계약은 이제 내비의 vitest 가 든다.
#   여기 남는 것은 **파일 이름 계약**뿐이다 — 내비가 읽는 web/data 파일이 실재하는가.

WEBDIR = ROOT / "web"


def navi_reads() -> set[str]:
    """web/navi/src 가 이름으로 읽는 web/data 파일. 주석은 뺀다 — 주석에 이름만 적어도 소비자가 되면 고아를 숨긴다."""
    import re
    out: set[str] = set()
    for p in sorted((WEBDIR / "navi" / "src").rglob("*.ts*")):
        src = re.sub(r"/\*.*?\*/", "", p.read_text(encoding="utf-8"), flags=re.DOTALL)
        src = re.sub(r"^\s*//.*$", "", src, flags=re.MULTILINE)
        out |= set(re.findall(r'"([\w_]+\.(?:geojson|json))"', src))
    return out


def _read(name):
    return (WEBDIR / name).read_text(encoding="utf-8")


def test_navi_data_files_exist():
    """내비가 이름으로 읽는 web/data 파일이 실제로 있어야 한다.

    ★ 옛 지도 시절에는 `web/js/data.js` 의 BASE_KEYS 를 봤다. 소비자가 내비 하나가 됐으므로
      `navi_reads()` 가 근거다. 반대 방향(발행됐는데 아무도 안 읽는가)은
      `test_web_data_has_no_unintended_orphan` 이 본다.
    """
    names = navi_reads()
    assert len(names) >= 5, f"내비가 읽는 파일을 못 찾았다 — 추출기를 의심하라: {sorted(names)}"
    miss = sorted(n for n in names if not (WEBDIR / "data" / n).exists())
    assert not miss, f"내비가 읽는데 web/data 에 없다: {miss}"


# ── ETL 스크립트 계약 ────────────────────────────────────────
# ★ 같은 회귀가 세 번 반복됐다. 스크립트가 paths.py 를 안 쓰고 자체 RAW 를 정의하면
#   FIRE_LANE_RAW 환경변수가 무시되고 원본을 못 찾는다(전부 MISSING).
#   패치를 적용할 때마다 되돌아갔으므로 테스트로 고정한다.

ETL = ROOT / "src" / "firelane"


def test_etl_uses_paths_module():
    """ETL 스크립트는 경로를 자체 정의하지 않고 paths.py 를 써야 한다."""
    import re
    for f in ("ingest.py", "segments.py", "terrain.py", "ortho.py", "publish_web.py"):
        src = (ETL / f).read_text(encoding="utf-8")
        own = re.findall(r'^(?:RAW|OUT|PROCESSED|WEB)[\w,\s]*=\s*ROOT.*$', src, re.M)
        assert not own, f"{f} 가 경로를 자체 정의한다: {own}. paths.py 를 쓸 것"
        assert "from firelane.paths import" in src, f"{f} 가 paths.py 를 import 하지 않는다"


def test_publish_z_is_optional():
    """z 는 terrain.py 산출물이므로 필수 컬럼이면 DEM 없이 파이프라인이 죽는다."""
    src = (ETL / "publish_web.py").read_text(encoding="utf-8")
    assert '"unknown_reason","z","geometry"' not in src, \
        "publish_web.py 가 z 를 필수 컬럼으로 요구한다. 선택 컬럼으로 둘 것"
def test_optional_layers_not_silently_empty(seg):
    """
    조용한 결측 방어.

    2026-08-14: raw 폴더를 gjcity/ 로 옮겼는데 segments.py 가 옛 경로를 읽고 있었다.
    glob 이 빈 리스트를 돌려줬고 `if _lp:` 가 그냥 지나가서
    light_count 가 전부 0 인 채 파이프라인이 "OK" 를 찍었다.
    '있어야 할 데이터가 0건'은 정상이 아니다.
    """
    P = [f["properties"] for f in seg["features"]]
    n = sum(1 for p in P if p.get("light_count"))
    assert n > 0, "light_count 전부 0 — 가로등 CSV 경로 확인 (RAW/gjcity/*streetlight*.csv)"


# ── seg_uid ──────────────────────────────────────────────────
# seg_id 는 실행마다 갈린다(1266→1087 때 전부 밀렸다). 외부(실측 DB·영상판정·
# 향후 DB PK)가 붙을 키는 seg_uid 하나뿐이므로 형식과 유일성을 계약으로 고정한다.
import re

SEG_UID_RE = re.compile(r"^[A-Z]{2}-\d{6}-\d{6}-[0-9A-Z]{4}$")


def test_seg_uid_format(seg):
    """형식이 깨지면 파싱하는 쪽(로그·DB·야장)이 전부 깨진다."""
    for f in seg["features"]:
        u = f["properties"]["seg_uid"]
        assert SEG_UID_RE.match(u), f"seg_uid 형식 위반: {u}"


def test_seg_uid_unique(seg):
    """
    중복은 중점이 1m 안에 겹치고 도로명도 같은 구간이 둘 이상이라는 뜻이다.
    접미사로 회피하면 다음 실행에 접미사 순서가 바뀌어 키가 또 갈린다.
    병합 규칙을 봐야 한다.
    """
    ids = [f["properties"]["seg_uid"] for f in seg["features"]]
    dup = {i for i in ids if ids.count(i) > 1}
    assert not dup, f"seg_uid 중복 {len(dup)}건: {sorted(dup)[:5]}"


def test_seg_uid_retention():
    """
    직전 실행 대비 유지율 90%. 무너지면 실측값이 미아가 된다.
    검증: NODE_TOL/SNAP_TOL 0.5 -> 0.6 에서 99.4% (2026-08-14)
    """
    import csv
    import io
    import subprocess

    # ★ 2026-09-17 (§175). seg_uid_map.csv 는 커밋된 파일이다. 없거나 비면 skip 이 아니라 사고다
    # ★ 2026-09-22 (DECISIONS §218-5). 기준을 **작업 트리가 아니라 커밋본**(`HEAD`)에서 읽는다.
    #   종전에는 작업 트리의 `data/processed/seg_uid_map.csv` 를 읽었는데 —
    #     · 전수 실행에서는 `segments.py` 가 이 시험 **전에** 그 파일을 이번 실행 키로 덮어써
    #       「이번 실행 대 이번 실행」을 쟀다. 항상 100% 라 아무것도 안 봤다.
    #     · 부분 실행(segments 만 · 발행 없이)에서는 새 키 표와 **옛 발행물**을 견줘 거짓 빨강이 났다.
    #   「직전 실행」의 정본은 마지막으로 커밋된 표다. segments.py 는 안 고친다 — 그쪽은
    #   덮어쓰기 전에 자기 유지율을 따로 찍는다(`uid_retention`).
    rel = "data/processed/seg_uid_map.csv"
    r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode == 0, (
        f"`git show HEAD:{rel}` 를 못 읽었다 — 커밋된 비교 기준이 없다.\n"
        f"  {r.stderr.strip()[:300]}\n"
        "  git 밖에서 돌렸거나 그 파일이 커밋에서 빠졌다. skip 하지 않는다 — 기준 없는 유지율은 판정이 아니다.")
    prev = {row["seg_uid"] for row in csv.DictReader(io.StringIO(r.stdout))}
    assert prev, f"HEAD 의 {rel} 가 비었다 — 유지율 기준이 없다"

    # 지금의 산출 — 발행물(web)과 파이프라인 산출(processed) 둘 다 본다. 어느 쪽만 다시 만든
    # 부분 실행이어도 **다시 만든 쪽**이 커밋된 키를 지키는지가 잡힌다.
    for cur_path in (WEB / "segments.geojson", ROOT / "data" / "processed" / "segments.geojson"):
        assert cur_path.exists(), f"{cur_path.relative_to(ROOT)} 가 없다"
        cur = {f["properties"]["seg_uid"]
               for f in json.loads(cur_path.read_text(encoding="utf-8"))["features"]}
        ret = len(prev & cur) / len(prev)
        assert ret >= 0.90, (f"seg_uid 유지율 {ret:.1%} ({cur_path.relative_to(ROOT)} 대 HEAD 의 {rel})"
                             " — 키 규칙 재검토")


def test_verdict_matches_rules_for_every_segment():
    """1,101구간 **각각**이 규칙대로 칠해졌는가.

    ★ 2026-08-22. 지금까지 아무도 이걸 검증한 적이 없다. 계약 테스트는
      개수(159/400/190/352)만 봤고, 개별 구간이 규칙과 맞는지는 안 봤다.
      seg_label 을 만들어놓고 툴팁이 seg_no 를 쓰던 것과 같은 구멍이다.
      개수가 맞아도 안이 뒤바뀌었을 수 있다.

    여기서 재현하는 규칙 — 정본은 seg/geom.py verdict() 와 segments.py 다.

      1. wmax < 3.0                        blocked   담이 소방차보다 좁다
      2. wmax 없음 · wmin < 3.0 ·
         road_bt < 3.0                     blocked   ★ 두 근거 독립 일치
                                                     (2026-08-18 도입.
                                                      대장폭 단독으로는
                                                      실측을 뒤집지 않는다)
      3. wmin >= 7.0 · 정규표본 2개 이상    clear     양쪽 주정차해도 통과
      4. wmin >= 7.0 · 정규표본 1개        needs_cv  DM02825 사고 방어
      5. wmin 있음                         needs_cv
      6. 그 외                             unknown
      7. needs_cv 인데 CCTV 25m 밖         unknown

    ★ 이 테스트가 깨지면 둘 중 하나다. 규칙을 고쳤는데 여기를 안 고쳤거나,
      산출물이 규칙을 안 따르거나. 어느 쪽이든 멈추고 봐야 한다.
    """
    import json

    from firelane.seg.params import PARK, TRUCK

    seg = ROOT / "web" / "data" / "segments.geojson"
    assert seg.exists(), "web/data/segments.geojson 가 없다 — 커밋된 산출물이다. publish 를 돌려라"

    num = lambda v: float(v) if v not in (None, "") else None
    feats = json.loads(seg.read_text(encoding="utf-8"))["features"]

    # ★ 필요한 컬럼이 없으면 이 검사는 조용히 틀린 답을 낸다.
    #   2026-08-22 에 실제로 겪었다 — n_sample 이 없는 옛 산출물로 돌렸더니
    #   "표본 1개 방어" 18구간이 규칙 위반으로 잡혔다. 판정은 멀쩡했고
    #   검사가 못 읽은 것이었다. 없으면 통과가 아니라 실패해야 한다.
    need = {"width_min_m", "width_max_m", "road_bt_m", "n_sample",
            "cv_feasible", "verdict"}
    missing = need - set(feats[0]["properties"])
    assert not missing, (
        f"segments.geojson 에 컬럼이 없다: {sorted(missing)}\n"
        "  publish 화이트리스트(publish_web.py _cols)를 확인하고 다시 발행할 것.\n"
        "  이 컬럼 없이는 판정 검증이 성립하지 않는다.")

    bad = []
    for f in feats:
        x = f["properties"]
        wmin, wmax = num(x.get("width_min_m")), num(x.get("width_max_m"))
        bt = num(x.get("road_bt_m"))
        ns = x.get("n_sample")
        ns = int(ns) if ns not in (None, "") else None

        if wmax is not None and wmax < TRUCK:
            exp = "blocked"
        elif (wmax is None and (wmin is None or wmin < TRUCK)
              and bt is not None and bt < TRUCK):
            exp = "blocked"
        elif wmin is not None and wmin >= TRUCK + 2 * PARK:
            exp = "needs_cv" if (ns is not None and ns <= 1) else "clear"
        elif wmin is not None:
            exp = "needs_cv"
        else:
            exp = "unknown"

        if exp == "needs_cv" and not x.get("cv_feasible"):
            exp = "unknown"

        if exp != x["verdict"]:
            bad.append(f"{x.get('seg_id')} {x.get('road_name')}: "
                       f"산출 {x['verdict']} · 규칙 {exp} "
                       f"(wmin={wmin} wmax={wmax} bt={bt} n={ns})")

    assert not bad, (
        f"판정이 규칙과 어긋난 구간 {len(bad)}개\n  "
        + "\n  ".join(bad[:15]))


def test_unknown_reason_vocabulary_is_declared_in_three_places():
    """`unknown_reason` 어휘가 산출·스키마·화면 셋에서 같아야 한다.

    ★ 2026-08-23. 08-22 에 `no_cctv` 를 넷으로 쪼갰는데 `seg/report.py` 의
      스키마는 `null|width|no_cctv` 라는 옛 어휘를 그대로 적고 있었다(R7 위반).
      `web/config.js` 의 reason 표는 이미 넷을 갖고 있어 **화면은 멀쩡했고
      그래서 아무도 몰랐다.** UI 를 새로 짜는 사람이 스키마를 보고 분기하면
      없는 키로 분기한다.

    `test_schema_matches_data` 는 컬럼 **집합**만 본다. 값 어휘는 안 본다.

    ★ 산출물이 아니라 **코드**를 본다. 스키마 JSON 은 생성물이라 파이프라인을
      다시 돌려야 갱신되는데, 그러면 이 검사가 재실행 시점에 의존한다.
      어휘를 정하는 곳은 `segments.py` 이므로 거기서 읽는다.
    """
    import re
    # ★ 주석을 먼저 걷어낸다. segments.py 는 이 어휘를 주석에서도 잔뜩
    #   설명하므로, 안 걷으면 "설명만 있고 코드에는 없는" 값까지 잡는다.
    seg_src = "\n".join(
        re.sub(r"#.*$", "", ln)
        for ln in (ROOT / "src/firelane/segments.py")
        .read_text(encoding="utf-8").splitlines())
    # ★ `reason = "..."` 만 보면 안 된다. 실제 코드에는 여러 줄 삼항이 있어
    #   (`("no_cctv_narrow" if ... else "no_cctv_thin")`) 그 방식으로는
    #   넷 중 둘을 놓친다. 값 자체를 찾는다.
    emitted = set(re.findall(r'"(no_cctv[a-z_]*|width)"', seg_src))
    assert len(emitted) >= 5, f"segments.py 에서 사유 어휘를 못 찾았다: {emitted}"

    schema_src = (ROOT / "src/firelane/seg/report.py").read_text(encoding="utf-8")
    blk = schema_src[schema_src.index('"unknown_reason"'):][:900]
    miss_s = sorted(r for r in emitted if r not in blk)
    assert not miss_s, (
        f"seg/report.py 스키마가 설명하지 않는 사유: {miss_s}\n"
        "  segments.py 가 내는 값과 스키마 서술을 같이 고칠 것(R7).")

    cfg = _read("config.js")
    reason_blk = cfg[cfg.index("reason: {"):][:900]
    miss_c = sorted(r for r in emitted if r not in reason_blk)
    assert not miss_c, (
        f"web/config.js 의 reason 표에 없는 사유: {miss_c}\n"
        "  툴팁이 빈칸으로 뜬다.")


def test_web_data_has_no_unintended_orphan():
    """발행되는데 아무도 안 읽는 레이어가 있는가.

    ★ `test_navi_data_files_exist`(옛 `test_web_data_files_referenced`)는 **한 방향**만 본다 —
      "선언된 것이 실재하는가". 반대 방향(발행됐는데 소비자가 없는가)은
      아무도 안 봤고, `lightpoles.geojson` 163KB 가 그 상태였다(2026-08-23).

      web/data 는 40MB 상한을 받는 공간이다. 아무도 안 읽는 파일이 쌓이면
      그 상한이 빨리 찬다. 더 나쁜 것은 다음 사람이 그것을 보고 "쓰이나 보다"
      하고 유지하는 것이다 — 08-22 에 `zOf` · `width(f)` · `POPUP` 을 옮기지
      않은 것과 같은 이유다.

    ★ 의도된 미배선은 여기 적는다. **적는 행위가 곧 기록이다** —
      `<!--stale-ok-->` 마커와 같은 방식이다.
    """
    import re

    # 예정 작업이라 데이터를 먼저 발행해 둔 것. 배선하면 여기서 뺀다.
    # ★ 2026-08-23. `lightpoles.geojson` 을 뺐다 — 배선했다(옛 지도 poles.js).
    # ★ 2026-09-22. 옛 지도(web/js)를 걷어내자 그 지도만 읽던 다섯이 소비자를 잃었다.
    #   이번 배치는 **발행을 안 건드린다**(publish_web.py 는 판정 지문 옆이라 따로 한다).
    #   그래서 지우는 대신 여기 적는다 — 적는 행위가 곧 철거 대기 목록이다.
    #   관제 화면이 배선하거나 publish_web.py 가 발행을 멈추면 한 줄씩 뺀다.
    INTENDED: dict[str, str] = {
        # 2026-09-22 — 옛 지도만 읽던 다섯(boundary · mask · mask_soft · lightpoles · streetlights)을
        # 같은 날 발행에서 뺐다(DECISIONS §218-1). 지금 의도된 미배선은 없다.
    }

    # 파이프라인이 **읽는** 것도 소비자다(ortho 가 scope.geojson 을 읽는다).
    # 쓰기(to_file)는 소비가 아니다 — 그것을 소비로 세면 모든 발행물이
    # 자기 자신 덕에 통과한다.
    pysrc = "\n".join(p.read_text(encoding="utf-8")
                      for p in (ROOT / "src/firelane").rglob("*.py"))
    read = set(re.findall(r'read_file\(\s*(?:WEB|W)\s*/\s*"([\w_.]+)"', pysrc))
    read |= set(re.findall(r'(?:WEB|W)\s*/\s*"([\w_.]+)"\s*\)\.read_text', pysrc))

    # ★ 2026-09-17 (DECISIONS §181-7). 내비(web/navi/src · TS)도 소비자다. 이 검사는 지도(web/js)만
    #   보다가 내비만 읽는 `dest.geojson` 을 고아로 불러 파이프라인 계약 단계를 세웠다. 샌드박스
    #   web/data 에는 그 파일이 없어서 초록이었다 — 발행한 기계에서만 울었다.
    # ★ 2026-09-22. 옛 지도를 걷어내 이제 화면 소비자는 내비(관제 포함) 하나다.
    read |= navi_reads()

    published = {p.name for p in (WEB).glob("*.geojson")}
    # ★ 면제가 낡으면 사각지대다. 소비자가 생겼거나 발행이 멈췄으면 줄을 지워라.
    stale = sorted(n for n in INTENDED if n in read or n not in published)
    assert not stale, f"INTENDED 가 낡았다 — 이미 읽히거나 발행되지 않는다: {stale}"
    orphan = sorted(published - read - set(INTENDED))
    assert not orphan, (
        f"발행되는데 아무도 안 읽는 레이어: {orphan}\n"
        "  배선하거나, publish_web.py 에서 발행을 멈추거나,\n"
        "  의도된 미배선이면 이 테스트의 INTENDED 에 근거와 함께 적어라.")


def test_segment_fields_are_internally_consistent(seg):
    """구간 하나 안에서 필드끼리 모순이 없는가.

    ★ `test_verdict_matches_rules_for_every_segment` 는 **판정 규칙**만 본다.
      필드 사이의 관계는 아무도 안 봤다. 아래는 그중 코드를 읽지 않고도
      참이어야 하는 것들이다 — 하나라도 깨지면 산출 로직이 어긋난 것이다.

    ★ 2026-08-23 도입 시점에 1,101구간 전부 통과했다. 즉 이 검사는 지금
      있는 버그를 잡으려고 만든 것이 아니라 **앞으로 생길 것**을 잡는다.
      폭 산출을 손대는 작업(clearance 재검토 · wmax 결손 해소)이 예정돼
      있으므로 그때 여기서 걸린다.
    """
    num = lambda v: None if v in (None, "") else float(v)
    bad = []

    def chk(cond, why, p):
        if not cond:
            bad.append(f"{p.get('seg_label') or p.get('seg_id')}: {why}")

    for f in seg["features"]:
        p = f["properties"]
        wmin, wmax = num(p.get("width_min_m")), num(p.get("width_max_m"))
        cov, ns = num(p.get("width_cov")), p.get("n_sample")
        dist, rl = num(p.get("cctv_dist_m")), num(p.get("run_length_m"))

        # 벽 사이 폭은 도로 폭보다 좁을 수 없다(width.py 가 보정한다)
        if wmin is not None and wmax is not None:
            chk(wmax >= wmin - 1e-9, f"wmax {wmax} < wmin {wmin}", p)
        # 폭과 소스는 같이 있거나 같이 없다
        chk((wmin is None) == (p.get("width_src") in (None, "")),
            f"wmin={wmin} 인데 width_src={p.get('width_src')!r}", p)
        # 커버율은 비율이다
        if cov is not None:
            chk(0.0 <= cov <= 1.0, f"width_cov {cov} 가 0~1 밖", p)
        # 표본이 없으면 폭도 없다
        if ns == 0:
            chk(wmin is None, "n_sample 0 인데 폭이 있다", p)
        # cv_feasible 은 cctv_dist_m 의 함수다(CCTV_RANGE)
        if dist is not None:
            from firelane.seg.params import CCTV_RANGE
            chk(bool(p.get("cv_feasible")) == (dist <= CCTV_RANGE),
                f"cv_feasible={p.get('cv_feasible')} 인데 cctv_dist_m={dist}", p)
        # 회색이면 사유가 있고, 회색이 아니면 사유가 없다
        chk((p["verdict"] == "unknown") == bool(p.get("unknown_reason")),
            f"verdict={p['verdict']} · reason={p.get('unknown_reason')!r}", p)
        # 소방청 지정은 연속 100m 이상과 동치다
        from firelane.seg.params import NFA_RUN_M
        want = rl is not None and rl >= NFA_RUN_M
        chk(bool(p.get("nfa_designated")) == want,
            f"nfa_designated={p.get('nfa_designated')} 인데 run_length={rl}", p)
        # 길이는 양수다 — 08-13 에 길이 0.0m 구간 40개가 clear 로 표출됐다
        chk(num(p["length_m"]) > 0, "length_m 이 0 이하", p)
        # 폐기된 필드는 항상 거짓이다
        chk(p.get("inherited") in (False, "false", None),
            "inherited 가 참이다 — 상속은 08-12 에 폐기했다", p)
        chk(p.get("width_verified") in (False, "false", None),
            "width_verified 가 참이다 — D-25 실측 전이다", p)

    assert not bad, (f"필드 간 모순 {len(bad)}건\n  " + "\n  ".join(bad[:15]))


def test_schema_layers_differ_only_by_declaration():
    """`processed` 와 `web` 스키마의 필드 집합 차이가 **선언과 정확히 같은가.**

    ★ 2026-09-17 (DECISIONS §171-4). `pipeline.verify_schema` 는 계층마다
      *스키마 == 자기 산출물* 만 본다. 두 계층을 서로 대조하는 곳이 없었다
      (PLAN `계층 간 스키마 드리프트`). 그래서 processed 에 필드가 생기고
      publish 가 조용히 떨어뜨려도, web 에만 필드가 생겨도 초록이었다.

      선언은 둘이다 —
        processed → web 에서 뺀 것   web 스키마의 `dropped_from_processed`
        web 에만 있는 것             `seg_no`(publish 가 만든다) · `z`(지형 덧쓰기)
      공유 필드의 서술도 같아야 한다. publish 는 서술을 복사한다.
    """
    P = ROOT / "data" / "processed" / "segments.schema.json"
    assert P.exists(), "data/processed/segments.schema.json 가 없다 — 커밋된 스키마다"
    p = json.loads(P.read_text(encoding="utf-8"))
    w = json.loads((WEB / "segments.schema.json").read_text(encoding="utf-8"))
    pf, wf = set(p["fields"]), set(w["fields"])
    dropped = set(w.get("dropped_from_processed") or [])
    assert pf - wf == dropped, (
        f"processed 전용 필드가 선언과 다르다 — 실제 {sorted(pf - wf)} · "
        f"선언 {sorted(dropped)}")
    web_only = wf - pf
    assert web_only <= {"seg_no", "z"} and "seg_no" in web_only, (
        f"web 전용 필드가 선언 밖이다 — {sorted(web_only)}")
    drift = sorted(k for k in pf & wf
                   if k != "seg_no" and p["fields"][k] != w["fields"][k])
    assert not drift, f"같은 필드의 서술이 계층마다 다르다 — {drift}"
