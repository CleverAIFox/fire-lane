#!/usr/bin/env python3
"""
render_figures.py — 정본에서 그림을 만든다.

    uv run python tools/render_figures.py            docs/figures/*.svg 생성
    uv run python tools/render_figures.py --check    정본과 어긋나면 종료코드 1

── 왜 생겼나 ───────────────────────────────────────────────────
기획서 그림 24장에 강제자가 **캡션뿐**이었다. `docx_check` 가 캡션 텍스트를
저장소 어휘와 대조하지만 **그림 자체는 아무도 안 본다.** [그림 13] 이 폐기된
반경 5m 원을 그리는데 캡션은 맞아서 안 잡혔다(PLAN §12 #15).

24장 중 **넷은 값이 정본에 있다.** 그리면 되는 것이지 사람이 다시 그릴
이유가 없다 — `web/workflow.html` 이 `MASTER §12` 에서 나오는 것과 같다.

★ 2026-09-24 (DECISIONS §236). 그 [그림 13] 을 여기서 그린다(`fig_xsec`).
  머리말이 석 주 동안 **자기가 못 고치는 예시로 그 그림을 들고 있었다.**

★ 2026-09-23 (DECISIONS §221-1). 종전에는 여기에 「`.docx` 안 이미지를 코드가
  교체하지는 않는다 — 알리기만 하고 넣는 것은 사람이 한다」 고 적혀 있었다.
  그 결정을 뒤집었다. 이 파일은 **SVG 를 만들고 어긋남을 알리고**,
  `tools/docx_figs.py --sync` 가 그것을 기획서 안에 **넣는다.**

IN    data/golden/segments.fingerprint.json · src/firelane/seg/params.py
OUT   docs/figures/*.svg · docs/figures/.lock.json
PARAM --check
"""

import argparse
import hashlib
import json
import sys

from figures import LOCK, OUT
from figures.structure import fig_boundary, fig_branch, fig_deploy, fig_verdict_flow
from figures.value import fig_cctv, fig_threshold, fig_unknown, fig_verdict
from figures.xsec import fig_xsec

FIGURES = {
    "verdict": fig_verdict,
    "threshold": fig_threshold,
    "cctv": fig_cctv,
    "unknown": fig_unknown,
    # ★ 구조 그림. 값이 아니라 관계를 그린다 — 2026-09-02 에 틀린 것이
    #   그 종류였다(DECISIONS §110).
    "branch": fig_branch,
    "deploy": fig_deploy,
    # ★ 2026-09-24 (PLAN §12 #15). 캡션은 고쳐졌는데 그림이 옛 모델을 그리던
    #   자리다. 값이 아니라 **규칙**을 그린다.
    "xsec": fig_xsec,
    # ★ 2026-09-28 (§278-4). 기획서 [그림 8] 이 라벨 둘을 겹쳐 찍은 채 제출본에
    #   있었다. 저장소 밖 PNG 라 고칠 수가 없었다 — 여기로 옮긴다.
    "boundary": fig_boundary,
    # ★ 2026-09-28 (§281-1). 기획서 [그림 14]. 규칙 문언 · 임계값 · 구간 수
    #   **셋 다 정본에서 읽는다** — 규칙이 바뀌면 그림이 따라 바뀐다.
    "verdict_flow": fig_verdict_flow,
}


def main() -> int:
    # ★ 2026-09-24 (PLAN §13 W13-6 · DECISIONS §243). 종전에는 `"--x" in sys.argv`
    #   였다 — **오타가 조용히 무시된다.** `--chek` 는 검사 대신 **그림 파일을 덮어썼다.**
    #   argparse 는 모르는 인자에 스스로 운다. 직접 구현할 일이 아니다(4족).
    ap = argparse.ArgumentParser(description="정본 → docs/figures/*.svg")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 낡았는지만 본다")
    check = ap.parse_args().check
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    for name, fn in FIGURES.items():
        svg = fn()
        made[name] = hashlib.sha256(svg.encode("utf-8")).hexdigest()[:16]
        if not check:
            (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")

    old = {}
    if LOCK.exists():
        old = json.loads(LOCK.read_text(encoding="utf-8")).get("figures", {})

    drift = [k for k, v in made.items() if old.get(k) not in (None, v)]
    if check:
        if drift:
            print("★ 그림이 정본과 어긋난다 — " + " · ".join(drift))
            print("  값이 바뀌었는데 기획서 그림이 옛 값을 그리고 있다.")
            print("  uv run python tools/render_figures.py         다시 만든다")
            print("  uv run python tools/docx_figs.py --sync       기획서에 넣는다")
            # ★ 2026-09-23 (DECISIONS §221-1). 종전에는 여기서 「사람이 넣는다 — 기획서는
            #   대외 제출본이고 생성물이 아니다」 라고 했다. 그 사이 `docx_fix.py` 가 같은
            #   파일의 문단을 기계로 고치고 있었고, 「사람이 넣는다」 는 곧 「안 넣는다」 였다.
            return 1
        if not old:
            print("! 잠금이 없다 — 한 번 생성해서 기준을 만들어라")
            return 1
        print(f"그림 OK — {len(made)}장 정본과 일치")
        return 0

    # ★ 2026-09-23. 잠금을 **덮어쓰지 않고 합친다.** `docx_figs.py` 가 같은 파일에
    #   `placed`(기획서에 박힌 지문)를 쓴다 — 덮어쓰면 그쪽 기록이 매번 사라지고,
    #   그러면 「기획서가 낡았는가」 를 묻는 관문이 조용히 통과한다.
    keep = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    LOCK.write_text(json.dumps({**keep, "figures": made}, ensure_ascii=False,
                               indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    for k in sorted(made):
        mark = " ★ 바뀜" if k in drift else ""
        print(f"  docs/figures/{k}.svg  {made[k]}{mark}")
    if drift:
        print("\n★ 바뀐 그림을 기획서에 넣는다:  uv run python tools/docx_figs.py --sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
