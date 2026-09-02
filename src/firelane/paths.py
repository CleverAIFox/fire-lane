#!/usr/bin/env python3
"""
paths.py — 경로 정본. 모든 ETL 스크립트가 여기를 본다.

★ 심링크를 쓰지 않는다.
  `data/raw` 를 심링크로 걸었더니 git 이 그것을 추적했고,
  exFAT 에서 `git reset --hard` 시 경로 문자열 파일로 체크아웃되면서
  원본 2.5GB 가 소실됐다(2026-08-11). 환경변수는 git 에 아무것도 남기지 않는다.

── 계층 (MASTER §18-1) ───────────────────────────────────────
  landing     외장 SSD fire-lane-data/   다운로드 원본. 규칙 없음
  raw         절대 수정하지 않는다
  norm        파일명·인코딩·확장자만 통일. 값은 안 바꾼다
  field       실측 원자료. ★ 재생성 불가
  quarantine  대장에 없는 파일. 삭제하지 않고 격리
  processed   산출물. 재생성 가능하므로 백업·커밋하지 않는다

설정
    export FIRE_LANE_DATA="/mnt/ssd/.../fire-lane-data"
    (구방식 FIRE_LANE_RAW 도 계속 인식한다)

향후
    S3 로 옮기면 FIRE_LANE_DATA 에 s3:// 를 받도록 확장한다.
    스크립트들이 이 모듈만 보므로 그때 여기만 고치면 된다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── 데이터 레이크 루트 ────────────────────────────────────────
DATA = os.environ.get("FIRE_LANE_DATA")
DATA = Path(DATA).expanduser() if DATA else None

# 원본. 절대 수정하지 않는다.
# ★ FIRE_LANE_RAW 는 2026-08-15 개편으로 폐기됐다. 남아 있는 기계에서
#   FIRE_LANE_DATA 를 **경고 없이 이기고** 있었다. 기계마다 .bashrc 를
#   고치는 것은 해결이 아니다 — 코드가 알아채야 한다. 계속 인식하되
#   충돌하면 시끄럽게 말한다.
_legacy_raw = os.environ.get("FIRE_LANE_RAW")
if _legacy_raw and DATA and Path(_legacy_raw).expanduser() != (DATA / "raw"):
    print(f"★ FIRE_LANE_RAW(폐기) 가 FIRE_LANE_DATA 를 덮고 있다\n"
          f"    FIRE_LANE_RAW   {_legacy_raw}   ← 이 값이 쓰인다\n"
          f"    FIRE_LANE_DATA  {DATA / 'raw'}  ← 무시된다\n"
          f"  기계 간 산출물이 갈리는 원인이다. unset FIRE_LANE_RAW 해라.",
          file=sys.stderr)

RAW = Path(_legacy_raw
           or (DATA / "raw" if DATA else ROOT / "data" / "raw")).expanduser()

# 정규화본. 파일명·인코딩·확장자만 통일한다. 값은 안 바꾼다(MASTER §18-1).
NORM = (DATA / "norm") if DATA else (ROOT / "data" / "norm")

# 다운로드 원본 수집소. 규칙 없음. acquire.py 가 여기서 raw 로 편입한다.
# ★ 2026-08-24. 종전에는 acquire.py 안에 `RAW.parent / "landing"` 로 있었다.
#   계층인데 계층 모듈이 모르면 도구마다 자기 자리를 발명한다.
LANDING = (DATA / "landing") if DATA else (ROOT / "data" / "landing")

# ── 출발지 ────────────────────────────────────────────────────
# 브라우저가 떨구는 곳. **파이프라인의 머리이자 우리가 소유하지 않는 유일한
# 계층**이다. 읽기 전용으로 취급한다 — 사용자의 폴더지 우리 것이 아니다.
#
# ★ 2026-08-26. 처음에 `tools/intake.py` 안에 박아뒀더니 `doctor.py` 가
#   그것을 쓰려고 `sys.path.insert` 를 했고 `test_layering` 에 걸렸다.
#   **경로 정본은 여기다**(모듈 머리말). 도구 안에 두면 다른 도구가
#   자기 자리를 발명하거나 남의 자리를 훔친다 — interim 때와 같은 형태다.
#
# WSL 에서 윈도우 다운로드는 `/mnt/c/Users/<user>/Downloads` 다. 사용자명이
# 기계마다 다르므로 자동탐색하되, **이름으로 거르지 않는다** — `Default User`
# 를 빼먹어 빈 폴더를 출발지로 잡은 적이 있다. 파일이 실제로 있는 곳을 고른다.
def inbox() -> Path:
    env = os.environ.get("FIRE_LANE_INBOX")
    if env:
        return Path(env).expanduser()
    cands = []
    for base in (Path("/mnt/c/Users"), Path("/c/Users")):
        if not base.is_dir():
            continue
        for u in sorted(base.iterdir()):
            d = u / "Downloads"
            try:
                n = sum(1 for x in d.iterdir() if x.is_file())
            except OSError:
                continue
            if n:
                cands.append((n, d))
    if not cands:
        return Path.home() / "Downloads"
    cands.sort(reverse=True)
    return cands[0][1]


# 중간 산출물. 언제든 지워도 재생성된다(MASTER §18-1).
#
# ★ 2026-08-24 신설. 그전까지 이 계층은 **문서에만 있었다.** §18-1 이 여섯
#   계층을 선언하는데 `interim` 은 선언조차 없었고, 그래서 탐색 도구들이
#   갈 곳이 없어 프로젝트 루트에 떨궜다. `jijeok_probe._side()` 가 그것을
#   주석으로 자백하고 있었다 —
#
#       """저장소 밖 작업 위치. 아직 대장에 없는 탐색 산출물이라 여기 둔다."""
#       return RAW.parent.parent
#
#   결과: SSD 루트에 jijeok_*.gpkg 11.7MB + check27/42 가 널렸다.
#   **계층이 없으면 파일은 아무 데나 떨어진다.** 규율의 문제가 아니라
#   구조의 문제다.
#
# ★ processed 와 다르다. processed 는 파이프라인 정본이고 여기는 탐색·
#   대조 산출물이다. 대장에 없고, 커밋하지 않고, 지워도 된다.
# ★ SSD 에 둔다. raw 옆이라야 970MB 지적도 파싱 결과를 다시 안 만든다.
INTERIM = (DATA / "interim") if DATA else (ROOT / "data" / "interim")

# 실측 원자료. ★ 재생성 불가. raw 와 같은 등급으로 보호한다.
# ★ 2026-08-23. FIRE_LANE_DATA 를 타지 않는다. 저장소 안이 정본이다.
#   종전에는 (DATA / "field") 였는데 그것이 문서 셋을 다 어겼다.
#     MASTER §18-1 계층표      field → `data/field/`
#     MASTER §6-2 보관 전략     FIRE_LANE_DATA 는 raw 2.2GB 를 저장소 밖에
#                              두려는 것이다. field 를 옮기려는 것이 아니다
#   야장은 CSV 세 개에 수십 KB 이고, UI 담당·심사위원이 clone 만으로 봐야
#   하는 자료다. web/data 를 git 에 넣는 것과 같은 논리다.
#
#   ★ 이 정의를 쓰는 곳이 한 곳도 없었다. sample_design.py 는 자기 파일에
#     ROOT/"data"/"field" 를 따로 두고 있었고 그쪽이 맞았다. 아무도 안 쓰는
#     정의가 조용히 문서를 어기고 있었던 것이고, 쓰기 시작하는 순간
#     FIRE_LANE_DATA 가 설정된 기계에서 야장이 SSD 로 이사했을 것이다.
FIELD = ROOT / "data" / "field"

# 대장에 없는 파일. 삭제하지 않고 격리한다(MASTER §18-12).
QUARANTINE = (DATA / "_quarantine") if DATA else (ROOT / "data" / "_quarantine")

# ── 산출물 ────────────────────────────────────────────────────
# ★ processed 는 백업하지도 커밋하지도 않는다.
#   raw + 코드 + 대장 이 있으면 결정론적으로 재생성된다(현재 80초).
#   산출물만 보관하는 것은 "함수 결과는 저장하고 함수는 안 저장하는 것"이다.
#   재현 증적은 _manifest.json 의 git_sha 가 담당한다.
# ★ SSD(drvfs)에 두지 않는다. 파일당 I/O 가 경계를 넘어 크게 느려진다.
# ★ 2026-08-24 정정. 아래 주석은 "백업·커밋 안 함" 이라 적는데 실제로는
#   넷을 커밋한다(`.gitignore` 의 `!` 예외 — segments.geojson ·
#   segments.schema.json · _manifest.json · seg_uid_map.csv). UI 담당이
#   raw 2.6GB 없이 지도를 띄워야 하고 재현 증적이 저장소에 남아야 해서다.
#   `sources.yaml` layers.processed.committed_exceptions 가 정본이고
#   `datalog fsck` 가 git 추적 목록과 대조한다.
PROCESSED = ROOT / "data" / "processed"

# ★ 2026-08-26. 계층 선언 밖에 있던 둘을 등재했다. `pipeline.py` 가
#   `ROOT / "data/golden/..."` 를 문자열로 조립하고 `baseline.py` 가
#   자기 자리를 따로 잡고 있었다 — 계층이 없으면 파일은 아무 데나 떨어진다.
#   base 는 repo 다. 재생성 불가라 clone 만으로 보여야 한다.
GOLDEN = ROOT / "data" / "golden"
BASELINE = ROOT / "data" / "baseline"

# 표출용. 저장소 안. UI 담당이 raw 없이 작업할 수 있어야 하므로 커밋한다.
WEB = ROOT / "web" / "data"

# 계산은 미터 좌표계, 표출은 경위도. 순서를 바꾸면 전부 어긋난다.
CRS_M = "EPSG:5186"
CRS_W = "EPSG:4326"


def alive(p: Path) -> bool:
    """디렉터리가 **실제로 붙어 있는가.**

    ★ 2026-09-02. 외장 매체를 뽑은 채 `verify.sh` 를 돌리자 세 곳이 같은
      형태로 죽었다 — `pipeline.check_only` · `docnum_check` · `treecheck`.

          OSError: [Errno 19] No such device: '.../fire-lane-data/raw'

      `FIRE_LANE_DATA` 는 잡혀 있는데 **장치가 없는 상태**다. `is_dir()` 은
      경로가 없으면 `False` 를 주지만 마운트가 끊기면 예외를 던진다.
      "없다" 와 "죽었다" 를 코드가 안 갈랐다.

    ★ 2026-09-07 에 매체를 GIS 통합 담당에게 넘기면 **이것이 상시
      상태**가 된다. 그때 verify 가 세 곳에서 터지면 원인을 찾는 데
      시간을 쓴다(DECISIONS §104).
    """
    try:
        return p.is_dir()
    except OSError:
        return False


def check() -> None:
    """경로 상태를 사람이 읽을 수 있게 출력한다."""
    if DATA:
        src = "FIRE_LANE_DATA"
    elif os.environ.get("FIRE_LANE_RAW"):
        src = "FIRE_LANE_RAW (구방식)"
    else:
        src = "기본값(repo/data)"
    print(f"DATA      {DATA or '—'}   [{src}]")
    print(f"RAW       {RAW}")
    if not alive(RAW):
        print("          ★ 없다. FIRE_LANE_DATA 를 설정하거나 원본을 배치할 것")
    else:
        n = sum(1 for _ in RAW.rglob("*") if _.is_file())
        sz = sum(f.stat().st_size for f in RAW.rglob("*") if f.is_file()) / 1e9
        print(f"          {n}개 파일 · {sz:.2f} GB")
    for nm, p in (("LANDING", LANDING), ("NORM", NORM), ("INTERIM", INTERIM),
                  ("FIELD", FIELD), ("QUARANTINE", QUARANTINE)):
        print(f"{nm:9} {p}{'' if alive(p) else '   (없음)'}")
    print(f"PROCESSED {PROCESSED}   [재생성 가능. 백업·커밋 안 함]")
    print(f"WEB       {WEB}")


if __name__ == "__main__":
    check()


def require_lake(*, need: tuple[str, ...] = ("raw",)) -> None:
    """레이크가 실제로 붙어 있는가. **없으면 여기서 멈춘다.**

    ★ 2026-08-27. `raw` 가 없는 기계에서 `intake --stage` 가 그대로 돌아
      `landing` 을 새로 만들고 파일 10건을 복사했다. `doctor` 는
      `✗ layers.raw 이 required 인데 없다` 를 정확히 냈는데, **진단과
      게이트가 연결돼 있지 않았다.** 판정만 하고 아무도 안 막았다.

      같은 날 두 번 났다 — 리전에서 `apply*.sh` 6건, 그램에서 프로젝트
      산출물 4건. 도구마다 따로 검사하면 또 빠뜨린다. 관문은 하나여야
      하고, 경로 해석의 정본인 이 모듈이 그 자리다.

    ★ **빈 디렉터리는 붙은 것으로 치지 않는다.** WSL 은 마운트가 없어도
      `/mnt/d` 를 만들어 두고, 그러면 `is_dir()` 이 참이 된다.
      그것을 믿고 쓴 것이 이번 사고다.
    """
    import sys
    table = {"raw": RAW, "landing": LANDING, "norm": NORM,
             "interim": INTERIM, "quarantine": QUARANTINE}
    bad = []
    for n in need:
        d = table.get(n)
        if d is None:
            continue
        try:
            empty = not any(d.iterdir())
        except OSError:
            empty = True
        if empty:
            bad.append((n, d))
    if not bad:
        return
    lines = ["✗ 데이터 레이크가 붙어 있지 않다."]
    lines += [f"    {n:10} {d}" for n, d in bad]
    lines += [
        "",
        "  확인 —",
        "    ls /mnt/                          드라이브 문자",
        '    cmd.exe /c "wmic logicaldisk get name"',
        "    export FIRE_LANE_DATA=<fire-lane-data 경로>",
        "",
        "  ★ 빈 디렉터리는 붙은 것이 아니다. WSL 은 마운트가 없어도",
        "    /mnt/d 를 만들어 둔다 — 그것을 믿고 쓰다 landing 을",
        "    엉뚱한 곳에 만들었다(2026-08-27).",
    ]
    print("\n".join(lines))
    sys.exit(2)
