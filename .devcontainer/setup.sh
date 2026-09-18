#!/usr/bin/env bash
# .devcontainer/setup.sh — 컨테이너를 한 번 만들 때 도는 것.
#
# ★ 왜 생겼나. 2026-09-02 하루에만 기계 차이로 세 번 걸렸다 —
#   노드 v22 대 v24, 윈도우 사용자명이 달라 경로가 안 맞음,
#   FIRE_LANE_INBOX 가 한쪽에만 설정됨. 사람이 기억해서 맞추는 것을
#   그만둔다.
#
# ★ 파이프라인 전량은 이 안에서 안 돈다. `data/raw` 2.5GB 가 저장소 밖
#   외장 매체이고 컨테이너에 마운트되지 않는다. 여기서 되는 것은
#   문서 검사 · 테스트 · 린트다. 파이프라인은 레이크가 붙은 기계에서
#   돈다(MASTER §12-7).
#
# ★ 2026-09-18 정정. 종전 이 자리에 `JS · 화면` 이 적혀 있었다. **이미지에
#   node 가 없다**(Dockerfile — python:3.11-slim · features 선언도 없다).
#   `verify.sh` 의 JS 넷과 내비 타입 검사는 이 안에서 못 돈다. 되는 것만 적는다.
set -euo pipefail

# ★ 2026-09-18. 이미지(Dockerfile)가 `/bin/uv` 를 이미 넣는다. 그런데도 매번 받아서
#   설치하고 있었다 — 컨테이너에 네트워크가 없으면 여기서 죽는다. 없을 때만 받는다.
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv sync

# 커밋 시점 방어. 이걸 안 걸면 산출물·비밀값이 그냥 들어간다(MASTER §12-11).
# ★ 지웠다 — 전역 훅이 저장소 `.githooks` 에 위임한다. **로컬로 박으면** 전역이 죽고 자격증명 검사가 사라진다
git config core.quotepath false
git config core.precomposeunicode true

echo
echo "  준비됐다. 확인은 이것 하나다 —"
echo "    bash tools/verify.sh --fast"
echo
echo "  ★ 파이프라인 전량은 데이터 레이크가 붙은 기계에서만 돈다."
echo "    FIRE_LANE_DATA 가 비어 있으면 verify 가 그 단계를 건너뛴다."
