#!/usr/bin/env python3
"""
b2_ingest.py — B2 **종결.** 파이프라인 FAIL 3종을 닫는다.

    uv run python tools/b2_ingest.py            무엇을 할지만
    uv run python tools/b2_ingest.py --apply    실제로

★ 원인은 `kind` 가 아니라 **`layer` 키를 오용한 것**이었다.

      ingest.py:283   _want = e["layer"]        ← zip 안에서 읽을 **SHP 이름**
      내가 쓴 값       layer: raw                ← 계층 이름으로 착각

  그래서 `raw` 로 시작하는 SHP 를 찾다 없어서 죽었다. 에러 메시지의
  "raw 계열 shp 가 없다" 가 그 뜻이었는데 **화면에 안 나와서** 못 봤다.
  `vector` → `shp_zip_multi` → `raw_only` 로 **세 번 추측했다.**

★ 그리고 `shp_zip_multi` 도 안 맞는다. 그것은 "도엽 여러 zip 을 병합" 이라
  같은 성격을 합치는 종류다. 승인분은 **한 zip 에 성격이 다른 레이어가
  여럿**이다 —

      juso_bldg_geom     건물 폴리곤 · 출입구 점 · 접속선      3벌
      juso_bldggrp_geom  동 도형 · 동 출입구                  2벌
      juso_etc_geom      터널 · 고가 · 교량 · 공원 · 하천 …    21벌

  한 항목이 한 레이어를 지목하는 구조라 지금 대장으로는 표현이 안 된다.
  나눠 등재하거나 새 kind 를 만들어야 하는데 **둘 다 지금 할 일이 아니다.**
  `feeds: []` 와 `feeds_why`("아직 배선하지 않았다. B4 에서 정한다")가 이미
  그렇게 적혀 있었다 — `kind` 만 그 선언과 안 맞았다.

닫는 것 셋 —

  ㊸ juso 3종 → raw_only      "읽지 않는다. 존재만 기록한다"
  ㊹ layer 오용 제거 · note    나눠 등재할 때 쓸 레이어 목록을 남긴다
  ㊺ ingest 가 사유를 화면에   ★ 이 사고의 진짜 교훈이다
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"


def keyset(t: str) -> set[str]:
    d = yaml.safe_load(t) or {}
    out: set[str] = set()
    for b, it in d.items():
        out.add(b)
        if isinstance(it, dict):
            for k, v in it.items():
                out.add(f"{b}.{k}")
                if isinstance(v, dict):
                    out |= {f"{b}.{k}.{f}" for f in v}
    return out


def edit(p: Path, old: str, new: str, why: str, apply: bool) -> int:
    if not p.exists():
        print(f"  ✗ {p} 없음")
        return 1
    s = p.read_text(encoding="utf-8")
    n = s.count(old)
    if n == 0:
        print(f"  = {why} (이미 적용)")
        return 0
    if n > 1:
        print(f"  ✗ {why} — {n}건. 모호하면 안 바꾼다")
        return 1
    out = s.replace(old, new, 1)
    if p.suffix == ".py":
        import ast
        try:
            ast.parse(out)
        except SyntaxError as e:
            print(f"  ✗ {why} — 구문 오류 {e.lineno}행")
            return 1
    if p.name == "sources.yaml":
        lost = keyset(s) - keyset(out)
        # ★ layer 는 **의도한 제거**다. 그것만 허용한다.
        if lost - {f"datasets.{k}.layer" for k in
                   ("juso_bldg_geom", "juso_bldggrp_geom", "juso_etc_geom")}:
            print(f"  ✗ {why} — 의도 밖 키 손실 {sorted(lost)[:4]}")
            return 1
    print(f"  {'→' if apply else '·'} {why}")
    if apply:
        p.write_text(out, encoding="utf-8")
    return 0


LAYERS = {
    "juso_bldg_geom": (
        "      TL_SGCO_RNADR_MST   건물 폴리곤        15,518\n"
        "      TL_SPBD_ENTRC       건물 출입구 점     17,069\n"
        "      TL_SPOT_CNTC        건물↔도로 접속선   15,518 "
        "(CNT_DST_LN 중앙 7.6m · 최대 402.5m)"),
    "juso_bldggrp_geom": (
        "      TL_SGCO_RNADR_DONG  건물군 내 동 도형   8,221\n"
        "      TL_SPBD_ENTRC_DONG  동 출입구 점          939"),
    "juso_etc_geom": (
        "      TL_SPOT_TUNNEL      터널 10 (지산·산수·지원·소태)\n"
        "      TL_SPOT_OVERPASS    고가  4 (너릿재로·제2순환로)\n"
        "      TL_SPOT_BRIDGE      교량 36 · 공원 34 · 하천 27\n"
        "      TL_SPOT_SUBWAY*     지하철역 6 · 출입구 26"),
}

NOTE_ADD = """    read_note: |
      ★ 2026-09-10. `kind: raw_only` 인 이유 — **한 zip 에 성격이 다른
        레이어가 여럿**이다. ingest 의 shp 계열은 `layer` 키로 zip 안
        SHP 하나를 지목하는데(ingest.py:283), 이 자산은 하나로 못 고른다.
        합치면 폴리곤과 점과 선이 한 GeoDataFrame 에 섞인다.

        읽으려면 레이어별로 항목을 나누거나 새 kind 를 만들어야 한다.
        그 판단은 판정 규칙 변경이라 B4 소관이다. 지금은 존재만 기록한다.

        zip 안 레이어 —
{layers}
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    A = a.apply
    if A:
        b = LEDGER.with_suffix(".yaml.b2ingest")
        if not b.exists():
            shutil.copy2(LEDGER, b)
    print(f"{'적용' if A else 'dry-run — --apply 로 실행'}\n")
    f = 0

    print("── ㊸㊹ juso 3종 → raw_only · layer 오용 제거")
    for k, lay in LAYERS.items():
        f += edit(LEDGER,
                  f"  {k}:\n    stem: {k}\n    ext: [zip]\n"
                  f"    kind: shp_zip_multi\n    layer: raw\n",
                  f"  {k}:\n    stem: {k}\n    ext: [zip]\n"
                  f"    kind: raw_only\n"
                  + NOTE_ADD.format(layers=lay),
                  f"{k} — raw_only · layer 제거 · 레이어 목록", A)

    print("\n── ㊺ ingest 가 실패 사유를 화면에")
    # ★ 이 사고의 진짜 교훈이다. `[FAIL]` 만 찍고 `error` 는 매니페스트에만
    #   있었다. 그래서 사유를 못 보고 세 번 추측했다. 한 줄이면 첫 번에 끝났다.
    #   같은 파일 339-340 이 이미 적어놨다 — "_manifest.json 에 FAIL 이
    #   적힌 채 파이프라인은 OK 를 찍었다".
    f += edit(ROOT / "src" / "firelane" / "ingest.py",
              '        print(f"[{r.get(\'status\',\'-\'):7}] {key:20} '
              '{r.get(\'features\',\'\'):>8} feat")',
              '        # ★ 2026-09-10. 종전에는 status 와 건수만 찍고 error 는\n'
              '        #   _manifest.json 에만 적었다. 실패 사유를 보려면 JSON 을\n'
              '        #   손으로 파싱해야 했고, 그 바람에 juso 3종 FAIL 의 원인을\n'
              '        #   **세 번 추측**했다(vector → shp_zip_multi → raw_only).\n'
              '        #   339행이 같은 병을 이미 적어놨다. 화면에 낸다.\n'
              '        _st = r.get("status", "-")\n'
              '        _msg = f"{r.get(\'features\', \'\'):>8} feat"\n'
              '        if _st in ("FAIL", "MISSING") and r.get("error"):\n'
              '            _msg = str(r["error"])[:78]\n'
              '        print(f"[{_st:7}] {key:20} {_msg}")',
              "ingest — FAIL 시 error 를 화면에", A)

    print(f"\n{'실패 ' + str(f) + '건' if f else '전부 통과'}")
    if A and not f:
        print("\n검증 —")
        print("  uv run fire-lane --only ingest")
        print("  uv run pytest tests/ -q")
        print("  bash tools/verify.sh")
        print("\n남는 것 — 둘 다 기존 결함이다")
        print("  · 기한 초과 3건   F-090. PLAN 의 DEFERRED 를 사람이 정한다")
        print("  · 그림 ↔ 정본     F-128. render_figures 후 기획서에 사람이 넣는다")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
