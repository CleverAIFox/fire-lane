#!/usr/bin/env python3
"""
fixture_recut.py — 커밋된 **사본 픽스처**를 산출물에서 다시 뗀다.  (§258 · PLAN #135)

    uv run python tools/fixture_recut.py                 대조만 (기본 · 쓰지 않는다)
    uv run python tools/fixture_recut.py --check         같다
    uv run python tools/fixture_recut.py --write         다시 뗀다
    uv run python tools/fixture_recut.py --selftest      ★ 판별식이 살아 있나

★ 왜 생겼나 (2026-09-25). `tests/fixtures/dongmyeong_boundary.geojson` 은
  `data/processed/boundary_emd.geojson` 에서 **손으로** 뗀 한 장이다. 원본은
  `.gitignore` 라 CI 클론에 없고, 사본이 없으면 범위 시험 다섯이 통째로 안
  돈다(§238). 그래서 사본을 둔다 — **대가는 조용히 낡는 것**이고, 그 낡음을
  `test_committed_boundary_matches_the_pipeline` 이 든다.

  2026-09-25 전수 verify 에서 그 시험이 처음 울었다. 원인은 이 배치가 봉인지를
  찢어 **ingest 를 전량 다시 돌렸다**는 것이다 — 종전 실행은 샤드 봉인으로 거의
  다 `SKIP` 이었고, 그래서 사본이 9월 19일판 산출물에 맞춰진 채 엿새를 갔다.
  전량 재빌드가 그것을 드러냈다.

  그런데 「다시 떼라」는 안내만 있고 **떼는 도구가 없었다.** 손으로 떼면 어느
  피처를 어떤 정밀도로 떼는지가 매번 사람 손에 달리고, 그것이 사본을 두는 값을
  다시 올린다. 그래서 여기 둔다.

★ **진단을 같이 낸다** — 꼭짓점 최대 이동거리 · 갈린 좌표의 실제 값 · 면적 변화.
  1mm 넘게 움직였으면 판이 바뀐 것이고 다시 뜨면 된다. **1mm 미만이면 이 수치로
  단정하지 않는다** — 같은 기계에서 두 번 돌려야 「재현 불가」와 「다른 스택」이
  갈린다. 그 명령을 진단이 같이 낸다(§258-14).

★ 자동으로 안 쓴다. 관문에 `--write` 를 넣으면 갈린 사본이 **조용히** 맞춰지고,
  사본을 두는 값이 0 이 된다. 관문은 `--check` 만 보고, 쓰는 것은 사람이 시킨다.

IN    data/processed/boundary_emd.geojson  (레이크 기계에만 있다)
OUT   tests/fixtures/dongmyeong_boundary.geojson   (`--write` 일 때만)
PARAM CUTS
밖    **직렬화 형식은 안 본다** — 들여쓰기·키 순서가 달라도 의미가 같으면 같다.
      쓰는 쪽이 파싱해서 비교하므로 그 기준을 따른다. 사본이 **참인가**도 안 본다 — 원본이 맞다고 가정하고 그것에 맞춘다.
      원본의 참은 파이프라인 계약 시험과 `golden` 이 든다. 그리고 여기서 뗀
      사본을 **쓰는 쪽의 규칙**(범위 판정)도 안 본다 — `tests/test_dest_scope.py`
      소관이다.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

# ★ 읍면동 코드를 손으로 박지 않는다. 판정 정본이 `firelane.seg.params.EMD_CD`
#   하나고, 여기서 또 쓰면 **한쪽만 움직인다**(R3). `params` 는 아무것도
#   import 하지 않으므로 도구가 들어도 무겁지 않다(§252).
from firelane.seg.params import EMD_CD

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Cut:
    """사본 한 장. `pick` 은 원본 피처 목록에서 **뗄 것만** 고른다."""
    name: str
    src: str
    dst: str
    key: str                  # 고르는 속성 이름
    value: str                # 그 값


#: ★ 표로 둔다. 다음 사본이 생기면 줄 하나를 더하고, 도구를 또 만들지 않는다.
CUTS: tuple[Cut, ...] = (
    Cut("동명동 경계",
        "data/processed/boundary_emd.geojson",
        "tests/fixtures/dongmyeong_boundary.geojson",
        "EMD_CD", EMD_CD),
)


def _feats(doc: dict, cut: Cut) -> list:
    return [f for f in doc.get("features", [])
            if str((f.get("properties") or {}).get(cut.key, "")) == cut.value]


def _coords(geom) -> list[tuple[float, float]]:
    """어떤 기하든 꼭짓점을 평평하게 낸다. shapely 를 안 쓴다 — 이 도구는
    관문 어디서나 돌아야 하고 지오 스택은 무거우며 없을 수도 있다."""
    out: list[tuple[float, float]] = []

    def walk(x) -> None:
        if (isinstance(x, list) and len(x) >= 2
                and all(isinstance(v, (int, float)) for v in x[:2])):
            out.append((float(x[0]), float(x[1])))
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk((geom or {}).get("coordinates"))
    return out


def _ring_area(pts: list[tuple[float, float]]) -> float:
    """신발끈 공식. 단위는 도(degree)의 제곱이라 **비교용**으로만 쓴다."""
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def diagnose(old: dict, new: dict, cut: Cut) -> list[str]:
    """갈린 원인을 가르는 **수치**. 판정은 안 한다.

    ★ 2026-09-26 정정 (§258-14). 처음 판은 「1mm 미만이면 ㉠ 재현 불가」라고
      **단정했다.** 실기에서 최대 이동 0.0000 m · 면적 0.000000% 가 나왔는데
      그 한 줄이 「ingest 가 재현 불가다」라고 말했다 — 그것은 셋 중 하나일 뿐이다:

        ㉮ 같은 기계에서 두 번 돌려도 갈린다        → 진짜 재현 불가. 심각하다
        ㉯ 기계가 다르다(GDAL·PROJ 판이 다르다)      → 재투영 말미. 사본을 다시 뜬다
        ㉰ 값은 같고 **표기**만 다르다               → 사본을 다시 뜨면 끝이다

      **수치 하나로는 셋을 못 가른다.** 가르는 것은 「같은 기계에서 두 번」이고
      그것은 사람이 명령 하나로 한다. 그래서 이 함수는 수치와 그 명령만 낸다.
      단정하는 진단은 틀린 처방을 부른다 — 사본을 다시 뜨면 될 일에
      「ingest 재현성을 봐라」로 사람을 보냈다.
    """
    a, b = _feats(old, cut), _feats(new, cut)
    if len(a) != 1 or len(b) != 1:
        return [f"고른 피처가 {len(a)} · {len(b)} 개다 — 1개여야 한다 "
                f"({cut.key}={cut.value})"]
    pa, pb = _coords(a[0]["geometry"]), _coords(b[0]["geometry"])
    lines = [f"  꼭짓점 {len(pa)} → {len(pb)}"]
    if a[0]["properties"] != b[0]["properties"]:
        keys = {k for k in set(a[0]["properties"]) | set(b[0]["properties"])
                if a[0]["properties"].get(k) != b[0]["properties"].get(k)}
        lines.append(f"  속성이 갈렸다: {sorted(keys)}")
    if len(pa) == len(pb) and pa:
        # 같은 순서를 가정한다 — ingest 가 순서를 바꾸면 꼭짓점 수가 같아도
        # 이 값이 커진다. 그 경우도 「재현 불가」쪽 신호라 결론이 안 바뀐다.
        d = [(((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5, i)
             for i, ((x1, y1), (x2, y2)) in enumerate(zip(pa, pb, strict=True))]
        far, idx = max(d)
        m = far * 111_000          # 도 → m, 위도 기준 대략치
        lines.append(f"  꼭짓점 최대 이동 {m:.6f} m  (#{idx})")
        if far:
            # ★ 값 자체를 보여준다. 「0.0000 m」 만으로는 표기 차이인지 안 보인다.
            lines.append(f"    사본 {pa[idx][0]!r}, {pa[idx][1]!r}")
            lines.append(f"    산출 {pb[idx][0]!r}, {pb[idx][1]!r}")
        if m < 0.001:
            lines.append("  → **1mm 미만이다.** 판정을 움직일 수 없는 크기다.")
            lines.append("    원인 셋을 이 수치로는 못 가른다 — 같은 기계에서 두 번 돌려 가른다:")
            lines.append("      uv run fire-lane --only ingest && "
                         "cp data/processed/boundary_emd.geojson /tmp/a.geojson")
            lines.append("      uv run fire-lane --only ingest --rebuild && "
                         "cmp /tmp/a.geojson data/processed/boundary_emd.geojson")
            lines.append("    같으면 이 기계에서는 재현된다 → 사본이 **다른 스택에서**")
            lines.append("    떠진 것이다. `--write` 로 이 기계 기준으로 다시 뜬다.")
            lines.append("    다르면 ingest 가 재현 불가다 — 거기서 멈추고 그것을 먼저 본다.")
        else:
            lines.append("  → 판이 바뀌었다. `--write` 로 다시 뜨면 된다")
    else:
        lines.append("  꼭짓점 수가 달라졌다 → 판이 바뀌었다. `--write` 로 다시 뜬다")
    if pa and pb:
        aa, ab = _ring_area(pa), _ring_area(pb)
        if aa:
            lines.append(f"  면적 변화 {100 * (ab - aa) / aa:+.6f}%")
    return lines


def run(write: bool) -> int:
    rc, missing = 0, 0
    for cut in CUTS:
        src, dst = ROOT / cut.src, ROOT / cut.dst
        if not src.is_file():
            print(f"  [건너뜀] {cut.name} — {cut.src} 이 없다 (레이크 기계에서만 잰다)")
            missing += 1
            continue
        new = json.loads(src.read_text(encoding="utf-8"))
        picked = _feats(new, cut)
        if len(picked) != 1:
            print(f"  ✗ {cut.name} — 원본에서 {cut.key}={cut.value} 가 {len(picked)}건이다")
            rc = 1
            continue
        doc = {"type": "FeatureCollection", "features": picked}
        body = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
        old_txt = dst.read_text(encoding="utf-8") if dst.is_file() else ""
        # ★ 2026-09-25. **의미로 비교한다.** 처음 판은 바이트로 비교해서
        #   들여쓰기 한 칸 차이에 「사본이 갈렸다」고 했다 — 내 기계에서 기하가
        #   완전히 같은데(최대 이동 0.0000m · 면적 0.000000%) 빨간불이 떴다.
        #   쓰는 쪽(`test_dest_scope`)이 파싱해서 비교하므로 판정 기준을 맞춘다.
        #   형식만 다르면 **건드리지 않는다** — 무의미한 diff 를 만들지 않는다.
        same = False
        if old_txt:
            try:
                same = _feats(json.loads(old_txt), cut) == picked
            except json.JSONDecodeError:
                same = False
        if same:
            print(f"  ✓ {cut.name} — 사본이 원본과 같다 (의미 기준)")
            continue
        print(f"  ✗ {cut.name} — 사본이 원본과 다르다")
        if old_txt:
            for ln in diagnose(json.loads(old_txt), new, cut):
                print(ln)
        if write:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(body, encoding="utf-8")
            print(f"    → 다시 뗐다 {cut.dst}")
            print("    ★ 그냥 커밋하지 마라. 위 진단이 ㉠ 이면 원인이 ingest 다.")
        else:
            rc = 1
            print(f"    다시 뜨려면:  uv run python {Path(__file__).relative_to(ROOT)} --write")
    if missing == len(CUTS):
        print("  ★ 전부 건너뛰었다 — 이 기계에는 원본이 없다. 레이크 기계에서 돌려라.")
    return rc


def selftest() -> int:
    """판별식이 **빈 그물이 아닌가.** 합성 문서로 잰다."""
    cut = CUTS[0]
    base = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {cut.key: cut.value, "NM": "동명동"},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[126.9, 35.1], [126.9, 35.2],
                                       [127.0, 35.2], [126.9, 35.1]]]}},
        {"type": "Feature", "properties": {cut.key: "99999999"},
         "geometry": {"type": "Point", "coordinates": [0, 0]}},
    ]}
    bad = []
    if len(_feats(base, cut)) != 1:
        bad.append("고르기가 다른 읍면동을 같이 집는다")
    if len(_coords(base["features"][0]["geometry"])) != 4:
        bad.append("꼭짓점 평탄화가 틀렸다")

    import copy

    # ㉠ 1mm 미만 흔들림 → 재현 불가로 읽어야 한다
    jitter = copy.deepcopy(base)
    jitter["features"][0]["geometry"]["coordinates"][0][0][0] += 1e-9
    # ㉠ 1mm 미만 → **단정하지 않는다.** 두 번 돌리라는 명령을 낸다
    tiny = diagnose(base, jitter, cut)
    if not any("1mm 미만" in ln for ln in tiny):
        bad.append("1mm 미만을 그렇게 안 읽는다")
    if any("재현 불가다" in ln and "→" in ln for ln in tiny):
        bad.append("1mm 미만인데 재현 불가로 **단정한다** — 수치로는 못 가른다")
    if not any("두 번 돌려" in ln for ln in tiny):
        bad.append("가르는 명령을 안 낸다")
    # ㉡ 실제 모양 변경 → 판 변경으로 읽어야 한다
    moved = copy.deepcopy(base)
    moved["features"][0]["geometry"]["coordinates"][0][0][0] += 1e-4
    if not any("판이 바뀌었다" in ln for ln in diagnose(base, moved, cut)):
        bad.append("모양 변경을 「판 변경」으로 읽지 않는다")
    # 속성만 갈린 것도 잡아야 한다
    prop = copy.deepcopy(base)
    prop["features"][0]["properties"]["NM"] = "딴동"
    if not any("속성이 갈렸다" in ln for ln in diagnose(base, prop, cut)):
        bad.append("속성 차이를 안 본다")
    # 같은 것을 다르다고 하지 않는다
    if any("갈렸다" in ln for ln in diagnose(base, copy.deepcopy(base), cut)):
        bad.append("같은 문서를 다르다고 한다")

    if bad:
        print("selftest 빨강")
        for b in bad:
            print(f"  ✗ {b}")
        return 1
    print("selftest 초록")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="커밋된 사본 픽스처를 산출물에서 다시 뗀다")
    ap.add_argument("--check", action="store_true", help="대조만 한다 (기본)")
    ap.add_argument("--write", action="store_true", help="사본을 다시 뗀다")
    ap.add_argument("--selftest", action="store_true", help="판별식 자기검사")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    return run(write=a.write)


if __name__ == "__main__":
    sys.exit(main())
