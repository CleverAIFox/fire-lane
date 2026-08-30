#!/usr/bin/env python3
"""
triage.py — **대장 밖 파일이 무엇인지 내용으로 판정한다.**

    uv run python tools/triage.py                     Downloads · landing · 격리 전부
    uv run python tools/triage.py --dir /경로          그 폴더만
    uv run python tools/triage.py --plan              실행 계획까지 (아무것도 안 함)
    uv run python tools/triage.py --json

── 왜 필요한가 ────────────────────────────────────────────────
지금 관문은 **이름으로만** 판정한다.

    intake      Downloads → landing   대장 미매칭이면 차단
    acquire     landing  → raw        정규명이 아니면 차단
    --quarantine 대장 밖이면 격리

셋 다 "이름이 대장과 맞는가" 를 묻는다. 그래서 이런 것들이 생겼다 —

    격리 12건 7.3MB   `_kr` 붙기 전 옛 이름. 내용은 raw 와 **완전히 같다**
    격리 hydrant_point_jngj_20250917   raw 것보다 1년 7개월 **최신**인데
                                        이름이 안 맞아서 격리됐다
    landing 18건      원본이 남아 있어 --stage 를 돌리면 다시 격리로 간다

★ **이름이 다르다는 것과 데이터가 다르다는 것은 다르다.** 앞의 것은
  잔해고 뒤의 것은 자산인데, 지금 체계는 둘을 같은 통에 넣는다. 그리고
  격리는 판단 보류지 폐기가 아니라(MASTER §18-12) 아무도 안 본다.

그래서 이 도구는 **내용으로** 묻는다 —

    1. sha 가 raw 의 어떤 파일과 같은가      → 잔해. 지워도 안전
    2. 대장 어떤 항목의 스키마와 맞는가       → 그 dataset 의 다른 판
    3. 맞다면 raw 의 현재 판보다 새로운가     → 승격 후보
    4. 아무것도 아닌가                       → 미상. 사람이 본다

── 무엇을 읽나 ────────────────────────────────────────────────
    sha256          전량. 동일성 판정의 유일한 근거
    인코딩·개행      firelane.encoding
    컬럼·행수        CSV 헤더 + 행 세기
    데이터기준일자    있으면 판(vintage)의 실제 근거가 된다
    좌표 범위        x_col·y_col 이 선언된 dataset 만. scope 를 실측한다

zip·tif·hwp 는 sha 와 크기만 본다. 열지 않는다.

★ 읽기 전용이다. 옮기지도 지우지도 않는다. `--plan` 은 명령을 **출력만**
  한다. 자동 갱신과 파괴를 붙이지 않는다(DECISIONS §73).

IN    sources.yaml · data/_acquire.json · $FIRE_LANE_DATA · Downloads
OUT   없음
PARAM 없음
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

from firelane import encoding as enc
from firelane import paths

ROOT = paths.ROOT
ACQ = ROOT / "data" / "_acquire.json"
TEXT = {".csv", ".txt", ".tsv"}

#  ★ 임계가 둘이다. 하나로 쓰면 반드시 한쪽이 망가진다.
#    2026-08-27. 진단을 위해 0.5 → 0.15 로 낮췄더니 **판정까지 같이
#    낮아져** 일치 15% 인 `safety_firestation_kr_20250701.csv`(컬럼 6개,
#    좌표 없음)를 "유사 스키마" 로 냈다. 좌표가 없어 파이프라인이 쓸 수
#    없는 파일인데 대장 항목의 다른 판인 것처럼 보고했다.
#      SHOW  이만큼 겹치면 **차이를 보여준다**. 판정이 아니다
#      CALL  이만큼 겹쳐야 **같은 dataset 이라고 말한다**
SHOW, CALL, SAME = 0.15, 0.60, 0.99

#  ★ 데이터 자산이 아닌 것. 판정 대상에서 뺀다.
#    2026-08-27. Downloads 를 훑었더니 `desktop.ini` 와 이 도구 자신에게
#    "대장에 등재하거나 retired 로 근거를 남겨라" 를 냈다. **오탐이다.**
#    오탐은 강제자를 죽인다 — 정상을 막으면 사람이 우회하고, 우회가
#    습관이 되면 관문이 없는 것과 같다(DECISIONS §73).
#    출발지는 우리가 소유하지 않는 계층이라(paths.inbox 머리말) 남의
#    파일이 섞여 있는 것이 정상이다. 조용히 넘긴다.
IGNORE_NAME = {"desktop.ini", "thumbs.db", ".ds_store"}
IGNORE_EXT = {".py", ".sh", ".ps1", ".bat", ".exe", ".msi", ".lnk", ".url",
              ".tmp", ".crdownload", ".part", ".log", ".ini"}
BIG = 1 << 28                       # 256MB 넘으면 sha 를 건너뛴다(옵션으로 강제)


def sha256(p: Path, *, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def cfg() -> dict:
    return yaml.safe_load((ROOT / "sources.yaml").read_text("utf-8")) or {}


def retired() -> dict[str, tuple[str, str]]:
    """폐기 등재된 파일 이름 → (등재키, 사유 첫 줄).

    ★ 2026-08-27. 이 조회가 없어서 격리 4건 중 **3건을 "미상" 으로 냈다.**
      셋 다 2026-08-23~24 에 사람이 열어보고 판단을 끝내 `retired` 에
      근거까지 적어 둔 것이었다. 오탐이다.

      `mas_optional_20241111` 의 reason 이 정확히 그 위험을 적고 있다 —
      *"안 열어보고 내렸으면 3개월 뒤 또 받고 또 조사했을 것이다."*
      판단이 끝난 것을 "미상" 으로 보여주면 **같은 조사를 다시 시킨다.**

    ★ `successor` 에서 파일명을 뽑지 않는다. successor 는 **대체한 쪽**,
      즉 지금 쓰는 활성 파일이다. 그것을 폐기 목록에 넣으면 살아 있는
      raw 를 "내려도 된다" 로 표시한다(acquire.retired_names 와 같은 이유).

    ★ 확장자를 넓히지 않는다. `.hwp` 를 등재했다고 `.pdf` 까지 폐기로
      보면 안 된다 — 포맷이 다르면 다른 파일이다(naming.py 머리말).
      대신 줄기가 같은데 확장자만 다른 것은 "부분 등재" 로 알린다.
    """
    out: dict[str, tuple[str, str]] = {}
    for k, v in (cfg().get("retired") or {}).items():
        v = v or {}
        why = str(v.get("reason") or v.get("what") or k).strip().splitlines()[0]
        for f in ([v["file"]] if v.get("file") else []) + list(v.get("files") or []):
            out[Path(str(f)).name] = (k, why)
    return out


def acquire() -> dict:
    if not ACQ.exists():
        return {}
    return json.loads(ACQ.read_text("utf-8")).get("files", {})


# ── 내용 읽기 ─────────────────────────────────────────────────
def probe_csv(p: Path, declared: str | None, entry: dict | None = None) -> dict:
    """헤더·행수·기준일자·좌표범위. 실패해도 죽지 않는다.

    ★ 좌표 컬럼을 이름으로 추측하지 않는다. **대장이 정본이다.**
      `fire_station` 은 `x_col: Y좌표` · `y_col: X좌표` 로 뒤집혀 선언돼
      있다 — 원본이 그렇게 들어왔고 prep 은 값을 안 고친다. 이름으로
      추측하면 그 데이터셋에서만 조용히 틀린다.
      선언이 없을 때만 흔한 이름으로 넘겨짚고, 그 사실을 표시한다.
    """
    out: dict = {}
    try:
        v = enc.detect(p)
        out["encoding"] = v.encoding
        out["newline"] = v.newline
        out["hangul"] = round(v.hangul_ratio, 3)
        if getattr(v, "notes", None):
            out["encoding_notes"] = list(v.notes)[:3]
    except Exception as ex:                                  # noqa: BLE001
        out["encoding_error"] = f"{type(ex).__name__}: {ex}"
    use = declared or out.get("encoding") or "utf-8"
    try:
        raw = p.read_bytes()
        text = raw.decode(use, errors="replace")
        # ★ 깨짐 신호. 디코드 성공은 증거가 아니다(encoding.py 머리말).
        out["replacement"] = text.count("\ufffd")
        rdr = csv.reader(io.StringIO(text))
        head = next(rdr, [])
        out["columns"] = [c.strip().lstrip("\ufeff") for c in head]
        n, dates = 0, []
        xi = yi = di = None
        xn = (entry or {}).get("x_col")
        yn = (entry or {}).get("y_col")
        if xn or yn:
            out["coord_src"] = f"대장 선언 x={xn} y={yn}"
        else:
            xn, yn = None, None
            out["coord_src"] = "추정(경도/위도 · X/Y좌표)"
        for i, c in enumerate(out["columns"]):
            if xn and c == xn:
                xi = i
            elif yn and c == yn:
                yi = i
            elif not xn and c in ("경도", "lon", "x"):
                xi = i
            elif not yn and c in ("위도", "lat", "y"):
                yi = i
            if "기준일" in c:
                di = i
        xs, ys = [], []
        for row in rdr:
            n += 1
            if di is not None and di < len(row) and row[di].strip():
                dates.append(row[di].strip())
            for idx, acc in ((xi, xs), (yi, ys)):
                if idx is not None and idx < len(row):
                    try:
                        acc.append(float(row[idx]))
                    except ValueError:
                        pass
        out["rows"] = n
        if dates:
            out["기준일자"] = f"{min(dates)} ~ {max(dates)}" if min(dates) != max(dates) else min(dates)
        if xs and ys:
            out["bbox"] = [round(min(xs), 4), round(min(ys), 4),
                           round(max(xs), 4), round(max(ys), 4)]
            b = cfg().get("bbox_4326") or []
            if len(b) == 4:
                inside = sum(1 for x, y in zip(xs, ys, strict=False)
                             if b[0] <= x <= b[2] and b[1] <= y <= b[3])
                out["대상지_내"] = f"{inside} / {len(xs)}"
                # ★ 0건이면 축을 바꿔서 한 번 더 본다. 한국에서 경도는
                #   124~132, 위도는 33~39 라 겹치지 않으므로 판별된다.
                #   "0건" 과 "축이 뒤집혔다" 는 완전히 다른 결론이고,
                #   전자로 오판하면 멀쩡한 자산을 버린다.
                if inside == 0:
                    swap = sum(1 for x, y in zip(xs, ys, strict=False)
                               if b[0] <= y <= b[2] and b[1] <= x <= b[3])
                    if swap:
                        out["★축반전"] = f"x↔y 로 보면 {swap}건이 대상지 안이다"
    except Exception as ex:                                  # noqa: BLE001
        out["parse_error"] = f"{type(ex).__name__}: {ex}"
    return out


# ── 판정 ──────────────────────────────────────────────────────
def match_schema(cols: list[str], DS: dict) -> list[tuple]:
    """컬럼 집합으로 대장 항목을 맞춘다. (키, 자카드, 없는컬럼, 남는컬럼).

    ★ 임계를 0.5 에서 0.15 로 낮췄다. 2026-08-27 에 소화전·소방서 후보가
      **하나도 안 걸려 "미상" 으로 떨어졌고**, 왜 안 맞았는지 볼 방법이
      없었다. 판정을 못 하는 것보다 나쁜 것은 **왜 못 하는지 모르는 것**
      이다. 낮게 걸고 차이를 보여준다 — 판단은 사람이 한다.
    """
    s = set(cols)
    hits = []
    for k, e in DS.items():
        want = set((e.get("schema") or {}).get("columns") or [])
        if not want:
            continue
        j = len(s & want) / len(s | want) if (s | want) else 0
        if j > SHOW:
            hits.append((k, round(j, 3), sorted(want - s), sorted(s - want)))
    return sorted(hits, key=lambda x: -x[1])[:3]


def triage(p: Path, *, DS: dict, ACQ_: dict, raw_sha: dict) -> dict:
    r: dict = {"path": str(p), "name": p.name, "bytes": p.stat().st_size,
               "ext": p.suffix.lower()}
    if p.name.lower() in IGNORE_NAME or r["ext"] in IGNORE_EXT:
        r["verdict"] = "무관"
        r["action"] = ""
        return r
    if r["bytes"] < BIG:
        r["sha"] = sha256(p)
    else:
        r["sha"] = None
        r["note_sha"] = "256MB 초과 — sha 생략"

    #  ① 내용이 raw 와 같은가
    if r["sha"] and r["sha"] in raw_sha:
        r["verdict"] = "잔해"
        r["same_as"] = raw_sha[r["sha"]]
        r["action"] = "삭제 안전. raw 에 같은 내용이 이미 있다"
        return r

    #  ② 폐기 등재 — 판단이 끝난 것이다
    RET = retired()
    if p.name in RET:
        key, why = RET[p.name]
        r["verdict"] = "판단완료"
        r["retired"] = key
        r["action"] = f"retired.{key} — {why}"
        return r
    #  줄기는 같은데 확장자만 다른 폐기 항목이 있나 (hwp 등재 · pdf 미등재)
    stem = p.stem
    part = [(n, kv) for n, kv in RET.items() if Path(n).stem == stem]
    if part:
        key, why = part[0][1]
        r["verdict"] = "★ 폐기 부분등재"
        r["retired"] = key
        r["action"] = (f"retired.{key} 는 {[n for n, _ in part]} 만 적는다. "
                       f"이 파일({r['ext']})은 등재 밖이다 — files: 에 추가해라. "
                       "포맷이 다르면 다른 파일이고, 안 적으면 매번 다시 받는다")
        return r

    #  ③ 크기가 같은 raw 파일 — sha 는 다르다. 인코딩만 다를 수 있다
    same_size = [k for k, v in ACQ_.items() if v.get("bytes") == r["bytes"]]
    if same_size:
        r["same_size_as"] = same_size

    #  ③ 텍스트면 내용을 읽는다
    if r["ext"] in TEXT:
        cand = None
        for k in same_size:
            for _dk, e in DS.items():
                for pat in (e.get("files") or []):
                    if str(pat).endswith(Path(k).name):
                        cand = e
        #  ★ 두 번 읽는다. 1차는 선언 없이 헤더만 얻고, 그것으로 대장
        #    항목을 찾은 뒤 2차에서 **그 항목의 encoding·x_col·y_col 로**
        #    다시 잰다. 한 번만 읽으면 좌표 컬럼을 이름으로 넘겨짚게 되고,
        #    `fire_station`(x_col: Y좌표)처럼 뒤집힌 선언에서 틀린다.
        r["probe"] = probe_csv(p, (cand or {}).get("encoding"), cand)
        cols = r["probe"].get("columns") or []
        r["schema_match"] = match_schema(cols, DS)
        if r["schema_match"] and not cand:
            top = DS.get(r["schema_match"][0][0]) or {}
            if top.get("x_col") or top.get("encoding"):
                r["probe"] = probe_csv(p, top.get("encoding"), top)
                r["schema_match"] = match_schema(
                    r["probe"].get("columns") or [], DS)

        # ★ 깨짐은 스키마 매칭보다 **먼저** 본다. 헤더가 깨지면 컬럼이
        #   안 맞아서 매칭이 실패하고, 그러면 "미상" 으로 떨어져 격리로
        #   간다. 원인이 인코딩인데 판정이 "정체불명" 으로 나오면 사람이
        #   엉뚱한 것을 찾는다 — 2026-08-27 Downloads 의 주정차 CSV 가
        #   그 형태였다.
        bad = r["probe"].get("replacement") or 0
        if bad:
            r["verdict"] = "★ 인코딩 깨짐"
            r["action"] = (f"U+FFFD {bad}자. 다시 받거나 대장의 encoding "
                           "선언을 고쳐라. 이 상태로 편입하면 norm 이 "
                           "깨진 것을 그대로 굳힌다")
            if r["schema_match"]:
                r["dataset"] = r["schema_match"][0][0]
            return r

        if r["schema_match"] and r["schema_match"][0][1] >= CALL:
            key, j = r["schema_match"][0][0], r["schema_match"][0][1]
            e = DS[key]
            r["verdict"] = "동일 스키마" if j >= SAME else "유사 스키마"
            r["dataset"] = key
            r["ledger_updated"] = e.get("updated")
            r["ledger_scope"] = e.get("scope")
            #  판 비교 — 기준일자가 있으면 그것이 근거다
            d = r["probe"].get("기준일자", "")
            newer = d and e.get("updated") and d[:10].replace(".", "-") > str(e["updated"])
            if newer:
                r["verdict"] = "★ 신판 후보"
                r["action"] = (f"{key} 의 현재 판({e.get('updated')})보다 새롭다. "
                               "대장에 등재할지 판단하고 golden 으로 영향을 재라")
            else:
                r.setdefault("action",
                             f"{key} 와 같은 스키마인데 sha 가 다르다. "
                             "다른 판이거나 인코딩만 다르다 — 행수·기준일자를 봐라")
            return r

    #  ④ 이름으로도 스키마로도 못 맞췄다
    r["verdict"] = "미상"
    r["action"] = "대장에 없다. 등재하거나 retired 로 근거를 남겨라"
    return r


# ── 출력 ──────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", action="append", default=None)
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--apply", action="store_true",
                    help="잔해로 판정된 것만 지운다. --yes 가 함께 있어야 한다")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--vs", action="append", default=None,
                    help="이 대장 키의 현재 raw 판을 같이 재서 나란히 본다. "
                         "★ 대조군 없이는 '대상지 0건' 이 데이터 탓인지 "
                         "판정 코드 탓인지 못 가른다")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    DS = cfg().get("datasets") or {}
    ACQ_ = acquire()
    raw_sha = {v["sha256"]: k for k, v in ACQ_.items() if "sha256" in v}

    if a.dir:
        dirs = [Path(d).expanduser() for d in a.dir]
    else:
        dirs = [paths.inbox(), paths.LANDING, paths.QUARANTINE]

    rows = []
    for d in dirs:
        if not d.is_dir():
            print(f"! 없다: {d}", file=sys.stderr)
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                rows.append((d, triage(p, DS=DS, ACQ_=ACQ_, raw_sha=raw_sha)))

    #  대조군 — 후보와 같은 잣대로 raw 현재 판을 잰다
    if a.vs:
        base = {}
        for key in a.vs:
            e = DS.get(key)
            if not e:
                print(f"! 대장에 없는 키: {key}", file=sys.stderr)
                continue
            for pat in (e.get("files") or []):
                hits = sorted(paths.RAW.glob(pat)) if paths else []
                for h in hits:
                    if h.suffix.lower() in TEXT:
                        pv = probe_csv(h, e.get("encoding"), e)
                        base[key] = {"file": str(h.relative_to(paths.RAW)),
                                     "rows": pv.get("rows"),
                                     "대상지_내": pv.get("대상지_내"),
                                     "bbox": pv.get("bbox"),
                                     "columns": pv.get("columns")}
        #  ★ 대조군은 **그 파일의 후보** 에 붙인다. 종전에는 --vs 첫 키를
        #    무조건 붙여서 `firestation` 후보에 `hydrant_point` 대조군이
        #    달렸다. 엉뚱한 대조군은 없는 것보다 나쁘다 — 사람이 그 숫자로
        #    판단한다.
        for _, r in rows:
            if not r.get("probe"):
                continue
            want = [k for k, _j, _m, _e in (r.get("schema_match") or [])]
            want += [k for k in a.vs if k in r["name"].replace("-", "_")]
            for key in want:
                if key in base:
                    r["vs"] = base[key]
                    break
            else:
                if len(a.vs) == 1 and a.vs[0] in base:
                    r["vs"] = base[a.vs[0]]

    if a.json:
        print(json.dumps([r for _, r in rows], ensure_ascii=False, indent=1))
        return 0

    show = [(d, r) for d, r in rows if r["verdict"] != "무관"]
    skipped = len(rows) - len(show)
    cur = None
    for d, r in show:
        if d != cur:
            cur = d
            print(f"\n══ {d}")
        print(f"\n  {r['name']}   {r['bytes'] / 1e6:.2f}MB")
        print(f"    판정  {r['verdict']}")
        if r.get("same_as"):
            print(f"    동일  raw/{r['same_as']}")
        if r.get("retired"):
            print(f"    폐기  retired.{r['retired']}")
        if r.get("dataset"):
            print(f"    대장  {r['dataset']}  "
                  f"(현재 판 {r.get('ledger_updated')} · scope {r.get('ledger_scope')})")
        pr = r.get("probe") or {}
        bits = []
        for k in ("encoding", "newline", "rows", "기준일자", "대상지_내"):
            if pr.get(k) is not None:
                bits.append(f"{k} {pr[k]}")
        if pr.get("replacement"):
            bits.append(f"★ U+FFFD {pr['replacement']}")
        if bits:
            print("    내용  " + " · ".join(str(b) for b in bits))
        if pr.get("columns"):
            c = pr["columns"]
            print(f"    컬럼  {len(c)}개  {c[:10]}" + (" …" if len(c) > 10 else ""))
        if pr.get("bbox"):
            print(f"    범위  {pr['bbox']}   ({pr.get('coord_src')})")
        if pr.get("★축반전"):
            print(f"    ★★★  {pr['★축반전']}")
        for m in (r.get("schema_match") or [])[:3]:
            k, j, missing, extra = m
            print(f"    후보  {k}  일치 {j:.0%}")
            if missing:
                print(f"          대장에만 {missing[:6]}")
            if extra:
                print(f"          파일에만 {extra[:6]}")
        if r.get("vs"):
            v = r["vs"]
            print(f"    대조  raw/{v['file']}")
            print(f"          rows {v.get('rows')} · 대상지_내 {v.get('대상지_내')}"
                  f" · 범위 {v.get('bbox')}")
        if r.get("action"):
            print(f"    → {r['action']}")

    print("\n── 요약")
    c = Counter(r["verdict"] for _, r in rows)
    for k, n in c.most_common():
        if k != "무관":
            print(f"  {k:14} {n}")
    if skipped:
        print(f"  {'(무관)':14} {skipped}   데이터 자산 아님 — 판정 안 함")

    junk = [r for _, r in rows if r["verdict"] == "잔해"]

    if a.plan and not a.apply:
        print("\n── 계획 (실행하지 않는다)")
        for r in junk:
            print(f"  rm {r['path']!r}          # = raw/{r['same_as']}")
        print(f"\n  {len(junk)}건 · {sum(r['bytes'] for r in junk) / 1e6:.1f}MB")
        print("  실제로 지우려면  --apply --yes")
        return 0

    if a.apply:
        return apply_delete(junk, yes=a.yes)
    return 0


def apply_delete(junk: list[dict], *, yes: bool) -> int:
    """★ **잔해로 판정된 것만** 지운다. 그것도 다시 확인하고 지운다.

    ── 왜 다시 해싱하나 ───────────────────────────────────────
    위의 스캔과 여기 사이에 시간이 흐른다. `--plan` 출력을 복붙하면 그
    간격이 몇 분에서 며칠이 된다. 그 사이에 raw 가 바뀌었으면 "같은
    내용" 이 아니게 되고, 그러면 **살아 있는 유일본을 지운다.**

    이 저장소가 이미 겪은 형태다 — `ledger_stem` 이 실물을 읽어 대장을
    고치고 `--quarantine` 이 그 대장으로 실물을 내렸다. 판정과 파괴
    사이가 벌어지면 사고가 난다. 그래서 **파괴 직전에 양쪽을 다시 잰다.**

    ── 왜 빈 부모를 지우나 ────────────────────────────────────
    `acquire.cmd_quarantine()` 이 `shutil.move` 만 하고 부모를 안 지워서
    `raw/nsdi/` 껍데기가 남았고, 어떤 검사도 그것을 못 봤다(2026-08-27).
    같은 것을 여기서 반복하지 않는다.
    """
    if not junk:
        print("\n지울 것이 없다.")
        return 0
    tot = sum(r["bytes"] for r in junk)
    print(f"\n── 삭제 대상 {len(junk)}건 · {tot / 1e6:.1f}MB")
    if not yes:
        print("  --yes 가 없다. 아무것도 안 지웠다.")
        return 1

    ACQ_ = acquire()
    gone = kept = 0
    parents: set[Path] = set()
    for r in junk:
        f = Path(r["path"])
        twin = (paths.RAW / r["same_as"]) if paths else None
        if not f.exists():
            print(f"  건너뜀  {f.name}   이미 없다")
            continue
        #  ★ 지금 다시 잰다. 스캔 결과를 믿지 않는다.
        now = sha256(f)
        if now != r["sha"]:
            print(f"  ✗ 보류  {f.name}   스캔 이후 내용이 바뀌었다")
            kept += 1
            continue
        if twin is None or not twin.exists():
            print(f"  ✗ 보류  {f.name}   raw 짝이 없다: {r['same_as']}")
            kept += 1
            continue
        if sha256(twin) != now:
            print(f"  ✗ 보류  {f.name}   raw 짝의 내용이 달라졌다")
            kept += 1
            continue
        if ACQ_.get(r["same_as"], {}).get("sha256") not in (None, now):
            print(f"  ✗ 보류  {f.name}   sha 대장과 raw 가 어긋난다")
            kept += 1
            continue
        f.unlink()
        parents.add(f.parent)
        gone += 1
        print(f"  삭제  {f.name}")

    #  빈 부모 정리. 껍데기를 남기지 않는다.
    for d in sorted(parents, key=lambda x: -len(x.parts)):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
                print(f"  빈폴더 제거  {d.name}/")
        except OSError:
            pass

    print(f"\n삭제 {gone} · 보류 {kept}")
    if kept:
        print("  ★ 보류된 것은 손대지 않았다. 다시 스캔해서 원인을 봐라.")
    return 1 if kept else 0


if __name__ == "__main__":
    sys.exit(main())
