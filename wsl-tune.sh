#!/usr/bin/env bash
# wsl-tune.sh — hathor(CUDA) 와 fire-lane(ETL) 이 같은 WSL 을 나눠 쓰는 설정
#
#   bash wsl-tune.sh          현재 상태 + 권장값 출력, 파일은 안 건드림
#   bash wsl-tune.sh --apply  .wslconfig 를 쓴다 (기존 파일 백업)
#
# ── 전제 ───────────────────────────────────────────────────
# 호스트 8GB. hathor 는 CUDA 학습, fire-lane 은 GeoPandas ETL.
# 둘 다 같은 distro 안에서 돈다면 WSL 에 준 메모리를 서로 뺏는다.
#
# ── 왜 6GB 를 더 못 올리나 ──────────────────────────────────
# 8GB 중 6GB 를 WSL 이 잡으면 윈도우에 2GB 남는다. NVIDIA 드라이버와
# 데스크톱이 그걸 쓰고, CUDA 는 호스트에 pinned memory 도 잡는다.
# 더 올리면 윈도우가 스왑질을 시작해 GPU 학습이 오히려 느려진다.
#
# ── 그래서 방향을 바꾼다 ────────────────────────────────────
#   1. autoMemoryReclaim  — WSL 이 안 쓰는 메모리를 윈도우에 돌려준다.
#      ETL 이 끝난 뒤 6GB 를 계속 물고 있으면 hathor 가 굶는다.
#   2. processors 를 6 으로 — 8코어 전부 주면 ETL 의 GDAL 이 CPU 를
#      다 먹어 CUDA 호스트 스레드(데이터 로더)가 밀린다.
#   3. sparseVhd — 가상디스크가 쓴 만큼만 차지한다.
#   4. 우선순위 래퍼(flrun-nice) — ETL 을 낮은 우선순위로 돌리고,
#      메모리가 모자라면 hathor 가 아니라 ETL 이 먼저 죽게 만든다.
set -euo pipefail

CFG="/mnt/c/Users/${FL_WINUSER:-$USER}/.wslconfig"
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

echo "── 현재"
if [ -f "$CFG" ]; then
    sed 's/^/    /' "$CFG"
else
    echo "    (.wslconfig 없음)"
fi
echo
echo "── 현재 WSL 이 보는 것"
free -h | sed 's/^/    /'
echo "    코어 $(nproc)"
echo

RECOMMENDED='[wsl2]
# 호스트 8GB. 윈도우·NVIDIA 드라이버 몫으로 2.5GB 이상 남긴다.
memory=5500MB

# 8코어 전부 주면 GDAL 이 CUDA 데이터로더용 호스트 스레드를 밀어낸다.
processors=6

# 메모리보다 스왑을 크게. ETL 피크는 짧고, 스왑으로 넘겨도 죽지는 않는다.
swap=12GB

# ★ 안 쓰는 메모리를 윈도우에 돌려준다. ETL 이 끝난 뒤에도 5.5GB 를
#   계속 물고 있으면 hathor 학습이 굶는다.
autoMemoryReclaim=gradual

# 게스트가 해제한 페이지를 호스트에 알린다. 위 항목의 전제다.
pageReporting=true

[experimental]
# 구버전 WSL 은 위 두 항목을 여기서만 읽는다. 양쪽에 둬도 무해하다.
autoMemoryReclaim=gradual
sparseVhd=true'

echo "── 권장"
echo "$RECOMMENDED" | sed 's/^/    /'
echo

if [ "$APPLY" -eq 1 ]; then
    [ -f "$CFG" ] && cp "$CFG" "$CFG.bak.$(date +%Y%m%d_%H%M%S)" && echo "  ✓ 백업"
    printf '%s\n' "$RECOMMENDED" > "$CFG"
    echo "  ✓ $CFG 기록"
    echo
    echo "  ★ 윈도우 PowerShell 에서:  wsl --shutdown"
    echo "    hathor 가 돌고 있으면 먼저 멈춰라."
else
    echo "  적용하려면:  bash wsl-tune.sh --apply"
fi

echo
echo "── 우선순위 래퍼 설치"
cat >> "$HOME/.fire-lane.sh" <<'WRAP_EOF'

# ── hathor 와 공존 ─────────────────────────────────────────
# ETL 은 배치 작업이고 hathor 학습은 대기시간이 아깝다. ETL 을 양보시킨다.
#
#   flnice flrun --from ingest      낮은 우선순위 + OOM 1순위로 실행
#
# oom_score_adj 를 올리면 메모리가 바닥날 때 커널이 이 프로세스를 먼저
# 고른다. hathor 가 학습 3시간째에 죽는 것보다 ETL 이 죽고 다시 도는 게 싸다.
flnice() {
    ( echo 800 > /proc/self/oom_score_adj 2>/dev/null || true
      exec nice -n 15 ionice -c 3 "$@" )
}

# 지금 누가 메모리를 먹고 있나.
flmem() {
    printf '\n'; free -h
    printf '\n  메모리 상위 8개\n'
    ps -eo pid,rss,pcpu,comm --sort=-rss | head -9 |
        awk 'NR==1{printf "    %-8s %-10s %-6s %s\n","PID","RSS(MB)","CPU%","CMD";next}
             {printf "    %-8s %-10.0f %-6s %s\n",$1,$2/1024,$3,$4}'
    if command -v nvidia-smi >/dev/null 2>&1; then
        printf '\n  GPU\n'
        nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu \
                   --format=csv,noheader 2>/dev/null | sed 's/^/    /'
    fi
    printf '\n'
}
WRAP_EOF
echo "  ✓ flnice · flmem 를 ~/.fire-lane.sh 에 추가"
echo
cat <<'NEXT'
── 쓰는 법

  flmem                         지금 누가 먹고 있나
  flnice flrun --from ingest    ETL 을 양보시키며 실행

★ 근본 해결은 설정이 아니라 일정이다.
  hathor 학습 중에 ingest 전량(피크 ~4GB)을 같이 돌리지 마라.
  8GB 호스트에서 둘 다 만족시키는 설정은 없다.

  ETL 은 --only 로 쪼개면 피크가 크게 낮아진다. 학습 중에 꼭 돌려야 하면:
    flnice uv run python src/etl/ingest.py --only road_link road_rw road_intrvl
    flnice uv run python src/etl/ingest.py --only ngii1k ngii_road ngii_road_center
    flnice uv run python src/etl/ingest.py
NEXT
