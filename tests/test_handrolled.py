#!/usr/bin/env python3
"""
test_handrolled.py — **표준 의존성이 할 수 있는 일을 손으로 짠 자리.** (PLAN §1 #168)

── 왜 생겼나 (2026-10-11 · DECISIONS §470) ─────────────────────
사용자 원칙은 「가능한 한 모든 것을 의존성에 맡긴다」이고 `PLAN §13` 의 결함
족 표가 **「4. 직접 구현 — 표준 의존성이 할 수 있는 일을 손으로 짠다」**를
족으로 들고 있었다. 그런데 **전수로 훑은 판이 없었다** — 족만 있고 분모가
없으면 그 족은 세어지지 않는다(§435 · §468 이 다른 축에서 배운 그것이다).

★ 이 파일이 그 분모다. 자리마다 **옮겼다 / 안 옮긴다 + 사유**를 적는다.
  「안 옮긴다」가 많아도 된다 — 사유가 있으면 그것은 결정이고, 없으면 빚이다.

★ **양방향**이다 —
    옮겼다     그 표식이 **돌아오면** 운다 (손 판이 다시 서는 것)
    안 옮긴다  그 표식이 **사라지면** 운다 (죽은 선언 · §370)
    선언 밖    같은 표식이 다른 파일에 서면 운다 (새 사본)

★ **「의존성을 쓰면 늘 낫다」고 말하지 않는다.** 봉인 지문에 박힌 값, 번들
  무게, 결정성은 실재하는 사유다. 이 파일이 드는 것은 **그 사유가 적혀
  있는가** 하나다.

IN    tools/*.py · src/firelane/**/*.py · web/navi/src/**/*.ts
OUT   없음 (검사)
PARAM SITES
밖    **성능은 안 본다.** 「느린가」는 그 도구의 일이고, 여기가 드는 것은
      「남이 시험해 둔 것을 손으로 다시 짰는가」다.
      **옮긴 코드가 같은 답을 내는가도 안 본다** — 그 대조는 옮기는 판이
      실측으로 하고 DECISIONS 가 그 수를 든다(§470 이 둘을 적었다).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: 훑는 우주. 손으로 짠 것이 살 수 있는 자리 전부다.
#: ★ 2026-10-11 (DECISIONS §475). `.tsx` 를 넣었다 — `hhmm` 의 옛 두 사본이
#:   `App.tsx` · `OpsApp.tsx` 에 있었고(§130), 우주가 `.ts` 뿐이면 그 자리로
#:   사본이 돌아와도 안 운다. **분모는 사본이 살 수 있는 자리 전부다.**
SCAN = ("tools/*.py", "tools/**/*.py", "src/firelane/**/*.py",
        "web/navi/src/**/*.ts", "web/navi/src/**/*.tsx")

#: 자리 이름 → 선언.
#:   mark   그 손 판을 가리키는 표식 (정규식)
#:   where  그 표식이 **있어야/없어야** 하는 파일
#:   moved  True 면 옮겼다(표식이 없어야 한다) · False 면 안 옮긴다(있어야 한다)
#:   dep    그 일을 할 수 있는 **선언된** 의존성
#:   why    옮긴 사유 또는 **안 옮기는 사유.** 사유가 본체다
SITES: dict[str, dict] = {
    "kpi 최단경로": {
        "mark": r"^import heapq",
        "where": "tools/kpi.py",
        "moved": True,
        "dep": "networkx",
        "why": "손으로 짠 Dijkstra 와 역추적 15줄이었다. `networkx` 는 이미 선언돼"
               " 있고 `src/firelane/seg/graph.py` 를 포함해 다섯 파일이 쓴다 —"
               " 같은 일을 두 번 짠 자리다. 실측으로 옮겼다: 발행 그래프 전수에서"
               " **거리 어긋남 0 · 엣지열 어긋남 0** 이고 `kpi.py` 출력이"
               " **한 글자도 안 바뀌었다**(DECISIONS §470-1)",
    },
    "막다른 끝 최근접": {
        "mark": r"for j, q in enumerate\(nodes\)",
        "where": "tools/navicheck.py",
        "moved": True,
        "dep": "shapely",
        "why": "전수 곱(449 × 1,139)을 손으로 돌았고 머리말이 「격자를 깔면"
               " 빨라지지만 빠른 코드와 맞는 코드 중 맞는 쪽을 고른다」고 적었다."
               " **그 선택지가 둘이 아니다** — `shapely.STRtree` 는 빠르면서 맞는다."
               " 실측 — 쌍 집합 동일 · 거리 최대 차 1.3나노미터 · 15배"
               " (DECISIONS §470-2)",
    },
    "국소 평면 근사": {
        # ★ 2026-10-11 (DECISIONS §473). 표식이 `^MY = 110_574` 였고 그 수가
        #   **틀린 수**였다. 표식을 **값이 아니라 이름**으로 바꾼다 — 값에
        #   걸면 그 값을 고칠 때마다 선언이 낡고, 그러면 사람이 선언을
        #   고치면서 사유도 같이 지운다.
        "mark": r"^MY = [\d.]+",
        "where": "src/firelane/localplane.py",
        "moved": False,
        "dep": "pyproj",
        "why": "**투영이 아니라 한 동네 크기의 어림**이다. `pyproj` 변환으로 바꾸면"
               " 조사 도구가 파이프라인 의존에 붙고, 무엇보다 이 값은 **결정적**이라"
               " 같은 입력에 같은 수가 나온다 — 그것이 관문이 드는 성질이다."
               " 제대로 된 변환(5179 ↔ 5186 ↔ 4326)은 이미 `pyproj` 가 한다"
               " (DECISIONS §469-3)",
    },
    "끝점 접합 union-find": {
        "mark": r"^def find\(",
        "where": "src/firelane/seg/unionfind.py",
        "moved": False,
        "dep": "networkx",
        "why": "`networkx.connected_components` 로 바꿀 수 있지만 **묶는 규칙이"
               " 네 곳에서 서로 다르다** — 합치면 `seg_uid` 가 움직인다(PLAN #47 이"
               " 그 사유를 적고 **정본을 이 파일 하나로** 모았다. 넷은 여기서"
               " import 한다). 판정 키를 흔드는 것과 의존성에 맡기는 것은 다른 일이다",
    },
    "대체 접근 1→전 노드": {
        "mark": r"export function reachable",
        "where": "web/navi/src/domain/access.ts",
        "moved": False,
        "dep": "(없다 — 번들에 그래프 의존성을 안 넣는다)",
        "why": "같은 번들의 A*(`graph.ts`)와 **다른 일감**이다 — 이쪽은 1→전 노드고"
               " 저쪽은 1→1 이다(§465 가 그 둘의 전개 수를 쟀다). 번들 무게 사유는"
               " 같다. 둘을 하나로 합치지도 않는다: 합치면 회전 금지·되돌아가기"
               " 상태가 접근 탐색에도 붙고, 그것은 **다른 답**이다",
    },
    "내비 A*": {
        # ★ 표식을 **그 함수 이름**으로 좁혔다. `open.sort(` 로 잡으면 같은
        #   번들의 `access.ts::reachable`(아래 자리)까지 물고, 그러면 두 자리가
        #   서로를 사본으로 지목한다 — 그 둘은 다른 일감이다(§465).
        "mark": r"export function findRoute",
        "where": "web/navi/src/domain/graph.ts",
        "moved": False,
        "dep": "(없다 — 번들에 그래프 의존성을 안 넣는다)",
        "why": "브라우저 번들이다. 그래프 라이브러리를 넣으면 내비 무게가 늘고"
               " `naviweight` 래칫이 운다. 그리고 이 A* 는 **회전 금지·되돌아가기**"
               " 를 상태에 넣은 변종이라(§215-1 · §218-2) 범용 구현으로 못 받는다 —"
               " 같은 답을 내는 라이브러리가 애초에 없다",
    },
    "시각 서식 hh:mm": {
        # ★ 표식을 **서식의 꼴**로 잡는다. 이름(`hhmm`)으로 잡으면 다른
        #   이름의 다섯째 사본을 못 본다(§472 가 배운 그 자리다).
        "mark": r"getHours\(\)\)\.padStart",
        "where": "web/navi/src/ui/tokens.ts",
        "moved": False,
        "dep": "(없다 — 브라우저 표준은 로케일·시간대에 흔들린다)",
        "why": "`Intl.DateTimeFormat` · `toLocaleTimeString` 이 할 수 있지만 그"
               " 출력은 **기계의 로케일·시간대에 따라 갈린다** — 화면의 글자가"
               " 기계마다 다르면 그 화면을 대조할 수 없고, 이 저장소는 로케일에서"
               " 이미 한 번 물렸다(§462 의 들여쓰기 정규식). ★ 그래서 공식은"
               " 남고, 이 자리가 드는 것은 **집이 하나인가**다. §130 이 `App.tsx` ·"
               " `OpsApp.tsx` 의 두 벌을 여기로 모았는데 넉 달 뒤 `app/useShare.ts`"
               " 가 **네 번째**를 짰다 — 계층이 정본을 가렸다(DECISIONS §475)",
    },
    "sRGB 역감마 · 휘도": {
        # ★ 표식을 **상수**로 잡는다. 이름(`lin` · `ch`)은 자리마다 달랐고
        #   그것이 §472 가 배운 그 자리다 — 공식의 상수는 이름보다 안 변한다.
        "mark": r"0\.04045",
        "where": "tools/srgb.py",
        "moved": False,
        "dep": "pillow",
        "why": "**맡길 의존성이 없다.** `colorsys`(표준 라이브러리)는 HSV · HLS ·"
               " YIQ 뿐이고 sRGB 감마도 Lab 도 안 한다. `pillow` 의 `ImageCms` 는"
               " **ICC 프로파일** 변환이라 같은 수가 안 나오고 littlecms 판에 따라"
               " 갈린다 — 관문이 판마다 갈리면 관문이 아니다. ★ 그래서 이 자리가"
               " 고친 것은 「의존성이 할 일을 손으로 짰다」가 아니라 **「정본 없이"
               " 손으로 짠 것이 셋」**이다(`colorsim` 에 두 벌 · `uicheck` 에 한 벌)."
               " 실측으로 모았다 — 무작위 2만 쌍에서 휘도 어긋남 0 · ΔE 1.6e-13 ·"
               " 역감마는 0~255 전수 0 (DECISIONS §474)",
    },
    "분위수 손 색인": {
        # ★ 표식은 **색인 꼴** 이다 — `[int(… .9 …)]`. 정본(`firelane.quantile`)
        #   머리말도 이 꼴을 글자로 안 적는다(적으면 제 금지를 어긴다 · §469 가
        #   `localgeo` 에서 같은 값을 치렀다).
        "mark": r"\[int\([^\]\n]*\.9",
        "where": "tools/evalgen.py",
        "moved": True,
        "dep": "numpy",
        "why": "같은 분위수를 **네 공식**으로 재고 있었다. `evalgen` · `kpi` 는"
               " 「n×0.9 의 정수부」로 집어 **n ≤ 10 이면 최댓값**을 「p90」 이라고"
               " 찍었고(`ratio_max` 바로 옆 칸이다) `publish_context` 는"
               " 「0.9×(n−1)」로 집어 **n = 2 면 최솟값**을 찍었다."
               " `numpy.quantile` 이 정본이고 실측으로 `pandas` 와 전부 같다"
               " (DECISIONS §471)",
    },
    "글자 폭 어림 (관리카드)": {
        # ★ 2026-10-11 (DECISIONS §472). 이 자리는 **이름이 달라서** §470 의
        #   훑기에 안 걸렸다 — 표식이 `def text_extent` 였고 이쪽은 `_width` 다.
        #   같은 일감의 사본은 **정규식이 아니라 사람이** 찾는다. 찾은 것을
        #   선언에 올리는 것이 이 파일의 일이다.
        "mark": r"def _width",
        "where": "src/firelane/vehiclecard.py",
        "moved": True,
        "dep": "(정본 `firelane.emwidth`)",
        "why": "관리카드 PDF 의 **머리글 칸 중심**을 찾는 폭 어림이었다. 손 판은 `[가-힣]` 하나로"
               " 가르고 나머지를 0.55 로 세서 `㎏`·한자·전각을 좁다고 셌다. 정본으로 옮겼다 —"
               " 레이크의 관리카드 PDF 넷(84칸)을 두 판으로 파싱해 **어긋남 0**, norm CSV"
               " **바이트 동일**이다(PLAN #169 · DECISIONS §543). 칸 중심 간격 69pt 가 예보대로"
               " 어긋남을 삼켰다",
    },
    "글자 폭 어림": {
        "mark": r"def text_extent",
        "where": "tools/svg_fit.py",
        "moved": False,
        "dep": "pillow",
        "why": "`PIL.ImageFont.getlength` 로 **정확히** 잴 수 있지만, 이 어림이"
               " 묻는 것은 「브라우저가 어떤 폰트로 그려도 안 넘치는가」다 —"
               " 한 폰트로 정확히 재면 그 폰트에서만 맞고 다른 기계에서 넘친다."
               " **보수적인 어림이 목적이고 정확한 측정이 그것을 깨뜨린다**",
    },
}


#: 「가운데 원소를 집는다」 색인 꼴. **중앙값이면 `statistics.median` 이 정본**
#: 이고, 짝수 길이에서 이 꼴은 가운데 **둘의 평균이 아니라 위쪽**을 낸다.
MID_INDEX = re.compile(r"\[[^\[\]\n]*//\s*2\s*\]")

#: 그 꼴이 **중앙값이 아닌** 자리 — 파일 → (몇 번 · 사유).
#:   ★ 수를 같이 적는다. 사유만 적고 수를 안 적으면 같은 파일에 **새 손 중앙값**
#:     이 서도 조용히 통과한다 — 그것이 §468 · §469 가 치른 값이다.
MID_OK: dict[str, tuple[int, str]] = {
    "src/firelane/skeleton.py": (
        1, "NGII 점열의 **가운데 점**을 골라 거기서 최근접을 묻는다 —"
           " 표본의 중앙값이 아니라 선 위의 한 점이다"),
    "tools/baseline.py": (
        1, "구간 좌표열의 **가운데 좌표**다(스냅 대표점). 수가 아니라 점이고"
           " 평균을 내면 선 밖으로 나갈 수 있다"),
    "tools/bridge_audit.py": (
        1, "같은 것 — 교량 선형의 가운데 좌표를 집는다"),
}


def _files() -> list[Path]:
    out: list[Path] = []
    for pat in SCAN:
        out += [p for p in ROOT.glob(pat) if "__pycache__" not in p.parts]
    return sorted(set(out))


def site_faults(d: dict, root: Path = ROOT) -> list[str]:
    """한 자리의 선언이 실물과 같은가. **비면 산다.** 순수 함수다 — 시험이
    합성 선언으로 양쪽을 민다(카나리아)."""
    f = root / d["where"]
    if not f.is_file():
        return [f"선언이 없는 파일을 가리킨다 — {d['where']}"]
    hit = re.search(d["mark"], f.read_text(encoding="utf-8"), re.M)
    if d["moved"] and hit:
        return [f"**손 판이 돌아왔다** — {d['where']} 에 `{d['mark']}` 가 있다."
                f" 그 일은 `{d['dep']}` 가 한다"]
    if not d["moved"] and not hit:
        return [f"**표식이 사라졌다** — {d['where']} 에 `{d['mark']}` 가 없다."
                " 옮겼으면 `moved: True` 로 고치고 사유를 다시 적어라."
                " 지운 것이면 이 줄을 지워라(죽은 선언 · §370)"]
    return []


def copy_faults(d: dict, files: list[Path], root: Path = ROOT) -> list[str]:
    """같은 표식이 **선언 밖 파일**에 섰나. 비면 산다."""
    rx = re.compile(d["mark"], re.M)
    me = (root / d["where"]).resolve()
    here = Path(__file__).resolve()
    bad = [p.relative_to(root).as_posix() for p in files
           if p.resolve() not in (me, here) and rx.search(p.read_text(encoding="utf-8"))]
    return [f"같은 표식이 다른 파일에도 있다 — {bad}. 정본은 {d['where']} 다"] if bad else []


@pytest.mark.parametrize("name", sorted(SITES))
def test_each_site_matches_its_declaration(name: str):
    """「옮겼다」면 표식이 없고, 「안 옮긴다」면 있다."""
    bad = site_faults(SITES[name])
    assert not bad, f"{name}: " + "\n  ".join(bad)


@pytest.mark.parametrize("name", sorted(SITES))
def test_no_site_has_a_copy_elsewhere(name: str):
    """같은 표식이 선언 밖 파일에 서면 운다 — 새 사본이다."""
    bad = copy_faults(SITES[name], _files())
    assert not bad, f"{name}: " + "\n  ".join(bad)


def test_the_judges_bite_a_planted_fault():
    """★ **카나리아.** 합성 선언으로 두 판별식을 양쪽으로 민다 — 안 그러면
    「전부 초록」이 제가 보고 있다는 것을 증명하지 못한다(§445)."""
    # ① 옮겼다고 적었는데 표식이 **있다** → 운다
    bad = site_faults({"where": "tests/test_handrolled.py", "mark": r"^SITES",
                       "moved": True, "dep": "networkx"})
    assert bad and "돌아왔다" in bad[0], f"손 판이 돌아온 것을 안 댄다 — {bad}"
    # ② 같은 선언인데 안 옮긴다 → **안 운다**
    assert not site_faults({"where": "tests/test_handrolled.py", "mark": r"^SITES",
                            "moved": False, "dep": "networkx"}), "멀쩡한데 운다"
    # ③ 안 옮긴다고 적었는데 표식이 **없다** → 운다
    bad = site_faults({"where": "tests/test_handrolled.py", "mark": r"^없는표식임",
                       "moved": False, "dep": "networkx"})
    assert bad and "사라졌다" in bad[0], f"죽은 선언을 안 댄다 — {bad}"
    # ④ 없는 파일 → 운다
    assert site_faults({"where": "tools/없다.py", "mark": r"x",
                        "moved": False, "dep": "networkx"}), "없는 파일을 안 댄다"
    # ⑤ 사본 판별 — 선언 밖에 같은 표식이 있으면 운다
    d = {"where": "tools/kpi.py", "mark": r"^import json", "moved": False,
         "dep": "networkx"}
    assert copy_faults(d, _files()), "선언 밖 사본을 안 댄다"
    # ⑥ 그리고 그 표식이 **그 파일에만** 있으면 안 운다
    assert not copy_faults({**d, "mark": r"def _hop_edges"}, _files()), \
        "제 파일에만 있는 표식을 사본으로 센다"


def test_the_universe_is_not_empty():
    """★ 훑는 우주가 비면 위 둘이 전부 조용히 통과한다(빈 그물)."""
    fs = _files()
    assert len(fs) > 200, f"파일을 {len(fs)}개만 모았다 — `SCAN` 이 죽었다"
    out = {p.resolve() for p in fs}
    miss = [n for n, d in SITES.items() if (ROOT / d["where"]).resolve() not in out]
    assert not miss, f"선언한 자리가 우주 밖이다 — {miss}. `SCAN` 을 넓혀라"


def test_every_declaration_names_a_declared_dependency():
    """`dep` 이 **실제로 선언된** 의존성인가. 없는 이름을 적으면 그 사유가 거짓이다."""
    decl = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bad = []
    for name, d in SITES.items():
        dep = d["dep"]
        if dep.startswith("("):          # 「없다」를 적은 자리
            continue
        if not re.search(rf'^\s*"{re.escape(dep)}[>=<\[]', decl, re.M):
            bad.append(f"{name}: `{dep}` 가 `pyproject.toml` 에 없다")
    assert not bad, "\n  ".join(["선언 안 된 의존성을 사유로 든다:", *bad])


def mid_faults(files: list[Path], root: Path = ROOT,
               ok: dict[str, tuple[int, str]] | None = None) -> list[str]:
    """손 중앙값 색인이 **허용 목록 밖**이거나 **수가 늘었나.** 비면 산다."""
    ok = MID_OK if ok is None else ok
    bad = []
    seen: dict[str, int] = {}
    for p in files:
        n = len(MID_INDEX.findall(p.read_text(encoding="utf-8")))
        if n:
            seen[p.relative_to(root).as_posix()] = n
    for f, n in sorted(seen.items()):
        if f not in ok:
            bad.append(f"{f}: 가운데 원소를 {n}번 집는다 — 중앙값이면"
                       " `statistics.median` 이 정본이다(짝수 길이에서 다른 수다)."
                       " 중앙값이 아니면 `MID_OK` 에 수와 사유를 적어라")
        elif n != ok[f][0]:
            bad.append(f"{f}: {ok[f][0]}번으로 적혀 있는데 {n}번이다 —"
                       " 새로 선 자리가 중앙값인지 보고 수를 고쳐라")
    for f in sorted(ok):
        if f not in seen:
            bad.append(f"{f}: 허용 목록에 있는데 그 꼴이 없다 — 죽은 선언이다(§370)")
    return bad


def test_no_hand_rolled_median_outside_the_allow_list():
    """★ **자리 하나가 아니라 꼴을 금지한다.** §471 이 손 중앙값 다섯을 옮겼고,
    다섯을 옮기는 것으로 끝내면 여섯째가 내일 선다 — 분모를 든다."""
    bad = mid_faults(_files())
    assert not bad, "\n  ".join(["손으로 센 중앙값:", *bad])


def test_the_median_judge_bites_a_planted_fault():
    """★ 카나리아 — 위 판별식도 양쪽으로 민다."""
    fs = _files()
    # ① 허용 목록을 비우면 **셋 다** 걸린다
    assert len(mid_faults(fs, ok={})) == 3, "허용 목록 밖을 안 댄다"
    # ② 수를 틀리게 적으면 걸린다
    one = {"tools/bridge_audit.py": (9, "거짓 수")}
    assert any("9번으로 적혀 있는데" in b for b in mid_faults(fs, ok=one)), \
        "수가 틀린 것을 안 댄다"
    # ③ 없는 파일을 올려 두면 죽은 선언으로 걸린다
    dead = {**MID_OK, "tools/없다.py": (1, "없다")}
    assert any("죽은 선언" in b for b in mid_faults(fs, ok=dead)), \
        "죽은 선언을 안 댄다"


def test_every_site_states_a_reason():
    """사유가 **본체다.** 비거나 한 줄짜리면 그것은 결정이 아니다."""
    thin = [n for n, d in SITES.items() if len(" ".join(d["why"].split())) < 60]
    assert not thin, f"사유가 얇다 — {thin}. 왜 옮겼는지/왜 안 옮기는지를 적어라"
