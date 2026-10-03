#!/usr/bin/env python3
"""
readmecheck.py — **리드미가 적은 목록이 실물과 같은가.**

    uv run python tools/readmecheck.py
    uv run python tools/readmecheck.py --selftest

── 왜 생겼나 (DECISIONS §334) ──────────────────────────────────
PLAN #34 가 2026-09-17 에 「리드미 셋이 실물과 어긋났을 수 있다」고 적고
**거기서 멈췄다.** 사흘 뒤 실제로 둘이 틀려 있었다 —

    src/firelane/README.md   단계를 `… scope → streetlight → terrain …` 로 적는다.
                             `streetlight` 는 **단계가 아니다**(데이터 이름이다).
                             그리고 실물의 `nfa_compare` 가 목록에 없다
    web/README.md            파일 표에 `fonts/` · `404.html` · `proposal.pdf` ·
                             `navi/public/sw.js` 가 없다. 넷 다 §312·§313 이
                             넣은 것이고, **오프라인이 성립하는 근거 전체**다

★ 「어긋났을 수 있다」는 결함 기술이 아니다. 그것을 **재는 것**이 결함 기술이다.
  PLAN 은 「봐야 한다」를 적었고, 봐야 하는 일은 사람에게 남았고, 사흘 동안
  아무도 안 봤다. 그래서 이 도구가 생겼다 — **사람이 볼 일을 없앤다.**

★ 무엇을 재는가가 이 도구의 전부다. 「글이 참인가」는 못 잰다. 잴 수 있는 것은
  **리드미가 목록으로 적은 것**이고, 목록은 실물과 기계로 대조된다 —

    ① 파일 표    `web/README.md` 의 표 ↔ `web/` 의 최상위 항목
    ② 단계 목록  `src/firelane/README.md` 의 화살표 줄 ↔ `pipeline.STEPS`

IN    README.md · web/README.md · src/firelane/README.md · git 가 아는 web/** ·
      src/firelane/pipeline.py
OUT   표준출력
PARAM 없다. 면제는 `EXEMPT_WEB` 에 **사유와 함께**
밖    **산문이 참인가는 안 본다.** 「왜 그렇게 했나」는 사람이 쓰고 `docseal` 이
      「그 뒤로 안 바뀌었나」를 든다. 여기가 드는 것은 **목록**뿐이다.
      **리드미가 있어야 할 자리를 안 정한다** — 어느 폴더가 리드미를 갖는가는
      사람이 정하고, `tests/test_doc_style.py` 의 다섯 번째 문서 금지가 든다.
      **`data/baseline/*/README.md` 는 안 본다.** 그것은 당시 기록이고, 실물과
      갈리는 것이 정상이다(PLAN #34 가 같은 판단을 적었다).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from firelane import gitq

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
WEB_DOC = WEB / "README.md"
PKG_DOC = ROOT / "src" / "firelane" / "README.md"

#: `web/` 에 있으나 표에 적지 않는 것 — **사유와 함께.**
#: ★ 적는 순간 세어진다. 사유 없는 이름은 면제가 아니다.
EXEMPT_WEB: dict[str, str] = {
    "README.md":
        "이 문서 자신이다. 표가 자기를 한 줄 차지하면 그 줄은 아무것도 안 알려준다",
}


def web_entries() -> list[str] | None:
    """`web/` 의 **추적된** 최상위 항목. 폴더는 `/` 를 붙인다.

    ── 왜 추적된 것만 세나 (2026-09-30 실기) ────────────────────
    ★ 생성물은 **기계마다 있고 없다.** `web/proposal.docx` · `web/proposal.pdf` 는
      `tools/proposal_pdf.py` 가 굽는 추적 밖 파일이고 새 클론에는 없다. 그것을
      면제로 적었더니 배달 예습(빈 워크트리)에서 **「죽은 면제」로 울었다** —
      배치 P 의 포장이 거기서 거부됐다.
    ★ 같은 결함이 §319-4 다(「추적되지 않는 경로를 영향 범위로 선언했다 — 새
      클론에서 pytest 가 운다」). **그 절을 담은 배치가 같은 실수를 했다.**
      기계마다 다른 것을 관문이 들면 그 관문은 기계마다 다르게 옳다.
    ★ 그리고 이 표가 문서로서 설명하려는 것도 **저장소에 있는 것**이다. 굽는
      순간에만 생기는 파일은 그것을 굽는 행(`proposal.html`)이 이미 적는다.
    """
    # ★ 2026-10-03 (DECISIONS §372). 종전에는 `rc != 0` 에 `[]` 를 돌려줬다 —
    #   그러면 「web/ 에 아무것도 없다」가 되고 이 표 검사가 **분모 0 으로
    #   초록**이 된다. 못 물었으면 `None` 이고, 부르는 쪽이 가른다.
    stdout = gitq.ask(["-C", str(ROOT), "ls-files", "-z", "web/"])
    if stdout is None:
        return None
    top: dict[str, bool] = {}
    for rel in stdout.split("\0"):
        if not rel.startswith("web/"):
            continue
        rest = rel[len("web/"):]
        if not rest:
            continue
        head, _, tail = rest.partition("/")
        top[head] = top.get(head, False) or bool(tail)
    return sorted(f"{k}/" if v else k for k, v in top.items())


def table_names(text: str) -> set[str]:
    """리드미 표의 첫 칸에서 백틱으로 감싼 이름을 걷는다.

    ★ 표 **밖**의 백틱은 안 센다. 산문이 `config.js` 를 언급하는 것은
      「표에 있다」가 아니다 — 그것까지 세면 표를 안 고쳐도 통과한다.
    """
    got: set[str] = set()
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        first = line.split("|")[1] if line.count("|") >= 2 else ""
        for m in re.finditer(r"`([^`]+)`", first):
            got.add(m.group(1))
    return got


def covered(name: str, said: set[str]) -> bool:
    """실물 항목 `name` 이 표에 덮였는가.

    ★ 폴더는 **그 안을 가리키는 행**으로도 덮인다 —
      `assets/vehicles/profiles.json` 한 행이 `assets/` 를 설명한다.
      폴더마다 한 행을 강요하면 표가 파일 목록이 되고, 그것은 `ls` 다.
    """
    if name in said or name.rstrip("/") in said:
        return True
    return name.endswith("/") and any(s.startswith(name) for s in said)


def web_faults() -> list[str]:
    """① 파일 표 ↔ 실물."""
    if not WEB_DOC.is_file():
        return ["`web/README.md` 가 없다"]
    said = table_names(WEB_DOC.read_text(encoding="utf-8"))
    real = web_entries()
    if real is None:
        # ★ §372. 못 물었으면 **0 이라고 말하지 않는다.** 분모 0 은 초록이 된다
        return ["git 이 `web/` 목록을 못 줬다 — 이 표 검사의 분모가 없다(§372)"]
    bad = []
    for name in real:
        if name in EXEMPT_WEB or name.rstrip("/") in EXEMPT_WEB:
            continue
        if covered(name, said):
            continue
        bad.append(f"`web/{name}` 가 실물에 있는데 표에 없다 — 표에 넣거나 "
                   "`EXEMPT_WEB` 에 **사유와 함께** 적어라")
    flat = {n.rstrip("/") for n in real}
    for name in sorted(said):
        head = name.split("/")[0]
        if head and head not in flat and "/" not in name.rstrip("/"):
            bad.append(f"표가 `web/{name}` 을 적는데 실물에 없다 — 걷힌 파일이다")
    for name, why in EXEMPT_WEB.items():
        if name not in flat:
            bad.append(f"`EXEMPT_WEB` 의 `{name}` 이 실물에 없다 — 죽은 면제다 ({why[:24]}…)")
    return bad


def real_steps() -> list[str]:
    """`pipeline.py` 의 단계 이름. **파이프라인을 적재하지 않는다** —
    geopandas 가 없는 기계에서도 재야 하므로 소스를 읽는다."""
    p = ROOT / "src" / "firelane" / "pipeline.py"
    if not p.is_file():
        return []
    return re.findall(r'^    Step\("([a-z_]+)"', p.read_text(encoding="utf-8"), re.M)


def said_steps(text: str) -> list[str]:
    """리드미의 화살표 줄. 가장 긴 것 하나를 쓴다."""
    best: list[str] = []
    for line in text.splitlines():
        if "→" not in line:
            continue
        got = [x.strip().strip("`") for x in line.strip().split("→")]
        if all(re.fullmatch(r"[a-z_]+", x) for x in got) and len(got) > len(best):
            best = got
    return best


def step_faults() -> list[str]:
    """② 단계 목록 ↔ `pipeline.STEPS`."""
    if not PKG_DOC.is_file():
        return ["`src/firelane/README.md` 가 없다"]
    real = real_steps()
    if not real:
        return ["`pipeline.py` 에서 단계를 하나도 못 읽었다 — 이 검사가 빈 그물이다"]
    said = said_steps(PKG_DOC.read_text(encoding="utf-8"))
    if not said:
        return ["`src/firelane/README.md` 에 단계 목록 줄이 없다 — "
                f"실물은 {' → '.join(real)} 이다"]
    if said == real:
        return []
    return [f"단계 목록이 실물과 다르다\n"
            f"       적힘  {' → '.join(said)}\n"
            f"       실물  {' → '.join(real)}"]


def check() -> list[str]:
    real = web_entries()
    if real is None:
        return web_faults()
    print(f"web 최상위 {len(real)}개 · 면제 {len(EXEMPT_WEB)}개 · "
          f"단계 {len(real_steps())}개")
    return web_faults() + step_faults()


def selftest() -> int:
    fails = []

    # ★ 그물이 비지 않았는가 — 양쪽 다 실물을 읽는가
    got = web_entries()
    if got is None:
        fails.append("git 이 `web/` 목록을 못 줬다 — 못 물은 것이지 0 이 아니다(§372)")
        got = []
    elif not got:
        fails.append("`web/` 가 비었다 — 훑기가 실물과 갈렸다")
    # ★ **생성물을 세면 안 된다.** 기계마다 있고 없다 — 배달 예습(빈 워크트리)에서
    #   이 도구가 거기서 죽었다. 굽는 파일 이름이 목록에 들면 그 관문은 기계마다
    #   다르게 옳다(§319-4 와 같은 결함).
    for made in ("proposal.pdf", "proposal.docx"):
        if made in got:
            fails.append(f"굽는 파일 `{made}` 를 최상위 목록에 센다 — 새 클론에서 운다")
    # ★ 반대 방향 — 추적된 것은 반드시 있어야 한다
    for must in ("index.html", "navi/", "data/"):
        if must not in got:
            fails.append(f"추적된 `{must}` 를 못 찾는다 — 훑기가 git 과 갈렸다")
    if len(real_steps()) < 2:
        fails.append("단계를 둘도 못 읽는다 — 정규식이 `pipeline.py` 와 갈렸다")

    # ★ 표 밖의 백틱을 표로 세면 안 된다 — 그러면 표를 안 고쳐도 통과한다
    got = table_names("산문에서 `밖.js` 를 말한다\n| `안.js` | 뜻 |\n")
    if got != {"안.js"}:
        fails.append(f"표 안팎을 못 가른다 — {sorted(got)}")

    # ★ 첫 칸만 본다. 둘째 칸의 이름은 그 파일의 **설명**이다
    got = table_names("| `안.js` | `남.js` 가 읽는다 |\n")
    if got != {"안.js"}:
        fails.append(f"둘째 칸의 이름을 표의 항목으로 센다 — {sorted(got)}")

    # ★ 2026-09-30 의 그 결함. `streetlight` 가 끼면 잡아야 한다
    bad = said_steps("    ingest → segments → scope → streetlight → terrain → ortho → publish\n")
    if bad == real_steps():
        fails.append("틀린 단계 목록을 실물과 같다고 읽는다")
    if len(bad) != 7:
        fails.append(f"화살표 줄을 못 읽는다 — {bad}")

    # ★ 화살표가 있어도 단계 줄이 아닌 것은 안 줍는다
    if said_steps("    설명 → 다른 설명\n") != []:
        fails.append("한글 화살표 줄을 단계 목록으로 줍는다")

    # ★ 폴더 안을 가리키는 행이 그 폴더를 덮는가 — 덮지 않으면 표가 `ls` 가 된다
    if not covered("assets/", {"assets/vehicles/profiles.json"}):
        fails.append("폴더 안을 가리키는 행이 그 폴더를 못 덮는다 — 표가 `ls` 가 된다")
    # ★ 반대 방향. 이름이 비슷한 **다른** 것까지 덮으면 그물에 구멍이 난다
    if covered("assets/", {"assets_old/vehicles.json"}):
        fails.append("`assets_old/…` 가 `assets/` 를 덮는다 — 접두 비교가 너무 넓다")
    if covered("404.html", {"navi/404.html"}):
        fails.append("`navi/404.html` 이 최상위 `404.html` 을 덮는다 — 파일은 정확히 같아야 한다")

    for f in fails:
        print(f"  ✗ {f}")
    print(f"selftest {'초록' if not fails else f'{len(fails)}건 실패'} · 판별식 14")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="리드미가 적은 목록이 실물과 같은가")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    bad = check()
    if bad:
        print("\n✗ 리드미 대조")
        for b in bad:
            print(f"   {b}")
        return 1
    print("✓ 리드미 대조")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
