#!/usr/bin/env python3
"""
prep.py — raw → norm. **형식만 통일한다. 값은 안 바꾼다.**

    uv run python -m firelane.prep              계획만 (아무것도 안 쓴다)
    uv run python -m firelane.prep --apply       실행
    uv run python -m firelane.prep --check       norm 이 raw 와 정합한가

── 경계 ───────────────────────────────────────────────────────
바꾸는 것 셋 —
    인코딩   → UTF-8 (BOM 없음)
    개행     → LF
    파일명   → 대장의 정규명

★ 그 밖의 무엇도 바꾸지 않는다. 컬럼명 공백을 털고 싶어지고, 빈 문자열을
  NA 로 바꾸고 싶어지고, 좌표 컬럼명이 반대인 것(`fire_station` 의 X좌표에
  위도가 들어 있다)을 고치고 싶어진다. **하면 안 된다.**

  norm 의 값어치는 "원본이 그랬는지 우리가 고친 건지" 를 언제나 가릴 수
  있다는 것 하나다. 그 경계가 흐려지면 norm 은 processed 의 나쁜 사본이
  된다. 값 보정은 `ingest` 가 하고 그 사실이 계보에 남는다.

── 왜 멱등해야 하나 ───────────────────────────────────────────
`normalize_raw` 가 **크기로** "이미 있음" 을 판정했다. 313MB 정사영상이
전송 중 잘려도 같은 크기면 통과했고, 실증됐다(2026-08-23). 여기서는
`_prep.json` 에 (src_sha, dst_sha) 쌍을 남기고 **양쪽 다** 대조한다.
raw 가 바뀌면 다시 만들고, norm 이 손상되면 다시 만든다.

── 미구현이던 이유 ────────────────────────────────────────────
`layers.norm.status: 미구현` 이었고 caveat 이 이렇게 적고 있었다 —
*"디렉터리 문제가 아니라 변환 문제다. ingest 입력 경로가 전부 바뀐다."*

맞다. 그래서 **소스 하나씩 옮긴다.** `layers.norm.migrated` 에 키를 쌓고,
`source_path()` 가 그 목록을 보고 norm 과 raw 중 하나를 돌려준다.
전량 전환 없이 한 건씩 이동할 수 있고, 매 건 `golden.py check` 로
산출물 불변을 확인한다.

★ 2026-09-17. **서식 PDF → CSV 변환기**가 하나 붙었다(DECISIONS §172). 대장 항목이
  `norm_convert: <이름>` 을 적으면 raw PDF 를 그 변환기로 읽어 norm 에 **같은 이름의
  `.csv`** 를 쓴다. 경계는 같다 — 서식의 칸을 표의 칸으로 옮길 뿐 값은 글자 그대로다
  (`7,770` 은 `7,770`). 지금 변환기는 `vehiclecard`(소방자동차 관리카드) 하나다.

IN    $FIRE_LANE_DATA/raw · sources.yaml
OUT   $FIRE_LANE_DATA/norm · data/_prep.json (커밋한다)
PARAM 없음
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from firelane import encoding as enc
from firelane import ledger as _led
from firelane.encoding import TEXT_EXT_PREP
from firelane.paths import NORM, RAW, ROOT

KST = timezone(timedelta(hours=9))
STATE = ROOT / "data" / "_prep.json"

# 텍스트만 정규화한다. zip · tif · shp 는 바이트를 건드릴 수 없다.
# 정본은 firelane/encoding.py. 이름이 쓰임을 말한다 — 여기 것은 '전처리 대상'이고
# encoding.TEXT_EXT(자료 형식)와 값이 다르다. 같은 이름을 쓰던 것이 잘못이었다.
TEXT_EXT = TEXT_EXT_PREP

# 서식 변환기. 대장 `norm_convert` 값 → (받는 확장자, 모듈 경로). 이 표 밖의 값은 실패한다.
CONVERTERS = {"vehiclecard": (".pdf", "firelane.vehiclecard")}


def _converter(e: dict) -> str | None:
    name = (e or {}).get("norm_convert")
    if name and name not in CONVERTERS:
        raise ValueError(f"대장 norm_convert `{name}` 은 변환기 표에 없다 — {sorted(CONVERTERS)}")
    return name


def dst_rel(rel: str, e: dict) -> str:
    """norm 쪽 상대경로. 변환기가 있으면 확장자만 `.csv` 로 바뀐다."""
    return str(Path(rel).with_suffix(".csv")) if _converter(e) else rel


from firelane.hashing import sha256 as _h_sha256


def sha256(p, chunk: int = 1 << 20) -> str:
    # ★ 2026-09-13. 구현은 `firelane.hashing` 한 곳이다.
    #   이름은 호출부 때문에 남긴다 — 옮긴 것과 고친 것을
    #   한 커밋에 섞지 않는다(원칙 ⑤).
    return _h_sha256(p, chunk)


def _sources() -> dict:
    return _led.load_sources()


def migrated() -> set[str]:
    """norm 으로 옮긴 소스 키. 여기 없는 것은 아직 raw 를 읽는다."""
    L = (_sources().get("layers") or {}).get("norm") or {}
    return set(L.get("migrated") or [])


def source_path(key: str, rel: str) -> Path:
    """이 소스를 지금 어디서 읽어야 하나. **ingest 가 이것만 부른다.**

    ★ 이 함수가 있어서 전량 전환이 필요 없다. 한 건 옮기고, 여기가
      알아서 갈라주고, golden 으로 불변을 확인하고, 다음 건으로 간다.
    """
    if key in migrated():
        p = NORM / rel
        if p.exists():
            return p
        raise FileNotFoundError(
            f"{key} 는 norm 으로 마이그레이션됐다고 선언됐는데 실물이 없다: {p}\n"
            "  ★ 선언과 실물이 어긋난다. prep --apply 를 돌리거나\n"
            "    sources.yaml 의 layers.norm.migrated 에서 키를 빼라.")
    return RAW / rel


def _load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"files": {}, "at": None}


def _targets() -> list[tuple[str, str, dict]]:
    """(key, 상대경로, 대장항목). 텍스트 파일만.

    ★ 취득 사이드카는 `ledger.is_acquisition_meta` 로 뺀다. **`ingest` 와
      같은 규칙을 봐야 한다.** 둘이 다른 집합을 보면 한쪽이 안 만든 것을
      다른 쪽이 요구한다 — 2026-09-13 `hydrant_point` 가 그랬다.
    """
    out = []
    for key, e in (_sources().get("datasets") or {}).items():
        conv = _converter(e)
        exts = {CONVERTERS[conv][0]} if conv else TEXT_EXT
        files = _led.globs(e)
        for pat in files:
            if any(c in pat for c in "*?["):
                for p in sorted(RAW.glob(pat)):
                    if (p.suffix.lower() in exts
                            and not _led.is_acquisition_meta(p)):
                        out.append((key, str(p.relative_to(RAW)), e))
            elif (Path(pat).suffix.lower() in exts
                    and not _led.is_acquisition_meta(pat)):
                out.append((key, pat, e))
    return out


def run(*, apply: bool) -> int:
    st = _load_state()
    done = skip = miss = 0
    for key, rel, e in _targets():
        src = RAW / rel
        if not src.exists():
            print(f"  결손  {rel}   (대장에 있는데 raw 에 없다)")
            miss += 1
            continue
        ssha = sha256(src)
        drel = dst_rel(rel, e)
        dst = NORM / drel
        rec = st["files"].get(rel)
        conv_ver = None
        if _converter(e):
            import importlib
            conv_ver = importlib.import_module(CONVERTERS[_converter(e)][1]).VERSION
        if (rec and rec["src_sha256"] == ssha and dst.exists()
                and sha256(dst) == rec["dst_sha256"]
                and rec.get("converter_version") == conv_ver):   # ★ 변환 규칙이 바뀌면 다시 만든다
            skip += 1
            continue

        conv = _converter(e)
        if conv:
            tag = "변환" if apply else "변환 예정"
            print(f"  {tag}  {rel}  → {drel}   ({conv})")
            if apply:
                import importlib
                meta = importlib.import_module(CONVERTERS[conv][1]).convert(src, dst)
                st["files"][rel] = {"key": key, "dst": drel, "src_sha256": ssha,
                                    "dst_sha256": sha256(dst), **meta,
                                    "at": datetime.now(KST).isoformat(timespec="seconds")}
            done += 1
            continue

        declared = e.get("encoding")
        v = enc.detect(src)
        problems = enc.verify_declared(src, declared) if declared else []
        tag = "정규화" if apply else "정규화 예정"
        print(f"  {tag}  {rel}")
        print(f"        {v.encoding}/{v.newline} → utf-8/lf"
              f"   한글 {v.hangul_ratio:.3f}")
        for p in problems:
            print(f"        ★ {p.splitlines()[0]}")
        if not apply:
            done += 1
            continue
        # ★ 선언이 있으면 선언으로 읽는다. 판별은 대조용이지 결정용이 아니다.
        #   판별로 읽으면 대장이 정본이라는 원칙이 깨지고, 인코딩이 실행마다
        #   달라질 수 있다.
        meta = enc.to_norm(src, dst, declared=declared or v.encoding)
        st["files"][rel] = {
            "key": key, "src_sha256": ssha, "dst_sha256": sha256(dst),
            **meta,
            "at": datetime.now(KST).isoformat(timespec="seconds"),
        }
        done += 1

    if apply:
        st["at"] = datetime.now(KST).isoformat(timespec="seconds")
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n",
                         encoding="utf-8")
    print(f"\n{'정규화' if apply else '대상'} {done} · 최신 {skip} · 결손 {miss}")
    if not apply and done:
        print("  실제로 쓰려면 --apply")
    return 1 if miss else 0


def check(cap: int | None = None) -> int:
    """norm 이 지금의 raw 에서 나온 것인가. **재현성 게이트다.**

    ★ `cap` 은 허용 상한이다. 지금 값에서 시작해 내린다 — 0 을
      요구하면 게이트가 영영 빨갛고, 빨간 게이트는 아무도 안 본다.
    """
    st = _load_state()
    stale = broken = ok = 0
    # ★ 2026-09-13. 종전에는 `st["files"]` 만 돌았다. **상태 파일에 없는
    #   대상은 아예 안 셌다.** `정상 18` 의 18은 과거에 처리한 것 개수지
    #   지금 있어야 할 것 개수가 아니었다 — 자기가 아는 것만 자기가 맞다고
    #   확인하는 검사다(deadcheck ① 빈 그물). 대상 집합과 대조한다.
    want = {rel for _k, rel, _e in _targets()}
    unseen = sorted(want - set(st["files"]))
    for rel in unseen:
        print(f"  미등록  {rel}   대상인데 _prep.json 에 없다 — --apply 를 돌려라")
    broken += len(unseen)
    for rel, rec in st["files"].items():
        src, dst = RAW / rel, NORM / rec.get("dst", rel)
        if not dst.exists():
            print(f"  누락  {rel}")
            broken += 1
        elif sha256(dst) != rec["dst_sha256"]:
            print(f"  손상  {rel}   norm 이 기록과 다르다")
            broken += 1
        elif src.exists() and sha256(src) != rec["src_sha256"]:
            print(f"  낡음  {rel}   raw 가 바뀌었다 — prep --apply 를 돌려라")
            stale += 1
        else:
            ok += 1
    print(f"\n정상 {ok} · 낡음 {stale} · 손상 {broken}")
    n = stale + broken
    if cap is None:
        return 1 if n else 0
    # ★ 2026-09-14. 래칫. 지금 값에서 시작해 내린다 — 0 을 요구하면
    #   영영 빨갛고, 빨간 게이트는 아무도 안 본다(원칙 ③).
    if n > cap:
        print(f"\u2717 상한 {cap} 을 넘었다 ({n}). 늘었다.")
        return 1
    # ★ 2026-09-20 (W4-9). **미달도 실패다.** 종전에는 「조여라」를
    #   찍고 `return 0` 했다. 초록은 「문턱을 지켰다」는 뜻이지 「문턱이
    #   아직 의미 있다」는 뜻이 아니다 — **느슨해진 래칫은 초록으로
    #   위장한다.** 2026-09-19 에 커버리지 래칫이 14 인데 실물이 24%
    #   인 것을 나흘간 아무도 몰랐고, 그것이 이 행의 실물이었다.
    #   `gate_parity` 는 처음부터 양방향이었다. 넷을 그쪽에 맞춘다.
    if n < cap:
        print(f"\u2717 상한 {cap} 보다 {cap - n} 적다 ({n}) "
              f"— verify.sh 를 `--max {n}` 으로 조여라. 안 조이면 되돌아간다.")
        return 1
    return 0



def prune(apply: bool = False) -> int:
    """raw 에도 norm 에도 **없는** 상태 항목을 뺀다.

    ★ 2026-09-14. `_prep.json` 이 레이크를 안 따라간다. `eais_bldg_ledger`
      가 2026-09-07 에 후속(`eais_bldgledger_dm`)에 자리를 내줬는데 상태
      파일만 옛 항목을 붙들고 있었고, `--check` 가 그것을 `누락` 으로 울었다.

    ★ **둘 다 없을 때만** 뺀다. 하나라도 있으면 그것은 `--apply` 대상이지
      제거 대상이 아니다 — 실물이 있는데 기록을 지우면 계보가 끊긴다.

    ★ 지우기 전에 무엇을 왜 지우는지 낸다. 근거를 찾고 지우는 것과
      지울 만해 보여서 지우는 것은 다르다.
    """
    # ★ 레이크가 안 붙었으면 **전부** 없어 보인다. 그대로 지우면 상태
    #   파일이 통째로 날아간다. `lakecheck` 와 같은 방침이다 —
    #   못 쟀는데 깨끗하다고 하면 안 되고, 못 쟀는데 지우면 더 안 된다.
    if not RAW.is_dir() or not any(RAW.iterdir()):
        print("✗ raw 가 없거나 비었다 — 레이크가 안 붙었다. 아무것도 안 뺀다.")
        print("  ★ 0건이 아니라 실패다. 못 잰 것과 없는 것은 다르다.")
        return 1
    st = _load_state()
    gone = [rel for rel, rec in st["files"].items()
            if not (RAW / rel).exists() and not (NORM / rec.get("dst", rel)).exists()]
    for rel in gone:
        print(f"  제거  {rel}   raw·norm 둘 다 없다")
    if not gone:
        print("  뺄 것이 없다.")
        return 0
    # ★ 절반을 넘게 지우려 하면 그것은 정리가 아니라 사고다.
    #   레이크가 다른 곳을 가리키거나 절반만 붙은 상태일 수 있다.
    if len(gone) * 2 > len(st["files"]):
        print(f"\n✗ {len(st['files'])}건 중 {len(gone)}건을 빼려 한다. 너무 많다.")
        print("  ★ 레이크가 다른 곳을 가리키거나 반만 붙었을 수 있다.")
        print("    `lakecheck` 로 먼저 보고, 정말 맞으면 손으로 지워라.")
        return 1
    if not apply:
        print(f"\n{len(gone)}건. `--prune --apply` 로 뺀다.")
        return 0
    for rel in gone:
        st["files"].pop(rel, None)
    st["at"] = datetime.now(KST).isoformat(timespec="seconds")
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"\n{len(gone)}건을 뺐다 \u2192 {STATE}")
    return 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="raw·norm 둘 다 없는 상태 항목을 뺀다")
    ap.add_argument("--max", type=int, default=None,
                    help="허용 상한. \u2605 지금 값에서 시작해 내린다")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.prune:
        return prune(apply=a.apply)
    return (check(a.max) if a.check
            else run(apply=a.apply))


if __name__ == "__main__":
    sys.exit(main())
