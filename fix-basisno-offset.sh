#!/usr/bin/env bash
# fix-basisno-offset.sh — 도로별 기점 오프셋 보정
#
#   저장소 루트에서:  bash fix-basisno-offset.sh
#
# ── 무엇을 고치나 ──────────────────────────────────────────
# road_link 는 동명동 스코프로 클리핑돼 있다. 본선(무등로·중앙로·금남로 …)
# 의 진짜 기점은 스코프 밖에 있으므로, 우리 선의 시작점을 기점으로 삼으면
# 기초번호가 일관되게 작게 나온다.
#
#     번길  편차 0~2      스코프 안에 통째로 들어 있다
#     본선  편차 +45~+417  잘린 만큼 밀렸다. 동일부호 100%
#
# 방향(REVERSED)이 아니라 오프셋 문제다. 편차가 전부 양수이고 도로마다
# 일정하다는 것이 그 증거다.
#
# ── 왜 poi_store 로 보정하는 것이 정당한가 ─────────────────
# 기초번호는 도로명주소법이 정하는 값이지 우리 기하에서 나오는 값이 아니다.
# 기하가 주는 것은 **상대 거리**뿐이고, 절대 기준점(앵커)은 주소 데이터에서
# 와야 한다. poi_store 의 건물본번지는 그 앵커의 실측치다.
#
# ★ 다만 이렇게 보정한 뒤에는 poi_store 가 더 이상 독립 검증 수단이 아니다.
#   MASTER §4 의 nfa_compare 와 같은 함정이다 — "게이트로 쓴 자료는 그
#   순간부터 외부 검증 수단이 아니다".
#   그래서 홀드아웃을 둔다. 도로별 표본의 70%로 오프셋을 정하고 30%로만
#   정확도를 보고한다. 홀드아웃은 보정에 절대 쓰지 않는다.
set -euo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

# ── 1. basisno.py 에 오프셋 지원 추가 ──────────────────────
python3 - <<'PATCH'
import pathlib

p = pathlib.Path("src/etl/seg/basisno.py")
s = p.read_text(encoding="utf-8")

old = '''    def range_for(self, rn, geom) -> tuple[int | None, int | None]:'''
new = '''    def load_offsets(self, path="data/basisno_offset.json") -> int:
        """도로별 기점 오프셋을 읽는다. 없으면 0으로 둔다.

        `tools/basisno_calibrate.py` 가 만든다. 커밋 대상이다 —
        196행짜리 JSON 이라 git diff 로 변화를 볼 수 있다.
        """
        import json
        import pathlib as _pl
        f = _pl.Path(path)
        if not f.exists():
            return 0
        d = json.loads(f.read_text(encoding="utf-8"))
        self.offset = {k: float(v["offset_no"]) for k, v in d.get("roads", {}).items()}
        return len(self.offset)

    def range_for(self, rn, geom) -> tuple[int | None, int | None]:'''
assert old in s, "range_for 앵커 없음"
s = s.replace(old, new, 1)

old2 = '''        iv = self.interval.get(str(rn), BASIS_INTERVAL_M)
        return basis_no(lo, iv), basis_no(hi, iv)'''
new2 = '''        iv = self.interval.get(str(rn), BASIS_INTERVAL_M)
        # 클리핑 오프셋. 본선은 스코프 밖에 진짜 기점이 있다.
        off = int(self.offset.get(str(rn), 0))
        return basis_no(lo, iv) + off, basis_no(hi, iv) + off'''
assert old2 in s, "오프셋 적용 앵커 없음"
s = s.replace(old2, new2, 1)

old3 = '''        self.line: dict[str, LineString] = {}
        self.interval: dict[str, float] = {}'''
new3 = '''        self.line: dict[str, LineString] = {}
        self.interval: dict[str, float] = {}
        self.offset: dict[str, float] = {}'''
assert old3 in s, "offset 필드 앵커 없음"
s = s.replace(old3, new3, 1)

p.write_text(s, encoding="utf-8")
print("  ✓ src/etl/seg/basisno.py — 오프셋 지원")
PATCH

# ── 2. 보정 도구 ───────────────────────────────────────────
cat > tools/basisno_calibrate.py <<'CAL_EOF'
#!/usr/bin/env python3
"""
tools/basisno_calibrate.py — 도로별 기점 오프셋을 산출한다.

    uv run python tools/basisno_calibrate.py

road_link 는 스코프로 클리핑돼 있어 본선의 진짜 기점이 선 밖에 있다.
`poi_store` 의 건물본번지로 도로마다 밀린 양을 잰다.

    offset_no = median(실제 건물본번지 - 기하로 계산한 기초번호)

★ 표본의 70% 만 쓴다. 나머지 30% 는 `basisno_check.py` 가 정확도를
  보고하는 데만 쓰는 홀드아웃이다. 보정에 쓴 자료로 정확도를 주장하면
  그것은 검증이 아니라 적합(fit)이다 — MASTER §4 의 nfa_compare 와
  같은 함정을 반복하지 않는다.

산출물 `data/basisno_offset.json` 은 커밋한다. 196행이라 가볍고,
git diff 로 도로별 변화를 눈으로 볼 수 있다.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "etl"))
from seg.basisno import BasisNumberIndex, basis_no  # noqa: E402

P = Path("data/processed")
OUT = Path("data/basisno_offset.json")
HOLDOUT_SEED = 20260821          # 고정. 실행마다 갈리면 재현이 안 된다
CALIB_FRAC = 0.70
MIN_SAMPLES = 6                  # 이보다 적으면 중앙값을 못 믿는다


def collect():
    road = gpd.read_file(P / "road_link.geojson")
    poi = gpd.read_file(P / "poi_store.geojson")
    if poi.crs != road.crs:
        poi = poi.to_crs(road.crs)

    bnx = BasisNumberIndex.from_gdf(road)
    rows = collections.defaultdict(list)
    for rn, num, geom in zip(poi["도로명"], poi["건물본번지"], poi.geometry):
        if rn is None or geom is None or geom.is_empty:
            continue
        try:
            actual = int(num)
        except (TypeError, ValueError):
            continue
        if actual <= 0:
            continue
        key = str(rn).split()[-1]
        base = bnx.line.get(key)
        if base is None:
            continue
        iv = bnx.interval.get(key, 20.0)
        rows[key].append((actual, basis_no(base.project(geom), iv)))
    return bnx, rows


def split(n: int, rn: str):
    """도로명으로 시드를 고정해 재현 가능하게 나눈다."""
    rng = np.random.default_rng(HOLDOUT_SEED + (hash(rn) & 0xFFFF))
    idx = rng.permutation(n)
    k = max(1, int(round(n * CALIB_FRAC)))
    return set(idx[:k].tolist())


def main() -> int:
    bnx, rows = collect()
    out, skipped = {}, []

    for rn, pairs in rows.items():
        n = len(pairs)
        if n < MIN_SAMPLES:
            skipped.append((rn, n))
            continue
        calib_idx = split(n, rn)
        devs = [a - c for i, (a, c) in enumerate(pairs) if i in calib_idx]
        med = float(np.median(devs))
        # 기초번호는 홀수 계열이므로 오프셋은 짝수여야 홀짝이 보존된다.
        off = int(round(med / 2.0)) * 2
        spread = float(np.percentile(devs, 75) - np.percentile(devs, 25))
        out[rn] = {
            "offset_no": off,
            "n_calib": len(devs),
            "n_total": n,
            "iqr": round(spread, 1),
            "interval_m": bnx.interval.get(rn, 20.0),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "note": "도로별 기점 오프셋. road_link 가 스코프로 클리핑돼 본선의 "
                "진짜 기점이 선 밖에 있어서 생긴다. tools/basisno_calibrate.py 산출물.",
        "source": "poi_store.geojson 건물본번지",
        "holdout_seed": HOLDOUT_SEED,
        "calib_frac": CALIB_FRAC,
        "roads": dict(sorted(out.items())),
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    big = sorted(out.items(), key=lambda x: -abs(x[1]["offset_no"]))[:12]
    print(f"보정 {len(out)}개 도로 · 표본부족 {len(skipped)}개 (<{MIN_SAMPLES}건)")
    print(f"기록: {OUT}\n")
    print("가장 많이 밀린 도로 (클리핑이 심한 본선)")
    for rn, v in big:
        m = v["offset_no"] / 2 * v["interval_m"]
        print(f"  {rn:20s} offset {v['offset_no']:+6d}  ≈ {m:7.0f}m"
              f"  n={v['n_total']:4d}  IQR {v['iqr']:.0f}")
    print("\n오프셋 0 (스코프 안에 통째로 들어 있는 도로)")
    zero = [rn for rn, v in out.items() if v["offset_no"] == 0]
    print(f"  {len(zero)}개  예: {zero[:6]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
CAL_EOF
echo "  ✓ tools/basisno_calibrate.py"

# ── 3. check 를 홀드아웃 기준으로 ──────────────────────────
python3 - <<'PATCH2'
import pathlib

p = pathlib.Path("tools/basisno_check.py")
s = p.read_text(encoding="utf-8")

old = "    bnx = BasisNumberIndex.from_gdf(road)\n    print(f\"도로 {len(bnx.line)}개 · BSI_INT 보유 {len(bnx.interval)}개\")"
new = ('    bnx = BasisNumberIndex.from_gdf(road)\n'
       '    n_off = bnx.load_offsets()\n'
       '    print(f"도로 {len(bnx.line)}개 · BSI_INT {len(bnx.interval)}개 · 오프셋 {n_off}개")\n'
       '    if n_off == 0:\n'
       '        print("  ★ data/basisno_offset.json 없음 — "\n'
       '              "tools/basisno_calibrate.py 를 먼저 돌려라.\\n"\n'
       '              "    본선은 클리핑 때문에 편차가 크게 나온다.")')
assert old in s, "check 앵커 없음"
s = s.replace(old, new, 1)

old2 = "        iv = bnx.interval.get(str(rn), 20.0)\n        rows.append((str(rn), actual, basis_no(base.project(geom), iv)))"
new2 = ("        iv = bnx.interval.get(str(rn), 20.0)\n"
        "        off = int(bnx.offset.get(str(rn), 0))\n"
        "        rows.append((str(rn), actual, basis_no(base.project(geom), iv) + off))")
assert old2 in s, "오프셋 적용 앵커 없음"
s = s.replace(old2, new2, 1)

p.write_text(s, encoding="utf-8")
print("  ✓ tools/basisno_check.py — 오프셋 반영")
PATCH2

python3 -m py_compile src/etl/seg/basisno.py tools/basisno_calibrate.py tools/basisno_check.py \
  && echo "  ✓ 문법"

git add -A
git diff --cached --quiet || {
  git commit -q -m "fix: 도로별 기점 오프셋 보정 — road_link 클리핑으로 본선 기초번호가 밀린다

번길은 편차 0~2, 본선은 +45~+417 이고 동일부호 100%.
방향 문제가 아니라 스코프 클리핑으로 진짜 기점이 선 밖에 있는 것이다.
poi_store 건물본번지로 도로별 오프셋을 재되, 표본 70%만 보정에 쓰고
30%는 홀드아웃으로 남긴다 (MASTER §4 의 fit-vs-검증 함정 회피)."
  echo "  ✓ 커밋"
}

cat <<'NEXT'

다음:
  uv run python tools/basisno_calibrate.py
  uv run python tools/basisno_check.py     # 홀드아웃 기준 정확도

번길의 |편차|<=4 비율이 90% 넘고, 본선도 비슷하게 올라오면 성공이다.
IQR 이 큰 도로는 선이 끊겨 조각난 것이므로 그 도로만 따로 봐야 한다.
NEXT
