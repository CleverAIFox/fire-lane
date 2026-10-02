#!/usr/bin/env python3
"""
ledger_schema.py — 실물에서 스키마를 읽어 대장에 적는다.

FL_DATA_MIGRATION — git 밖 실물과 원자적으로 움직인다
  `test_no_source_patching_scripts` 의 예외 마커. 이 도구는 대장(데이터)만
  고치고 소스 코드는 건드리지 않는다. 대장 값은 저장소 밖 raw 실물에서
  나오므로 diff 로 담을 수 없다.

    uv run python tools/ledger_schema.py            계획만
    uv run python tools/ledger_schema.py --apply     대장에 기록
    uv run python tools/ledger_schema.py --check     대장과 실물이 어긋났나
    uv run python tools/ledger_schema.py --apply --missing   schema 가 없는 항목만 기록

── schema 와 contract 는 다르다 ───────────────────────────────
    schema     **실물이 이렇게 생겼다**. 기술(descriptive). 자동 생성
    contract   **이래야 한다**. 규범(normative). 사람이 고른다

대장에 이미 `contract:` 가 20건 있고 거기 `required_cols` · `rows` 가 들어
있다. 그것을 대체하지 않는다. `contract` 는 "이 컬럼이 없으면 파이프라인을
세운다" 는 약속이고, `schema` 는 "지금 실물에 이런 컬럼이 있다" 는 사실이다.

★ 둘을 합치면 안 되는 이유 — 실물이 바뀌었을 때 **약속이 함께 바뀌면
  아무도 못 알아챈다.** 지금 이 저장소에서 제일 비싼 사고가 전부 그
  형태였다(선언과 실물이 어긋난 채 조용히 통과).

  그래서 `--check` 가 존재한다. 실물이 대장과 달라지면 시끄럽게 센다.

── 무엇을 읽나 ────────────────────────────────────────────────
    csv_points · csv_table · csv_table_multi   헤더 · 행수 · 인코딩
    csv_points_in_zip                          zip 안 CSV
    shp_zip · shp_zip_multi · dbf_in_zip       레이어 목록 · 속성 컬럼
    raw_only                                   ★ 읽지 않는다(문서·래스터)

★ 값은 안 읽는다. 컬럼 이름과 개수만 본다. 개인정보가 섞인 소스가 있고
  (`enforcement` 의 위반장소명), 스키마에 표본값을 넣으면 그것이 저장소로
  들어온다.

IN    $FIRE_LANE_DATA/raw · sources.yaml
OUT   sources.yaml (datasets[*].schema)
PARAM 없음
"""
from __future__ import annotations

import argparse
import csv
import fnmatch
import io
import re
import sys
import zipfile
from pathlib import Path

import yaml

from firelane import ledger as _led

ROOT = Path(__file__).resolve().parents[1]
YAML = ROOT / "sources.yaml"

# ★ 2026-09-07. 손목록을 `firelane.kinds` 에서 유도한다.
#   종전 CSV_KINDS 에 `json_points` 가 **없었다.** 그래서 표준데이터 JSON
#   소스는 `--check` 가 실물 변경을 못 잡았다 — 조용히 None 을 냈다.
#   ngii1k·ngii_1k 는 shp_dir 의 옛 이름인데 SHP_KINDS 에만 빠져 있었다.
from firelane.kinds import (
    CSV_KINDS,
    DELIM_KINDS,
    JSON_KINDS,
    SHP_KINDS,
    SINGLE_PICK,
)
from firelane.ledger import yaml_span as _led_yaml_span

MAX_COLS = 60          # 이보다 많으면 접는다. 대장이 읽을 수 없게 된다


def _raw() -> Path:
    from firelane.paths import RAW
    return RAW


def _decode(b: bytes, declared: str | None) -> tuple[str, str]:
    """선언을 먼저 믿되, 안 되면 후보를 순서대로 시도한다.

    ★ `firelane.encoding.detect()` 를 안 쓴다. 그것은 **파일 경로**를 받고
      여기는 zip 안 바이트 조각을 다룬다. 조각은 멀티바이트 경계에서
      잘려 있어 strict 디코드가 실패할 수 있고, 그것은 인코딩이 틀린
      것이 아니다. 판정이 아니라 헤더 한 줄을 읽는 것이 목적이다.
    """
    if declared:
        try:
            return b.decode(declared), declared
        except UnicodeDecodeError:
            pass
    for c in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return b.decode(c), c
        except UnicodeDecodeError:
            continue
    return b.decode("cp949", errors="replace"), "cp949?"


def _csv_header(data: bytes, declared: str | None) -> dict:
    text, used = _decode(data, declared)
    head = text.splitlines()[:2]
    if not head:
        return {"error": "빈 파일"}
    cols = next(csv.reader(io.StringIO(head[0])), [])
    return {"columns": [c.strip().lstrip("\ufeff") for c in cols if c.strip()],
            "encoding_seen": used}


#: 레이어가 **있어야** 하는 갈래. 없으면 읽기가 실패한 것이다.
#: ★ 정본은 `SHP_KINDS` 다 — 여기서 목록을 다시 적지 않는다.
#: 못 믿을 값의 **지금 수.** 내려가는 쪽으로만.
#:
#: ★ **읽는 쪽을 레이크 없이 못 고친다.** 중첩 zip(`ngii1k`)과 도엽 묶음(`jijeok`),
#:   그리고 juso 전자지도 여섯의 `DataSourceError` 는 970MB·1.8GB 실물을 열어야
#:   풀린다. 그래서 이 배치는 **고치지 않고 센다** — 이 저장소가 「취입 계약 경고
#:   51 = 래칫 51」로 쓰는 그 방식이다(§13 빚 목록).
#: ★ 세는 것과 고치는 것은 다른 일이고, **세는 것이 먼저**다. 지금까지는 드리프트
#:   0 으로 **조용히 통과**했다 — 빚이 있다는 사실조차 수로 없었다.
#: ★ 이 수는 `ratchet.py` 가 **줄었을 때만** 고쳐 적는다(§309).
#:
#: ★ 2026-10-01 **정정.** 처음에 8 로 적고 `ratchet_values()` 가 빈 값을 돌렸다 —
#:   「레이크 없으면 이름을 안 낸다」는 판단이었는데, 그러면 **래칫이 선언만 있고
#:   실측이 없는 상태**가 되어 「래칫 정합」이 빨개진다. `deliver.py` 의 시운전이
#:   그것을 보내기 전에 잡았다(§340-4).
#:   그리고 그 판단 자체가 틀렸다 — 세는 대상은 **대장에 적혀 있는 값**이고,
#:   `sources.yaml` 은 저장소 안에 있다. 레이크는 **읽을 때만** 필요하다.
#:   대장만으로 센 실측이 3 이다.
#:
#: ★ 2026-10-02 **3 → 1** (DECISIONS §354). **셋 중 둘은 결함이 아니었다** —
#:   레이크에서 실물을 읽어 확인했고 둘 다 `kind in SINGLE_PICK` 으로 멈췄다.
#:   **느슨해지는 쪽이지만 실측이 근거다.** 남은 1(`ngii1k: layers 비었음`)이
#:   진짜이고 `_nested_layers` 가 그 길을 뚫었다. 사연은 §354 가 든다.
UNREADABLE = 0

RATCHETS = {"UNREADABLE": "down"}


def ledger_nonsense() -> int:
    """**대장에 적혀 있는** 못 믿을 값의 수. (DECISIONS §338 · §340-4)

    ★ 레이크를 안 읽는다. 그래서 어느 기계에서도, 빈 작업나무에서도 같은 수가
      난다 — 래칫은 **언제나 이름을 낼 수 있어야** 한다.

    ★ 이것으로 충분한 이유. 못 믿을 값이 들어오는 길은 둘뿐이다 —
      대장에 적혀 있거나(이 함수가 센다), 읽은 값과 대장이 다르거나
      (드리프트가 운다). 읽은 값만 못 믿을 꼴이고 대장은 멀쩡하면 그것은
      드리프트다. 둘을 합치면 빈 구멍이 없다.
    """
    try:
        d = yaml.safe_load(YAML.read_text(encoding="utf-8")) or {}
    except Exception:
        return 0
    n = 0
    for key, e in (d.get("datasets") or {}).items():
        sch = (e or {}).get("schema") or {}
        if sch:
            n += len(unreadable(key, sch, str((e or {}).get("kind") or "")))
    return n


def ratchet_values() -> dict[str, int]:
    """실측. **대장만 읽는다** — 위 `ledger_nonsense()` 머리말이 그 이유를 적는다."""
    return {"UNREADABLE": ledger_nonsense()}


#: 기계마다 다른 자리. 대장은 **어느 기계에서 읽어도 같아야** 한다.
#: ★ 대장 자신이 그 규칙을 적어 놨다(`sources.yaml` 의 `inventory:` 머리) —
#:   「`raw:` 에 기계 고유 절대경로(`/mnt/ssd/...`)가 박혀 있었다. 기계마다
#:   마운트가 달라 두 대에서 쓰는 순간 무의미해진다」. 그때 `raw:` 문은 막았고
#:   `columns_error:` 라는 **다른 문으로 다시 들어왔다**(§340).
ABS_PATH = re.compile(r"(?:^|[\s'\"(])(?:/mnt/|/home/|/Users/|/vsizip/|[A-Za-z]:\\\\)")


def machine_paths(sch: dict) -> list[str]:
    """스키마 안에 **기계 고유 경로**가 있는가. 어느 칸이든 본다.

    ★ 칸 이름을 열거하지 않는다. `raw:` 하나를 막았더니 `columns_error:` 로
      들어왔다 — **문을 하나씩 막으면 다음 문이 열린다.** 값 전체를 훑는다.
    """
    out = []
    for k, v in sch.items():
        for s in (v if isinstance(v, list) else [v]):
            if isinstance(s, str) and ABS_PATH.search(s):
                out.append(k)
                break
    return sorted(set(out))


def unreadable(key: str, sch: dict, kind: str) -> list[str]:
    """읽은 값이 **말이 되는가.** (DECISIONS §338)

    ── 왜 이 물음이 따로 필요한가 ──────────────────────────────
    `--check` 는 「읽은 값이 대장과 같은가」만 묻는다. 그런데 읽는 쪽이
    **일관되게 틀리면** 대장에도 그 틀린 값이 앉아 있고, 그래서 드리프트가
    **영원히 0** 이다. 2026-10-01 실기가 그것이었다 —

        ngii1k   layers: []          드리프트 0
        jijeok   features: 1000000   드리프트 0

    두 값 다 명백히 읽기 실패인데 검사가 초록이었다. **족 1(무음 통과)**이다.

    ★ **증명할 수 있는 것만 문다.** 「필드 이름이 이상하다」는 안 본다 —
      `A0`~`A7` 은 국가공간정보포털 지적도의 **실제 필드명일 수 있고**,
      짐작으로 빨갛게 만들면 고칠 수 없는 빨강이 된다(그런 빨강은 꺼진다).
    """
    bad = []
    lay = sch.get("layers")
    if kind in SHP_KINDS and lay is not None and not lay:
        bad.append(f"{key}: `layers` 가 비었다 — SHP 갈래인데 읽은 레이어가 0개다. "
                   "중첩 zip 이거나 SHP 가 아닌 형식일 수 있다")
    if lay and kind in SINGLE_PICK:
        # ★ `이름`, `이름(2)`, `이름(3)` … 은 레이어 셋이 아니라 **같은 레이어가
        #   여러 도엽에 있는 것**이다. 파일 이름이 겹쳐 OS 가 붙인 꼬리다.
        # ★ §354. 도엽이 여럿인 갈래에서는 **그것이 선언된 모양**이다.
        stems = {re.sub(r"\(\d+\)$", "", str(x)).strip() for x in lay}
        if len(lay) > 1 and len(stems) == 1:
            bad.append(f"{key}: `layers` {len(lay)}개가 전부 `{stems.pop()}` 의 중복 꼬리다 — "
                       "레이어가 여럿인 것이 아니라 **도엽이 여럿**이다")
    # ★ `columns_error` 는 **에러인데 값으로 저장된다.** `probe()` 가 그것을
    #   `sch` 에 담아 돌려주고, `--apply` 가 대장에 쓰고, 다음 실행이 같은 에러를
    #   내므로 드리프트가 0 이다. 2026-10-01 실기에서 juso 전자지도 **여섯**이
    #   그 꼴이었다 — `road_link` · `road_rw` · `road_intrvl` · `boundary_emd` ·
    #   `building` · `building_entrance` 전부 `DataSourceError` 를 들고 초록이었다.
    for k in machine_paths(sch):
        bad.append(f"{key}: `{k}` 에 **기계 고유 경로**가 들어 있다 — "
                   "대장은 어느 기계에서 읽어도 같아야 한다. 경로를 걷고 적어라")
    if sch.get("columns_error"):
        bad.append(f"{key}: `columns_error` 가 대장에 앉아 있다 — "
                   "**읽기 실패가 값이 됐다.** 에러는 기록할 것이 아니라 고칠 것이다")
    n = sch.get("features")
    # ★ §354. 쪼개어 내보내는 소스는 **조각 크기가 둥근 수**다 — 상한이 아니다.
    if (isinstance(n, int) and n >= 100000 and kind in SINGLE_PICK
            and str(n) == "1" + "0" * (len(str(n)) - 1)):
        bad.append(f"{key}: `features: {n}` 이 정확히 10의 거듭제곱이다 — "
                   "실측이 아니라 **상한이나 추정**일 수 있다. 세는 쪽을 확인해라")
    return bad


def probe(key: str, e: dict) -> dict | None:
    """대장 항목 하나의 스키마. 못 읽으면 None."""
    kind = e.get("kind")
    if kind in (None, "raw_only"):
        return None
    files = _led.globs(e)
    if not files:
        return None
    pat = str(files[0])
    hits = sorted(_raw().glob(pat)) if any(c in pat for c in "*?[") else (
        [_raw() / pat] if (_raw() / pat).exists() else [])
    if not hits:
        return {"error": f"실물 없음: {pat}"}
    src = hits[0]
    declared = e.get("encoding")

    try:
        if kind in JSON_KINDS:
            # ★ 값은 안 읽는다. 키 이름과 개수만 본다(이 파일 머리말).
            #   {"fields":[{"id":…}], "records":[…]}  표준데이터
            #   {"Description":{…}, "Data":[…]}       건축물대장
            import json as _json
            raw = _json.loads(src.read_text(encoding=declared or "utf-8"))
            if isinstance(raw, list):
                rows = raw
            else:
                rows = raw.get("records") or raw.get("Data") or []
            cols = list(rows[0]) if rows else []
            out = {"columns": cols[:MAX_COLS], "features": len(rows),
                   "encoding_seen": declared or "utf-8"}
            if len(cols) > MAX_COLS:
                out["layers_total"] = len(cols)
            return out

        if kind in DELIM_KINDS:
            # ★ **헤더가 없다.** 첫 행은 데이터다. csv 분기로 보내면 그 행을
            #   컬럼명으로 먹고 조용히 1행을 잃는다. 컬럼명은 파일에 없고
            #   제공처 활용가이드 PDF 에만 있으므로 `contract.columns` 에
            #   사람이 적는다 — 여기서는 **열 개수와 행 수만** 센다.
            # ★ 기본값의 정본은 `ledger.delimiter_of` 하나다(§284-4).
            delim = _led.delimiter_of(e)
            inner_key = e.get("inner_contains", "")
            if src.suffix.lower() == ".zip":
                with zipfile.ZipFile(src) as z:
                    inner = [n for n in z.namelist()
                             if not n.endswith("/") and inner_key in n]
                    if not inner:
                        return {"error": "zip 안에 대상 파일이 없다"}
                    pick = sorted(inner)[0]
                    with z.open(pick) as f:
                        head = f.read(1 << 16)
                out_src = pick
            else:
                head, out_src = src.read_bytes()[:1 << 16], src.name
            text, used = _decode(head, declared)
            first = next((L for L in text.splitlines() if L.strip()), "")
            # ★ 2026-09-17 (DECISIONS §182-1 · G-14). 종전에는 `error` 로 돌려줬다. run() 은 error 가
            #   있으면 **기록하지 않고 넘어가서** text_table 은 영영 schema 를 못 얻었고,
            #   `firelane.ledger` 는 그것을 `필수 필드 없음: schema` 로 FAIL 했다(navi_build · navi_jibun).
            #   헤더가 없는 것은 오류가 아니라 이 kind 의 성질이다 — 칸으로 적는다.
            return {"columns": [f"c{i:02d}" for i in
                                range(len(first.split(delim)))][:MAX_COLS],
                    "encoding_seen": used, "source": out_src, "headerless": True}

        if kind in CSV_KINDS:
            if src.suffix.lower() == ".zip":
                with zipfile.ZipFile(src) as z:
                    inner = [n for n in z.namelist()
                             if n.lower().endswith(".csv")
                             and (e.get("inner_contains", "") in n)]
                    if not inner:
                        return {"error": "zip 안에 CSV 가 없다"}
                    with z.open(sorted(inner)[0]) as f:
                        out = _csv_header(f.read(1 << 18), declared)
                out["source"] = sorted(inner)[0]
                return out
            return _csv_header(src.read_bytes()[:1 << 18], declared)

        if kind in SHP_KINDS:
            with zipfile.ZipFile(src) as z:
                infos = z.infolist()
                if nested := _nested_layers(z, infos):
                    return nested
            names = [i.filename for i in infos]
            # ★ 2026-09-17 (§182-1). UTF-8 플래그 없는 zip 의 한글 이름은 파이썬이 CP437 로 읽어 `╣╬┐°…` 가 된다
            #   (civil_office). 읽을 때는 그 이름 그대로 써야 열리고, **기록할 때는 사람이 읽는 이름**으로 되돌린다.
            shown = {i.filename: _zip_display(i) for i in infos}
            layers = sorted({Path(shown[n]).stem for n in names
                             if n.lower().endswith((".shp", ".dbf"))})
            out = {"layers": layers[:MAX_COLS]}
            if len(layers) > MAX_COLS:
                out["layers_total"] = len(layers)
            lay = e.get("layer")
            # ★ 2026-09-17 (§182-1). 글롭 레이어(`*.shp` — civil_office, §181-3)는 zip 이름과 맞춰
            #   **정확히 하나**를 고른다. 글롭을 그대로 /vsizip 경로에 넣으면 못 연다.
            if lay and any(ch in lay for ch in "*?["):
                got = [n for n in names if fnmatch.fnmatch(Path(n).name, lay)]
                if len(got) != 1:
                    out["columns_error"] = f"{lay} 가 {len(got)}개다 — 하나여야 한다"
                    return out
                out["layer_glob"], lay = lay, got[0]
            if lay:
                out["layer_used"] = shown.get(lay, lay)
                try:
                    import pyogrio
                    # ★ 2026-09-17 (§182-1). .cpg 없는 cp949 DBF(civil_office)는 인코딩을 안 주면 필드명이
                    #   `À¯Çü` 로 깨진다(모의 레이크 재현). 대장 encoding 을 넘긴다 — ingest 와 같은 규칙.
                    info = pyogrio.read_info(f"/vsizip/{src}/{lay}", encoding=e.get("encoding"))
                    out["columns"] = list(info["fields"])[:MAX_COLS]
                    out["features"] = int(info["features"])
                except Exception as ex:
                    out["columns_error"] = f"{type(ex).__name__}: {ex}"[:90]
            return out
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {ex}"[:110]}
    return None


def _nested_layers(z: zipfile.ZipFile, infos: list) -> dict | None:
    """**zip 안에 zip** 이면 한 겹 더 내려가 레이어 이름을 모은다. (DECISIONS §354)

    ★ `ngii1k` 이 이 모양이다 — 바깥 zip 에 도엽 zip 74장이 있고 `.shp` 가 **없다.**
      그래서 `layers: []` 를 적었고 다시 읽어도 같아 **드리프트가 영원히 0** 이었다.
    ★ **한 장씩 올리고 버린다.** 한꺼번에 펼치면 8GB 기계에서 죽는다(대장 `note`).
    ★ 안쪽 zip 이 없으면 `None` — 중첩 아닌 zip 의 동작을 안 바꾼다.
    """
    inner = [i.filename for i in infos if i.filename.lower().endswith(".zip")]
    if not inner or any(i.filename.lower().endswith(".shp") for i in infos):
        return None
    seen: dict[str, int] = {}
    for name in sorted(inner):
        try:
            with zipfile.ZipFile(io.BytesIO(z.read(name))) as iz:
                # ★ **도엽 단위로 센다.** 한 층이 `.shp` 와 `.dbf` 둘로 오므로
                #   파일 단위로 세면 같은 도엽을 두 번 센다.
                here = {Path(_zip_display(q)).stem for q in iz.infolist()
                        if q.filename.lower().endswith((".shp", ".dbf"))}
        except (zipfile.BadZipFile, OSError):
            continue
        for stem in here:
            seen[stem] = seen.get(stem, 0) + 1
    if not seen:
        return None
    out: dict = {"layers": sorted(seen)[:MAX_COLS], "nested_zips": len(inner)}
    if len(seen) > MAX_COLS:
        out["layers_total"] = len(seen)
    # ★ 전수에 있는 층을 따로 적는다 — 실측 68종 중 다섯뿐이다(§354-1).
    if every := sorted(k for k, n in seen.items() if n == len(inner)):
        out["layers_in_all"] = every[:MAX_COLS]
    return out


def _zip_display(info: zipfile.ZipInfo) -> str:
    """zip 항목 이름을 사람이 읽는 형태로. UTF-8 플래그(0x800)가 없고 CP437 → CP949 로 되돌려지면 그 이름."""
    n = info.filename
    if info.flag_bits & 0x800:
        return n
    try:
        return n.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return n


def _q(v) -> str:
    """YAML 안전 스칼라. 작은따옴표로 감싸고 내부 따옴표는 두 번 쓴다."""
    return "'" + str(v).replace("'", "''") + "'"


def _fmt(sch: dict) -> str:
    """YAML 블록. 손으로 고치지 말라는 표시를 단다."""
    lines = ["    schema:                       # AUTO — ledger_schema.py 가 쓴다"]
    # ★ 2026-10-01 (DECISIONS §340). `error` · `columns_error` 를 **뺐다.**
    #   에러는 **기록할 것이 아니라 고칠 것**이다. 적어 두면 ① 기계 고유 경로가
    #   대장에 박히고(실제로 juso 여섯이 그랬다) ② 다음 실행이 같은 에러를 내므로
    #   **드리프트가 영원히 0** 이다 — 읽기 실패가 「값」이 된다.
    #   에러는 `unreadable()` 이 **매 실행 세고**, `UNREADABLE` 래칫이 든다.
    for k in ("layers", "layer_glob", "layer_used", "columns", "features",
              "encoding_seen", "source", "headerless", "layers_total"):
        if k not in sch:
            continue
        v = sch[k]
        # ★ 전부 따옴표로 감싼다. 컬럼명에 `높이(m)` 처럼 괄호가 있고
        #   에러 메시지에는 콜론이 들어간다 — 맨값으로 쓰면 YAML 이 깨진다.
        #   실증했다(2026-08-26, DataSourceError 의 콜론).
        if isinstance(v, list):
            inner = ", ".join(_q(x) for x in v)
            lines.append(f"      {k}: [{inner}]")
        elif isinstance(v, bool):
            lines.append(f"      {k}: {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"      {k}: {v}")
        else:
            lines.append(f"      {k}: {_q(v)}")
    return "\n".join(lines) + "\n"


# ★ 2026-09-13. 구현은 `firelane.ledger.yaml_span` 한 곳이다. 여기와
#   짝 파일이 글자 하나까지 같았다 — `sources.yaml` 의 구조를 아는 것은
#   `ledger` 소관이고, 두 벌이면 한쪽만 고치는 날이 온다.
_span = _led_yaml_span


def _drop_schema(body: str) -> str:
    return re.sub(r"^    schema:.*\n(?:      .*\n)*", "", body,
                  count=1, flags=re.MULTILINE)


def run(*, apply: bool, check: bool, missing: bool = False) -> int:
    s = YAML.read_text(encoding="utf-8")
    d = yaml.safe_load(s) or {}
    ds = d.get("datasets") or {}
    ok = err = skip = drift = nonsense = 0

    for key, e in ds.items():
        # ★ §182-1. `--missing` — schema 가 이미 있는 항목은 읽지도 쓰지도 않는다.
        #   전량 --apply 는 드리프트가 난 항목까지 조용히 덮어쓴다. 빈 칸만 채울 때 쓴다.
        if missing and e.get("schema"):
            continue
        sch = probe(key, e)
        if sch is None:
            skip += 1
            continue
        if "error" in sch:
            print(f"  ! {key:22} {sch['error']}")
            err += 1
            continue
        cols = sch.get("columns") or sch.get("layers") or []
        print(f"  {key:22} {len(cols):3}개  {', '.join(map(str, cols[:6]))}"
              f"{' …' if len(cols) > 6 else ''}")
        ok += 1

        # ★ 2026-10-01 (§338). **읽은 값이 말이 되는가.** 드리프트와 다른 축이다 —
        #   읽는 쪽이 일관되게 틀리면 드리프트는 영원히 0 이다.
        for why in unreadable(key, sch, str(e.get("kind") or "")):
            print(f"      ★ {why}")
            nonsense += 1

        if check:
            old = (e.get("schema") or {})
            for f in ("columns", "layers"):
                if f in old and f in sch and list(old[f]) != list(sch[f]):
                    a, b = set(map(str, old[f])), set(map(str, sch[f]))
                    print(f"      ★ {f} 가 대장과 다르다 — "
                          f"사라짐 {sorted(a - b)[:4]} · 새로 {sorted(b - a)[:4]}")
                    drift += 1
            continue

        if apply:
            st, en, body = _span(s, key)
            if st < 0:
                continue
            nb = _drop_schema(body) + _fmt(sch)
            s = s[:st] + nb + s[en:]

    if apply:
        yaml.safe_load(s)
        YAML.write_text(s, encoding="utf-8")
        print("\n적용 · YAML 파싱 OK")
    print(f"\n읽음 {ok} · 실패 {err} · 대상아님 {skip}"
          + (f" · ★ 드리프트 {drift}" if check else "")
          + (f" · ★ 못 믿을 값 {nonsense}" if nonsense else ""))
    # ★ 2026-10-01 (§339 · §340). **이것은 드리프트가 아니다.** 대장과 실물이
    #   같은데 둘 다 틀린 상태다. 읽는 쪽을 고쳐야 풀리고 그것은 레이크가 있어야
    #   하는 일이라, 이 배치는 **고치지 않고 센다.** 래칫으로 든다.
    # ★ 래칫이 재는 것은 위 `nonsense`(이번 실행이 **읽은** 값)가 아니라
    #   **대장에 적혀 있는** 수다(§340-4). 둘은 보통 같고, 다르면 그것은
    #   드리프트라 바로 위에서 이미 운다. 대장 쪽을 재는 이유는 하나 —
    #   **레이크 없는 기계에서도 같은 수가 나야** 래칫이 이름을 낼 수 있다.
    led = ledger_nonsense()
    grew = led > UNREADABLE
    if led and not grew:
        print(f"   ★ 대장에 적힌 못 믿을 값 {led} = 래칫 {UNREADABLE} — **갚아야 할 빚이다.**\n"
              "     읽는 쪽(`probe`)을 고쳐야 줄어든다. 대장만 고치면 다음 실행이 되돌린다.")
    if grew:
        print(f"   ★ 못 믿을 값이 {led} 로 **늘었다**(래칫 {UNREADABLE}).\n"
              "     새로 생긴 읽기 실패다 — 이번 배치가 낸 것이다.")
    if led < UNREADABLE:
        print(f"   ★ {led} 로 **줄었다** — `uv run python tools/ratchet.py --write` 로 조여라")
    if not (apply or check):
        print("아무것도 바꾸지 않았다.  --apply 로 기록한다.")
    return 1 if (err or drift or led != UNREADABLE) else 0


def selftest() -> int:
    """판별식이 **두 결함을 실제로 가르는가.** (DECISIONS §338 · §340)"""
    fails = []
    P = "/mnt/f/projects/fire-lane/data/raw/juso/x.zip"

    # ① 2026-10-01 실기의 세 꼴
    if not unreadable("ngii1k", {"layers": []}, "shp_dir"):
        fails.append("빈 `layers` 를 SHP 갈래에서 통과시킨다 — 중첩 zip 을 못 읽은 것이다")
    dup = ["A_20260808", "A_20260808(2)", "A_20260808(3)"]
    if not unreadable("one", {"layers": dup}, "shp_zip"):
        fails.append("중복 꼬리 레이어를 여럿으로 센다 — 도엽이 여럿인 것이다")
    if not unreadable("x", {"features": 1000000}, "csv_points"):
        fails.append("`features: 1000000` 을 실측으로 읽는다")

    # ①′ §354. **도엽이 여럿인 갈래에서는 둘 다 정상이다**(실측 §354-1).
    if unreadable("jijeok", {"layers": dup}, "shp_zip_multi"):
        fails.append("쪼갠 갈래의 중복 꼬리에 운다 — 그것이 선언된 모양이다")
    if unreadable("jijeok", {"features": 1000000}, "shp_zip_multi"):
        fails.append("쪼갠 갈래의 조각 크기에 운다 — 상한이 아니라 내보내기 단위다")

    # ①″ 중첩 zip — `ngii1k` 의 실제 모양. 한 겹 내려가 이름을 모은다
    def _zb(items):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for n, data in items:
                z.writestr(n, data)
        return b.getvalue()

    leaf = _zb([("L1.shp", "x"), ("L1.dbf", "x"), ("L2.shp", "x")])
    outer = _zb([("a.zip", leaf), ("b.zip", _zb([("L1.shp", "x")]))])
    with zipfile.ZipFile(io.BytesIO(outer)) as z:
        got = _nested_layers(z, z.infolist())
    if (got or {}).get("layers") != ["L1", "L2"]:
        fails.append(f"중첩 zip 의 레이어를 못 모은다 — {got}")
    if (got or {}).get("layers_in_all") != ["L1"]:
        fails.append("**전부에 있는 층**을 안 가린다 — 도엽마다 들쭉날쭉하다")
    with zipfile.ZipFile(io.BytesIO(leaf)) as z:
        if _nested_layers(z, z.infolist()) is not None:
            fails.append("평범한 zip 을 중첩으로 본다 — 종전 경로를 바꾸면 안 된다")

    # ② 멀쩡한 것은 **조용해야** 한다 — 안 그러면 사람이 검사를 끈다
    if unreadable("ok", {"columns": ["A", "B"], "features": 63321}, "shp_zip"):
        fails.append("멀쩡한 스키마에 운다 — 고칠 수 없는 빨강은 꺼진다")
    if unreadable("y", {"columns": ["A0", "A1", "A7"]}, "shp_zip_multi"):
        fails.append("`A0`~`A7` 에 운다 — **지적도의 실제 필드명일 수 있다.** 짐작으로 안 문다")
    if unreadable("z", {"features": 100}, "csv_points"):
        fails.append("작은 10의 거듭제곱(100)에 운다 — 진짜 100건일 수 있다")

    # ③ 기계 경로 — **칸 이름을 안 가린다**(§340). 문을 하나씩 막으면 다음이 열린다
    for k in ("columns_error", "error", "layer_used", "source"):
        if machine_paths({k: f"DataSourceError: '/vsizip/{P}'"}) != [k]:
            fails.append(f"`{k}` 칸의 기계 경로를 못 본다 — 칸을 가리고 있다")
    if machine_paths({"layers": [P]}) != ["layers"]:
        fails.append("목록 안의 경로를 못 본다")
    if machine_paths({"columns": ["도로명", "폭(m)"], "features": 12}):
        fails.append("경로가 아닌 값을 경로로 본다")

    # ④ 에러를 **대장에 안 쓰는가** — 쓰면 드리프트가 영원히 0 이다
    body = _fmt({"columns": ["A"], "columns_error": "boom", "error": "boom"})
    for k in ("columns_error", "error"):
        if k in body:
            fails.append(f"`{k}` 를 대장에 쓴다 — 읽기 실패가 **값**이 된다(§340)")

    # ⑤ 래칫이 **이름을 내는가** (§340-4). 안 내면 「래칫 정합」이 빨개진다 —
    #    `deliver.py` 의 시운전이 보내기 전에 그것을 잡았다.
    rv = ratchet_values()
    if set(rv) != set(RATCHETS):
        fails.append(f"`ratchet_values()` 가 {sorted(rv)} 를 내는데 선언은 {sorted(RATCHETS)} 다")
    if not all(isinstance(v, int) for v in rv.values()):
        fails.append("`ratchet_values()` 가 수가 아닌 것을 낸다")
    if rv.get("UNREADABLE") != UNREADABLE:
        fails.append(f"대장 실측 {rv.get('UNREADABLE')} ≠ 선언 {UNREADABLE}"
                     " — 줄었으면 `ratchet.py --write`, 늘었으면 이번 배치가 낸 것이다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 23")
    return 1 if fails else 0


def main() -> int:
    from firelane.paths import require_lake

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="대장과 실물이 어긋났나. CI 가 아니라 사람이 돌린다")
    ap.add_argument("--missing", action="store_true",
                    help="schema 가 없는 항목만 (§182-1)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    # ★ `--selftest` 는 레이크가 없어도 돈다 — 판별식은 합성 입력만 쓴다.
    if a.selftest:
        return selftest()
    # ★ 관문. 레이크가 없으면 여기서 멈춘다 — 판정만 하고 안 막으면
    #   엉뚱한 곳에 계층을 만든다(2026-08-27).
    # ★ **`parse_args` 뒤다.** 앞에 두면 레이크가 없을 때 `--help` 조차
    #   종료 2 로 죽어 「이 도구가 무엇이냐」를 물을 길이 없었다(§283-4).
    require_lake(need=("raw",))
    return run(apply=a.apply, check=a.check, missing=a.missing)


if __name__ == "__main__":
    sys.exit(main())
