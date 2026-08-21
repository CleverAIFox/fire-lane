#!/usr/bin/env bash
# doc-update.sh — 4축 문서를 이번 PR 에 맞춘다
#
#   저장소 루트에서:  bash doc-update.sh
#
# ── 원칙 (DECISIONS 2026-08-18 "전면 개편은 하지 않는다") ──
#   MASTER 3,241줄을 한 번에 갈면 docnum_check 앵커와
#   test_reproducibility 문자열 매칭이 전부 깨진다.
#   손대는 절만 고친다.
#
# ── 확정된 수치 (2026-08-21 산출물 기준) ───────────────────
#   sources.yaml 대장      27종  (OK 23 · SKIP 4: spotaddr_geom/ref · dem_public · ortho)
#   data/processed gpkg    24개
#   계약 테스트            19
#   web/data               28.6MB (ortho z19 포함)
#   구간                   1,101
#
# 각 편집은 앵커를 확인하고, 없으면 그 항목만 건너뛰고 보고한다.
set -uo pipefail
[ -d .git ] || { echo "저장소 루트에서 실행할 것"; exit 1; }

python3 - <<'PATCH'
import sys
from pathlib import Path

done, skip, fail = [], [], []


def edit(path, label, old, new, count=1):
    p = Path(path)
    if not p.exists():
        fail.append(f"{path} 없음")
        return
    s = p.read_text(encoding="utf-8")
    if new.strip() and new.split("\n")[0].strip() in s and old not in s:
        skip.append(f"{path}  {label}")
        return
    if old not in s:
        fail.append(f"{path}  {label}  — 앵커 없음: {old.strip()[:60]!r}")
        return
    n = s.count(old)
    if n != count:
        fail.append(f"{path}  {label}  — 앵커가 {n}번 (기대 {count})")
        return
    p.write_text(s.replace(old, new, count), encoding="utf-8")
    done.append(f"{path}  {label}")


# ══════════════════════════════════════════════════════════
# README
# ══════════════════════════════════════════════════════════

edit("README.md", "실행 경로 — 머신 의존 값을 없앤다",
     'export FIRE_LANE_DATA="/mnt/ssd/인공_지능_사관학교/파이널_프로젝트_Fire_Lane/fire-lane-data"',
     'export FIRE_LANE_DATA="<raw 상위 폴더 경로>"   # 머신마다 다르다')

edit("README.md", "계약 테스트 종수 20 → 19",
     "  test_contract.py        GIS ↔ UI 경계 20종",
     "  test_contract.py        GIS ↔ UI 경계 19종")

# ══════════════════════════════════════════════════════════
# MASTER §5 — 시스템 구성. 신규 모듈 등재 + 수치 정정
# ══════════════════════════════════════════════════════════

edit("docs/MASTER.md", "§5 파이프라인 도식 — 신규 모듈 등재",
     """data/processed/    20종 · EPSG:5186(계산) / 4326(표출)
  ↓ src/etl/segments.py          조립부 429줄. 계산은 seg/ 가 한다
      seg/params.py                임계값 정본 (web/config.js 는 표시용 사본)
      seg/graph.py                 노딩 · 최대성분 · 접근 회랑
      seg/width.py                 폭 산출 — ngii1k 1014 · silpok 84 를 만든다
      seg/geom.py                  verdict · _seal · _join · _dirv (순수 함수)
      seg/roadname.py              노딩으로 끊긴 도로명 되붙이기
      seg/report.py                소방서 대조 · 진단 · 산출물 기록
  ↓ src/etl/publish_web.py       표출용 경량 사본
web/data/          12MB · UI 입력 · git 포함 (지형·정사영상 타일 포함)
  ↓ web/index.html               MapLibre 5 + deck.gl 9 (interleaved) + V-World
GitHub Pages       gis 브랜치 푸시 시 자동 배포""",
     """data/processed/    대장 27종(OK 23 · SKIP 4) · gpkg 24개
                   EPSG:5186(계산) / 4326(표출)
  ↓ src/etl/segments.py          조립부. 계산은 seg/ 가 한다
      seg/params.py                임계값 정본 (web/config.js 는 표시용 사본)
      seg/graph.py                 노딩 · 최대성분 · 접근 회랑
      seg/width.py                 폭 산출 — ngii1k 1014 · silpok 84 를 만든다
      seg/geom.py                  verdict · _seal · _join · _dirv (순수 함수)
      seg/roadname.py              노딩으로 끊긴 도로명 되붙이기
      seg/basisno.py               기초구간 → seg_label (도로명주소 기초번호)
      seg/report.py                소방서 대조 · 진단 · 산출물 기록
  ↓ src/etl/publish_web.py       표출용 경량 사본
web/data/          28.6MB · UI 입력 · git 포함 (지형·정사영상 타일 포함)
  ↓ web/index.html               MapLibre 5 + deck.gl 9 (interleaved) + V-World
GitHub Pages       main 브랜치 푸시 시 자동 배포

src/etl/quiet_gdal.py            GDAL 잡음 억제. rasterio 보다 먼저 import
tools/encoding_check.py          인코딩·개행 검사 (CI 게이트)
tools/web_manifest.py            web/data 계보 지문""")

edit("docs/MASTER.md", "§5 계약 — 테스트 개수",
     "`tests/test_contract.py` 20종 + 방어·위생 130종이 CI에서 검증한다.",
     "`tests/test_contract.py` 19종 + 방어·위생 171종이 CI에서 검증한다.")

edit("docs/MASTER.md", "§6 확보 종수",
     "### 확보 (21종)",
     "### 확보 (27종 · 2026-08-21 `road_intrvl` 추가)")

# ── FIRE_LANE_RAW 는 폐기된 레거시다 ──────────────────────
edit("docs/MASTER.md", "§6-2 FIRE_LANE_RAW 폐기 명시",
     """```bash
export FIRE_LANE_RAW="/mnt/f/.../FIRE_LANE/data/raw"     # 리눅스
setx FIRE_LANE_RAW "D:\\...\\FIRE_LANE\\data\\raw"        # 윈도우
```

미설정 시 `<repo>/data/raw` 를 쓴다. 단일 머신이면 그걸로 충분하다.""",
     """```bash
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"      # 리눅스
setx FIRE_LANE_DATA "<raw 상위 폴더 경로>"       # 윈도우
```

미설정 시 `<repo>/data/raw` 를 쓴다. 단일 머신이면 그걸로 충분하다.

> **★ `FIRE_LANE_RAW` 는 폐기됐다(2026-08-21).** `paths.py` 가 이 변수를
> 레거시로 처리하며, 설정돼 있으면 `FIRE_LANE_DATA` 를 덮어써 기계 간
> 산출물이 갈린다. 실행 시 경고가 나온다. 셸 프로필에 남아 있으면 지울 것.""")

edit("docs/MASTER.md", "§14-3 raw 위치",
     """### 14-3. raw 위치

```bash
export FIRE_LANE_RAW="/mnt/f/.../FIRE_LANE/data/raw"
```""",
     """### 14-3. raw 위치

```bash
export FIRE_LANE_DATA="<raw 상위 폴더 경로>"
```

`FIRE_LANE_RAW` 는 폐기됐다. §6-2 참조.""")

edit("docs/MASTER.md", "§11 실행 예시 종수",
     "uv run python src/etl/ingest.py        # raw → processed (15종)",
     "uv run python src/etl/ingest.py        # ★ 직접 호출 금지. §12 참조")

edit("docs/MASTER.md", "web/data 용량",
     "그래서 `web/data/` 1.2MB는 커밋한다.",
     "그래서 `web/data/` 를 커밋한다. 현재 28.6MB(정사영상 타일 포함)이며\n"
     "CI 가 40MB 상한을 감시한다.")

# ── §11 필드 표 — 미문서화 7개 ────────────────────────────
# ★ cov_ngii1k · cov_ngii · cov_silpok · width_cov · n_sample · merged_n ·
#   merge_why 는 이미 §11 "processed 전용 — 웹으로 안 나갑니다" 절에
#   문서화돼 있다(MASTER 1272~1278). 웹 필드표에 넣으면 docnum_check 가
#   "웹 필드로 적었으나 산출물에 없다"로 잡는다. 건드리지 않는다.

# ══════════════════════════════════════════════════════════
# PLAN — 상태가 바뀐 항목
# ══════════════════════════════════════════════════════════

# PLAN 에 "| 11 |" 로 시작하는 행이 두 곳(남은 일 표 · 별도 표)이라
# 문자열 앵커가 유일하지 않다. '정사영상 미터 단위 정합' 을 포함한 행만 고른다.
def edit_plan_row(label, needle, newline):
    p = Path("docs/PLAN.md")
    lines = p.read_text(encoding="utf-8").split("\n")
    hits = [i for i, ln in enumerate(lines)
            if ln.startswith("| 11 |") and needle in ln]
    if not hits:
        if any(newline[:40] in ln for ln in lines):
            skip.append(f"docs/PLAN.md  {label}")
        else:
            fail.append(f"docs/PLAN.md  {label} — 행을 못 찾았다")
        return
    if len(hits) != 1:
        fail.append(f"docs/PLAN.md  {label} — 후보 {len(hits)}행")
        return
    lines[hits[0]] = newline
    p.write_text("\n".join(lines), encoding="utf-8")
    done.append(f"docs/PLAN.md  {label}")


edit_plan_row(
    "#11 정사영상 — 사이드카 XML 발견 반영",
    "정사영상 미터 단위 정합",
    "| 11 | 정사영상 미터 단위 정합 미검증 | \U0001f7e1 | TIF 에 경계좌표 없음. "
    "도엽 bbox(5179→5186) + 사방 균등 pad **가정**. 조대 정합만 확인"
    "(중심선 94.5 vs 30m 옆 110.0). "
    "★ 사이드카 `.xml`(2,428B · UTF-8)은 존재하며 국토지리정보원 메타를 담는다. "
    "GDAL 이 이것을 읽다 cp949 오류를 내어 08-21 에 "
    "`GDAL_DISABLE_READDIR_ON_OPEN=EMPTY_DIR` 로 차단했다. 정합에 사이드카 좌표가 "
    "필요해지면 이 옵션을 빼고 `norm` 계층 심링크(#18)로 가야 한다 |")

edit("docs/PLAN.md", "#12 ortho z19 — 판단 확정",
     "| 12 | `web/data/ortho` z19 1,423장 커밋 | 🟡 | 29MB. CI 상한 60MB. 생성물인데 저장소에 있다 |",
     "| 12 | `web/data/ortho` z19 1,423장 커밋 | 📄 | **유지로 확정(2026-08-21).** "
     "3m 골목이 z18 에서 6px · z19 에서 12px 이라 `desk_check.py` 의 정사영상 대조(#11)가 "
     "z19 를 필요로 한다. 28.6MB · CI 상한 60→40MB 로 조정 |")

edit("docs/PLAN.md", "#14 도로명 미부여 — seg_label 로 해소",
     "| 14 | 도로명 미부여 5구간(77m) | 🟡 | 그중 3곳이 폭 1.0~1.5m. UI 머리글 폴백 규칙이 없다 |",
     "| 14 | 도로명 미부여 5구간(77m) | 📄 | **폴백 규칙 확정(2026-08-21).** "
     "`seg_label` 이 기초구간을 못 찾으면 도로명만 주고, 도로명도 없으면 `null` 이다. "
     "없는 번호를 지어내지 않는다. 그중 3곳이 폭 1.0~1.5m 인 것은 그대로 |")

# ── PLAN 남은 일에 신규 3건 ───────────────────────────────
edit("docs/PLAN.md", "남은 일 — 신규 3건",
     "| 15 | `desk_check` · `wmax_audit` 테스트 없음 | 🟡 | 좌표 변환이 틀려도 아무도 모른다 |",
     "| 15 | `desk_check` · `wmax_audit` 테스트 없음 | 🟡 | 좌표 변환이 틀려도 아무도 모른다 |\n"
     "| 16 | `turn_restriction` 건수 게이트 | 🔴 | 좌표 없는 DBF(전국 44,125행)라 `node_point` 로만 "
     "걸러진다. `node_point` 가 FAIL 이면 필터가 사라지는데 status 는 OK 다. 87 → 44,125(507배)가 "
     "조용히 통과한다. 08-21 에 1회 발생 |\n"
     "| 17 | 단계 스크립트 직접 호출 방지 | 🟡 | `ingest.py` 를 직접 부르면 `_manifest.json` 은 "
     "갱신되나 계보 기록은 안 된다. 다음 `pipeline` 실행이 교착한다. `__main__` 경고 또는 계보 기록 통일 |\n"
     "| 18 | `norm` 계층 미구현 | 🟡 | §5 는 `norm` 을 \"파일명·인코딩·확장자만 통일\" 로 정의했으나 "
     "실제로는 비어 있다. BOM · cp949 사이드카 · CRLF 가 각 소비 지점에서 개별로 처리되고 있다 |\n"
     "| 19 | `ingest` 메모리 반납 | 🟡 | WSL2 5GB 에서 전량 실행이 OOM(`Errno 12`). 실패 지점이 "
     "매 실행 달라진다. `--only` 분할로 우회 가능. `build()` 내부 정리 필요 |")

if fail:
    print("\033[31m실패\033[0m")
    for f in fail:
        print("  ✗ " + f)
for d in done:
    print("  ✓ " + d)
for s_ in skip:
    print("  · " + s_ + " — 이미 적용됨")
if fail:
    sys.exit(1)
PATCH

echo
echo "── 검증"
uv run python tools/docnum_check.py
echo
uv run python -m pytest tests/test_reproducibility.py -q 2>&1 | tail -3
echo
uv run python tools/encoding_check.py

cat <<'NEXT'

── 남은 것 (수동)

  1. DECISIONS.md append — doc-decisions.md 내용을 파일 끝에 붙인다
  2. README 상단에 MASTER §3 발견 5개 요약
  3. README:235 의 641/1,266 은 이력 서술이다. <!--stale-ok--> 확인만

  전부 끝나면:
    git add -A
    git commit -m "docs: 4축 문서를 이번 변경에 맞춘다"
    git push
NEXT
