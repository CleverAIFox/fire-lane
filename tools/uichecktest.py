#!/usr/bin/env python3
"""
uichecktest.py — **`uicheck.py` 의 자기검사.** 판별식만 산다.

★ 왜 별채인가 (DECISIONS §445-1 과 같은 사유). `uicheck` 가 상한(600)을 넘었고,
  흔드는 쪽과 재는 쪽을 한 파일에 두면 자기검사가 제 판별식을 흔든다
  (§398-6 · §443-6). 그리고 `#166` 을 닫으며 지문 범위가 **그 도구를 import 하는
  tools/*.py 까지** 넓어졌으므로, 떼어도 **장부가 이 파일을 덮는다** — 그 전에는
  떼면 문을 고쳐도 장부가 안 낡았다. 같은 쪼개기를 한 판에서 **두 번째** 한다.

IN    (없음 — `uicheck` 의 판별식을 합성 입력으로 민다)
OUT   표준출력 · 종료코드
부류  몸통   진입점이 **아니다.** `uicheck.py --selftest` 가 부른다  (DECISIONS §398)
밖    **실물이 옳은가는 안 본다** — 그것은 `uicheck` 의 `split()` 이 든다.
      **흔들지 않는다** — 합성 문자열만 민다(§441-5).
"""
from __future__ import annotations

from uicheck import (
    _THEME,
    LAYER_FILES,
    MARKER_SEC,
    NAVI_FNS,
    OPS_FNS,
    SRC,
    _newest,
    _uses,
    documented_markers,
    emphasis_faults,
    emphasis_uses_no_color,
    layer_ids,
    layers_declared,
    navi_off,
    screen_text,
    shared_layers,
    tier_faults,
    ui_text_chars,
)


def selftest() -> int:
    """★ 「0건이 청결인가 죽음인가」(§230). 판별식이 두 결함을 실제로 가르는가."""
    fails = []
    per = layer_ids()
    if not per:
        fails.append("층을 하나도 못 읽었다 — 빈 그물이다")
    if "baseLayers" not in per:
        fails.append("`baseLayers` 를 못 찾았다 — 공유 층 계산이 0 이 된다")
    # ★ 파일이 갈라져도 그물이 덮는가. 한 파일만 읽으면 여기서 걸린다(§311).
    for fn in NAVI_FNS + OPS_FNS:
        if fn not in per:
            fails.append(f"`{fn}` 을 못 찾았다 — 층 명세 파일이 갈라졌는데 "
                         "`LAYER_FILES` 에 안 넣었을 수 있다")
    for f in LAYER_FILES:
        if not (SRC / "components" / f).is_file():
            fails.append(f"`{f}` 가 없다 — 선언이 낡았다")

    sh = shared_layers()
    if not sh:
        fails.append("공유 층이 0 이다 — 두 지도가 `baseLayers` 를 같이 부르는데 0 일 수 없다")
    # ★ 주행에도 값이 있어 **남긴** 것들. 이것이 사라지면 세는 법이 틀린 것이다.
    for want in ("bg", "seg-road", "lbl-road", "hydrant"):
        if want not in sh:
            fails.append(f"공유 층에 `{want}` 가 없다 — 세는 법이 틀렸다")
    # ★ 반대 방향 — 끈 것이 공유에 남아 있으면 빼기가 안 먹은 것이다(§311).
    off = set(navi_off())
    if not off:
        fails.append("`NAVI_OFF` 를 못 읽었다 — 빼기가 통째로 안 먹는다")
    for gone in ("lbl-poi", "lbl-bldg", "seg-tint"):
        if gone in sh:
            fails.append(f"`{gone}` 가 아직 공유다 — 내비가 그것을 안 끈다")
        if gone not in off:
            fails.append(f"`{gone}` 가 `NAVI_OFF` 에서 빠졌다 — 주행 예산이 헐거워졌다")

    # 배타 판별식이 **거짓을 거짓이라 하는가**
    if _uses("OpsApp.tsx", "NaviMap"):
        fails.append("관제가 내비 지도를 쓴다고 나온다 — 실물과 다르면 판별식이 틀렸다")
    if not _uses("App.tsx", "NaviMap"):
        fails.append("내비가 `<NaviMap>` 을 안 쓴다고 나온다 — 판별식이 못 찾는다")

    # 신선도 판별식이 **반대 방향도 잡는가**
    if _newest(SRC) <= 0:
        fails.append("소스 시각을 못 읽는다 — 신선도 판정이 늘 통과한다")

    for f in fails:
        print(f"  ✗ {f}")
    # ★ ③ 마커 대조 (§337). **문서를 읽기는 하는가** — 못 읽으면 언제나 초록이다.
    said = documented_markers()
    if not said:
        fails.append(f"`MASTER {MARKER_SEC.strip('# .')}` 의 마커 표를 못 읽는다 — 빈 그물이다")
    # ★ 칸을 가르는가. 둘째 칸이 층이고 넷째 칸의 백틱은 **함수 이름**이다 —
    #   안 가르면 `hydrantIcon()` 이 층으로 세어져 영원히 빨갛다.
    if any(s.endswith("()") for s in said):
        fails.append(f"표의 함수 이름을 층으로 센다 — {[s for s in said if s.endswith('()')]}")
    if "hydrant" not in said:
        fails.append("표에서 `hydrant` 를 못 찾는다 — 둘째 칸을 안 읽고 있다")
    # ★ 반대 방향 — 없는 층을 적으면 정말 우는가
    if not [s for s in ("streetlight-dot", "lightpole")
            if s not in {i for v in per.values() for i in v}]:
        fails.append("걷어낸 가로등 층이 아직 코드에 있다 — 주입 판별식이 헛돈다")
    # ★ 2026-10-09 (§441). 강조 채널 문을 **양방향**으로 민다. 실물로만 재면
    #   「언제나 통과」와 「실제로 깨끗함」을 못 가른다(§230).
    #   ★ **합성으로 민다 — 실물을 안 고친다.** 고쳤다 되돌리면 그 사이 트리가
    #     더럽고, 배달 기계가 그것을 본다.
    if emphasis_uses_no_color():
        fails.append("지금 트리에서 강조 채널 문이 운다 — 실물이 이미 색을 쓴다")
    ok = "@keyframes flpulse{0%{opacity:1}}"
    if emphasis_faults(ok):
        fails.append("색 없는 선언에서 운다 — 거짓 경보")
    if not emphasis_faults(ok + '\nconst p = "#ff0000";'):
        fails.append("색을 심었는데 안 운다 — 그물이 샌다")
    if not emphasis_faults(ok + "\nconst p = rgba(1,2,3,.4);"):
        fails.append("`rgba(` 를 색으로 안 센다")
    if not emphasis_faults("// 머리말뿐"):
        fails.append("맥박 선언이 없는데 통과한다 — 빈 그물을 안 막는다")
    if not emphasis_faults(None):
        fails.append("파일이 없는데 통과한다")
    if emphasis_faults(ok + "\n// 주석 속 #ff0000 은 색이 아니다"):
        fails.append("주석 속 색을 센다 — 주석은 설명이다")

    # ★ ㉧ 화면 글자 — 세는 꼴을 **합성 입력으로** 민다(§445).
    if screen_text('const a = "통행 가능";') != "통행가능":
        fails.append("화면 문자열을 못 집는다")
    # ★ 2026-10-09 (DECISIONS §445). **이 문이 없어서 자가 틀렸다.** 화면 말의
    #   과반은 JSX 텍스트 노드이고 종전 판별식은 문자열 리터럴만 집었다 —
    #   관제 범례에서 설명 두 덩이를 걷었는데 수가 한 글자도 안 움직였다.
    if screen_text("<div>통행 가능</div>") != "통행가능":
        fails.append("JSX 텍스트를 안 센다 — 화면 말의 과반이 그 꼴이다")
    # ★ 2026-10-10 (§448). **줄 끝 주석**도 주석이다. 안 떼면 이 래칫이
    #   「사유를 줄 끝에 적지 마라」가 된다 — 자가 거꾸로 일한다.
    if screen_text("const a = 1;  // 성긴 파선"):
        fails.append("줄 끝 주석을 센다 — 사유를 적을수록 래칫이 는다")
    if screen_text('const u = "https://ko.example/가";') != "가":
        fails.append("`https://` 를 주석으로 보고 글자를 버린다")
    if screen_text('// "통행 가능"\n'):
        fails.append("주석 속 말을 센다 — 사유를 길게 적으면 래칫이 는다")
    if screen_text('/* "통행 가능" */\n'):
        fails.append("블록 주석 속 말을 센다")
    if screen_text('const c = "#ff0000"; const id = "seg-road";'):
        fails.append("한글 없는 문자열을 센다 — 색 코드와 id 가 분모에 든다")
    if screen_text("const t = `폭 ${w}m`;") != "폭":
        fails.append("백틱 문자열을 못 집는다")
    if ui_text_chars() <= 0:
        fails.append("화면 글자를 0자로 센다 — 수집기가 죽었다")

    # ★ ㉨ 층의 휘도 — **양방향**과 빈 그물(§445)
    _ok = [("act", "#16233c"), ("pick", "#111c2f"), ("idle", "#0b1322")]
    if tier_faults(_ok):
        fails.append("바른 순서에서 운다")
    if not tier_faults([("act", "#0b1322"), ("pick", "#111c2f"), ("idle", "#16233c")]):
        fails.append("순서가 거꾸로인데 안 운다 — 계층이 거꾸로 읽힌다")
    if not tier_faults([("act", "#111c2f"), ("pick", "#111c2f"), ("idle", "#0b1322")]):
        fails.append("두 층이 같은 밝기인데 안 운다 — 같으면 층이 아니다")
    if not tier_faults([]):
        fails.append("선언이 비었는데 통과한다 — 블록이 사라지면 조용히 통과한다")
    if len(layers_declared(_THEME.read_text(encoding="utf-8"))) != 3:
        fails.append("실물에서 층을 셋으로 못 읽는다 — `D.card` 꼴을 푸는가")

    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 32")
    return 1 if fails else 0
