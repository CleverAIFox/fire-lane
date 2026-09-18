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
# ★ 2026-09-18 (W1). node 가 들어왔다. 종전에는 이미지에 node 가 없어
#   `verify.sh` 의 JS 넷이 이 안에서 못 돌았고, `js_graph_check` 는 `note` 가
#   아니라 `step` 이라 **권장 명령(`verify.sh --fast`)이 컨테이너에서 빨간불로
#   끝났다.** Dockerfile 을 고치지 않고 `devcontainer.json` 의 `features` 로
#   받는다 — 손으로 설치 줄을 짜지 않는다.
#   판은 `web/navi/.nvmrc`(20) 를 따른다. 클래식 JS 검사(`node --check` ·
#   jsdom 스모크)는 판을 안 탄다. CI 의 클래식 22 는 의도된 결정이라 안 건드린다
#   (contract.yml §186-2 · test_ci_env.test_navi_node_version_has_one_source_of_truth).
set -euo pipefail

# ★ 2026-09-18. 이미지(Dockerfile)가 `/bin/uv` 를 이미 넣는다. 그런데도 매번 받아서
#   설치하고 있었다 — 컨테이너에 네트워크가 없으면 여기서 죽는다. 없을 때만 받는다.
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv sync

# 한글 파일명 표시. 커밋 방어가 아니다 — 아래가 커밋 방어다.
git config core.quotepath false
git config core.precomposeunicode true

# ── 커밋 시점 방어 ────────────────────────────────────────────
# ★ 2026-09-18 (W1). 종전 이 자리에는 "커밋 시점 방어" 라는 제목 아래
#   `quotepath` · `precomposeunicode` 두 줄만 있었다 — 한글 파일명 표시 설정이고
#   방어가 아니다. 실제 방어(`core.hooksPath`)는 지워져 있었고, 그래서
#   **clone 한 사람에게 커밋 시점 방어가 0 이었다.**
#
# ★ `pre-commit install` 을 쓰지 않는다. `core.hooksPath` 가 설정돼 있으면
#   pre-commit 이 설치를 거부한다(2026-09-18 실측). 그런데 `dms.py` 의
#   `hook/global-hooksPath` 는 전역 훅이 없으면 실패로 친다 — 전역 훅이
#   fire-lane 밖 저장소의 자격증명 방어를 맡기 때문이다. 둘 다 지키는 길은
#   전역 훅이 이 저장소의 설정을 **이어서 부르는** 것 하나뿐이다.
#   여기서는 훅 환경만 미리 받아둔다(첫 커밋이 느려지지 않게).
uv run pre-commit install-hooks

echo
echo "  준비됐다. 확인은 이것 하나다 —"
echo "    bash tools/verify.sh --fast"
echo
echo "  ★ 커밋 시점 방어 — 전역 훅이 .githooks/pre-commit 을 후보로 찾아 부른다."
echo "    설치할 것은 없다. 도달만 확인해라 —"
echo "      bash .githooks/global-chain.sh --check"
echo
echo "  ★ 파이프라인 전량은 데이터 레이크가 붙은 기계에서만 돈다."
echo "    FIRE_LANE_DATA 가 비어 있으면 verify 가 그 단계를 **실패**로 낸다."
echo "    (2026-09-18 배치 0 — 덮는 관문이 없는 생략은 통과가 아니다)"
