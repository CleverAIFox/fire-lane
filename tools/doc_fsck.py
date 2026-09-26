#!/usr/bin/env python3
"""
doc_fsck.py — 문서가 하는 말과 실물이 어긋나는 곳을 여덟만 본다.

── 왜 생겼나 ───────────────────────────────────────────────────
강제자 23종이 전부 **문서 ↔ 실물** 한 방향이었다. `docnum_check` 는 숫자를,
`test_docref` 는 절 참조를, `golden` 은 산출물을 본다. **문서 ↔ 문서** 를 보는
것이 하나도 없었고, 2026-09-01 에 그 자리에서 넷이 한꺼번에 나왔다.

    src/firelane/README.md 의 대장 예시가 `url` `license` `retrieved` 를 든다
        → datasets 41개 중 그 셋을 쓰는 항목이 0건이다
    web/config.js 가 web/assets/vehicles/profiles.json 을 fetch 한다
        → 저장소에 그 파일이 없다. clone 한 사람은 제원 칸이 빈다
    sources.yaml 이 turn_radius 를 "7종 전수 확인 0건" 으로 선언한다
        → profiles.json 은 7300~11889 를 갖고 있다
    layers.field 가 "재취득 불가한 실측" 이라고 선언한다
        → 재취득 가능한 공공데이터 CSV 가 거기 들어와 있고 대장에도 없다

넷 다 **읽으면 보이는데 아무도 안 읽었다.** `§79` 가 적은 형태 그대로다.

── 안 하는 것 ──────────────────────────────────────────────────
★ **자연어 모순은 잡지 않는다.** "A 문서와 B 문서가 다른 말을 한다" 를 기계가
  판정하려면 두 서술의 의미를 비교해야 하고, 그것은 이 도구의 범위가 아니다.
  여기서 보는 것은 **구조**뿐이다 — 키 목록 · 파일 경로 · 부재 선언 · 등재 ·
  만료 · 표지 날짜 · **셸 명령** · **기한**. 판단이 아니라 대조다.

★ 정본이 어느 쪽인지도 판정하지 않는다. 어긋난 자리를 짚고 사람에게 넘긴다.
  최신이 정본인 것이 보통이지만 그 판단은 사람이 한다.

IN    src/firelane/README.md · sources.yaml · docs/*.md · web/ · data/field
OUT   없음 (검사). 어긋나면 1
PARAM FIELD_EXEMPT — 등재 유예 목록. 비우는 것이 목표다
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# ★ 2026-09-26 (§258-19 · PLAN #136 닫힘). 프로브 셋을 `tools/docfsck/` 로 내렸다 —
#   664줄이 상한(600)을 넘었다. **진입점은 여기 하나**이고 `CHECKS` 표도 여기 있다.
#   「어느 파일에 있나」가 기억거리가 되는 문제(§18-3)는 **프로브 번호가 곧 파일
#   이름**이라 안 생긴다(③ absent · ⑤ expiry · ⑥ docx_revised).
from docfsck import _today
from docfsck.absent import check_absent
from docfsck.docx_revised import check_docx_revised
from docfsck.expiry import check_expiry

from firelane import generated

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"
PIPE_README = ROOT / "src/firelane/README.md"

# ★ 등재가 아직 안 된 field 파일. **늘리지 마라.** 여기 있는 동안은 그 파일이
#   무엇인지 저장소가 설명하지 못한다. PLAN 이 이 목록의 처리를 든다.
FIELD_EXEMPT = {
    "fieldsheet.md",      # 들고 나가는 종이. 코드 소비자가 없다(DECISIONS §243)
    # ── 2026-09-03. 네이버 산출 넷(DECISIONS §42)을 지웠다.
    #
    # ★ **저장소에는 한 번도 없었다.** 실물은 SSD 의 `data/field/` 에 있었고
    #   그것은 `FIRE_LANE_DATA`(fire-lane-data/)의 **형제**라 어떤 선언에도
    #   안 들어간다. `paths.FIELD` 는 저장소 `data/field` 를 가리킨다
    #   (paths.py:128 — 2026-08 이동 기록). 옮기고 원본을 안 지운 것이다.
    #
    # ★ 그래서 이 EXEMPT 가 **없는 파일을 면제하고 있었다.** 목록이 실물보다
    #   넓으면 그 목록은 방패가 아니라 사각지대다(오늘 감사 A-4 와 같은 형태).
    #
    # ★ 지운 근거 — 봉인·해제 도구 셋이 §41 에서 삭제돼 값을 풀 수도 없다.
    #   field 는 재생성 불가 등급이지만 읽을 수 없는 봉인은 자료가 아니다.
    #
    # ★ 재발 방지 — `scan_data §7` 이 `FIRE_LANE_DATA` 의 형제를 훑는다.
}

# ★ 한시 유예. **늘리지 마라.** 사유와 해소 조건을 함께 적는다(§80 과 같은 형태).
PATH_EXEMPT = {
    # 2026-09-01. 파일이 광인사 그램에만 있다. UI 담당이 커밋하면 해소된다.
    # ★ 2026-09-26 사유 정정 (§258-18). 종전에는 「`config.js:327` · `vehicle.js:187`
    #   이 fetch 하고, 없으면 화면이 "제원 미확인" 만 띄운다」고 적혀 있었다.
    #   **둘 다 죽었다** — `vehicle.js` 는 옛 지도와 함께 걷어냈고(2026-09-22),
    #   `web/config.js` 는 **어떤 HTML 도 로드하지 않는다**(전수 확인). 즉 브라우저는
    #   이 파일을 부르지 않으며 화면에 미치는 영향이 0이다.
    #   실제 유일한 독자는 `src/firelane/publish_fleet.py` 이고, 없으면 그 발행기가
    #   전장을 못 채운다 — 그것이 지금의 진짜 대가다.
    "web/assets/vehicles/profiles.json",
    # ★ 2026-09-22. `web/key.js` 를 뺐다 — 옛 지도와 함께 생성을 멈췄다. 이제 문서가 그 경로를
    #   적으면 **낡은 서술**이라 울어야 한다.
}

# ★ 2026-09-25 (§258). 생성물은 「없다」가 아니라 「아직 안 구웠다」다 — 표와 판정은
#   `firelane.generated.DOC_ABSENT` · `dead_claims()` 가 든다(생성물 지식의 한 문).
# 경로 참조를 찾을 때 저장소 안인 것만 본다. data/raw · norm · landing ·
# interim · _quarantine 은 외장 SSD 라 여기서 존재를 확인할 수 없고,
# data/processed 는 재생성물이라 clone 직후에는 없는 것이 정상이다.
REPO_DIRS = ("web", "src", "tools", "tests", "docs", ".github",
             "data/field", "data/golden", "data/baseline")
PATH_RX = re.compile(
    r"(?<![\w/.-])(" + "|".join(d.replace("/", r"/") for d in REPO_DIRS)
    + r")/[\w./-]+\.[A-Za-z0-9]{1,6}(?![\w/.-])")

# ★ DECISIONS 와 PLAN 은 보지 않는다. 전자는 **경위**라 폐기한 도구를 과거형
#   으로 적는 것이 정상이고(`tools/docfix_20260817.py` 는 지운 것이 맞다),
#   후자는 **계획**이라 아직 없는 파일을 가리키는 것이 정상이다. 여기서 보는
#   것은 "지금 그렇게 동작한다" 고 말하는 문서와 설정뿐이다.
# ★ 2026-09-22. `web/js/**/*.js` 를 뺐다 — 옛 지도를 걷어냈다.
SCAN_GLOBS = ("docs/MASTER.md", "sources.yaml", "web/config.js",
              "src/firelane/README.md", "README.md",
              ".github/CODEOWNERS")


def _ledger() -> dict:
    return yaml.safe_load(LEDGER.read_text(encoding="utf-8"))


# ── 1. 스키마 — 문서가 드는 키 ↔ 실제 쓰는 키 ────────────────────
def check_schema(led: dict) -> list[str]:
    """대장 예시가 든 키와 실물 41개가 쓰는 키를 센다."""
    blocks = re.findall(r"```yaml\n(.*?)```", PIPE_README.read_text(encoding="utf-8"),
                        re.S)
    documented: set[str] = set()
    for b in blocks:
        for line in b.splitlines():
            m = re.match(r"^\s{4}([a-z_]+):", line)
            if m:
                documented.add(m.group(1))
    if not documented:
        return ["src/firelane/README.md 에서 대장 예시 yaml 블록을 못 찾았다"]

    used: dict[str, int] = {}
    for v in led["datasets"].values():
        for k in v:
            used[k] = used.get(k, 0) + 1
    n = len(led["datasets"])

    bad = []
    dead = sorted(documented - set(used))
    if dead:
        bad.append(f"문서만 들고 실물이 0건인 키 {len(dead)}개 — {', '.join(dead)}")
    # 절반 넘게 쓰이는데 문서에 없으면 문서가 낡은 것이다
    missing = sorted(k for k, c in used.items() if c > n // 2 and k not in documented)
    if missing:
        bad.append(f"실물 과반이 쓰는데 문서에 없는 키 {len(missing)}개 — "
                   f"{', '.join(missing)}")
    return bad


# ── 2. 경로 — 문서·설정이 가리키는 저장소 파일이 실재하는가 ───────
def check_paths() -> list[str]:
    seen: dict[str, set[str]] = {}
    for g in SCAN_GLOBS:
        for f in ROOT.glob(g):
            if not f.is_file():
                continue
            for m in PATH_RX.finditer(f.read_text(encoding="utf-8", errors="ignore")):
                p = m.group(0)
                if "*" in p or "{" in p:
                    continue
                seen.setdefault(p, set()).add(str(f.relative_to(ROOT)))
    return [f"{p} 이 없다 — {' · '.join(sorted(src))} 가 가리킨다"
            for p, src in sorted(seen.items())
            if p not in PATH_EXEMPT and p not in generated.DOC_ABSENT
            and not (ROOT / p).exists()] + generated.dead_claims(ROOT)








# ── 4. 등재 — 사람이 만드는 계층의 파일이 대장에 있는가 ───────────
def check_field_ledger(led: dict) -> list[str]:
    """
    `layers.field` 는 `committed: true · regenerable: false` 로 raw 등급 보호를
    선언한다. 대장에 없으면 그 보호 목록에서 빠지고, 인수인계 때 그 파일이
    무엇인지 아무도 설명하지 못한다.

    ★ golden · baseline 은 같은 등급이지만 도구가 만드는 봉인이라 대장이 아니라
      `tools/golden.py` · `tools/baseline.py` 가 든다. 여기서 보지 않는다.
    """
    d = ROOT / "data/field"
    if not d.is_dir():
        return []
    text = LEDGER.read_text(encoding="utf-8")
    bad = []
    for f in sorted(d.iterdir()):
        if not f.is_file() or f.name in FIELD_EXEMPT:
            continue
        if f.name not in text:
            bad.append(f"data/field/{f.name} 이 대장에 없다 — "
                       "재취득 가능하면 raw 로, 실측이면 대장에 등재한다")
    return bad









# ── ⑦ 명령 ────────────────────────────────────────────────────
# 문서가 적은 셸 명령을 저장소 실물과 대조한다. 2026-09-02 감사에서 나온
# 낡음의 절반이 여기였다 — MASTER §12-5 의 `git merge origin/dev`,
# §12-8b 3·4단계의 직푸시, src/firelane/README 의 `python -m firelane.ingest`.
# 셋 다 **읽으면 보이는데 대조할 상대가 없었다**(§78 · §79).
#
# ★ DECISIONS 는 보지 않는다. 폐기한 명령을 증거로 인용하는 것이 그 문서의
#   일이고, 그것까지 세면 회고를 쓸 수 없게 된다(test_doc_style 과 같은 이유).
CMD_DOCS = ("README.md", "docs/MASTER.md", "docs/PLAN.md",
            "src/firelane/README.md", "web/README.md", "web/playbook.html",
            # ★ 2026-09-02 추가. PR 을 여는 사람이 매번 읽는 문서인데
            #   대상 밖이라 `git merge origin/dev` 두 곳이 살아 있었다.
            ".github/pull_request_template.md")


def _blocks(rel: str) -> list[list[str]]:
    """명령이 사는 자리만. .md 는 펜스·4칸 블록, .html 은 <pre>."""
    p = ROOT / rel
    if not p.exists():
        return []
    txt = p.read_text(encoding="utf-8")
    if rel.endswith(".html"):
        import html as _h
        return [_h.unescape(re.sub(r"<[^>]+>", "", m)).splitlines()
                for m in re.findall(r"<pre[^>]*>(.*?)</pre>", txt, re.S)]
    out, cur, fence = [], [], False
    for line in txt.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            if not fence and cur:
                out.append(cur)
            cur = []
            continue
        if fence:
            cur.append(line)
        elif line.startswith("    ") and line.strip():
            cur.append(line.strip())
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _protected() -> list[str]:
    """보호 브랜치를 §12-1 룰셋 표에서 읽는다. 목록을 손으로 들지 않는다."""
    t = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    return [r.replace("/**", "/") for r
            in re.findall(r"refs/heads/(\S+?)`", t)]


def _direct_stages() -> set[str]:
    """단계 직접 호출을 경고하는 모듈 = 파이프라인이 부르는 단계다."""
    d = ROOT / "src/firelane"
    return {p.stem for p in d.glob("*.py")
            if p.stem not in ("guards", "pipeline")
            and "warn_direct_call" in p.read_text(encoding="utf-8")}


def check_commands() -> list[str]:
    prot = _protected()
    stages = _direct_stages()
    tools = {p.name for p in (ROOT / "tools").iterdir()} if (
        ROOT / "tools").exists() else set()
    bad: list[str] = []
    for rel in CMD_DOCS:
        for blk in _blocks(rel):
            onprot = any(re.search(r"git switch (?:-c )?(" + "|".join(
                re.escape(b) for b in prot) + r")", ln) for ln in blk)
            for ln in blk:
                s = ln.strip()
                for b in prot:
                    if re.search(rf"git push \S+ {re.escape(b)}(\S*)?\s*$", s) \
                            or re.search(rf"git push \S+ {re.escape(b)}\S*\s*&&", s):
                        bad.append(f"{rel}  보호 브랜치 직푸시 — {s[:64]}"
                                   f"  (§12-1 이 pull_request 필수로 든다)")
                if onprot and re.search(r"git merge\b", s):
                    bad.append(f"{rel}  보호 브랜치에서 로컬 머지 — {s[:64]}"
                               f"  (원격과 갈린다. PR 로 받는다 §12-5)")
                if m := re.search(r"python -m firelane\.(\w+)", s):
                    if m.group(1) in stages:
                        bad.append(f"{rel}  단계 직접 호출 — {s[:64]}"
                                   f"  (계보가 빠진다. uv run fire-lane §14-2)")
                if "uv pip install" in s:
                    bad.append(f"{rel}  uv pip install — {s[:64]}"
                               f"  (uv sync 가 editable 로 깐다)")
                # ★ 지운 것을 지웠다고 적은 줄은 기록이다. 그것까지 세면
                #   폐기 이력을 쓸 수 없게 된다(DECISIONS 를 뺀 것과 같은 이유).
                if not re.search(r"삭제됨|폐기|제거함", s):
                    for m in re.finditer(r"tools/([\w.]+\.(?:py|mjs|sh))", s):
                        if tools and m.group(1) not in tools:
                            bad.append(f"{rel}  없는 도구 — tools/{m.group(1)}")
    return sorted(set(bad))


# ── ⑧ 기한 ────────────────────────────────────────────────────
# 날짜 없이 미룬 것은 이탈 후 아무도 안 한다(PLAN #64 가 그렇게 적는다).
# ★ 양방향이다. 기한이 지나도 울고, **이미 해소됐는데 표에 남아도 운다.**
#   해제만 검사하면 항상 통과하는 검사가 된다(§69). render_workflow 의
#   audit ↔ slots 과 같은 형태다.
#
# 문서에는 아무 표기도 넣지 않는다. 기대값은 여기 산다 — `stale-ok` ·
# `voice-ok` 에 세 번째 escape 를 더하지 않기 위해서다.
DEFERRED = (
    # ★ 2026-09-10 연기 2026-09-04 → 2026-10-05. **연기하되 사유를 적는다**
    #   (§76 — 적어두지 않은 완화는 영구가 된다).
    #
    #   사유 — 09-04 부터 09-10 까지 저장소 감사(203파일 44,899줄 · 발견
    #   232건)와 그 정리(B1 강제자 · B2 데이터 축)에 시간을 썼다. 셋 다
    #   **문서 작업**이고 코드 축이 흔들리는 동안 하면 또 낡는다 —
    #   실제로 그 사이 datasets 61→65 · retired 10→16 으로 늘어
    #   README·MASTER 숫자를 다시 고쳐야 했다.
    #
    #   10-05 인 이유 — 셋 다 대외 제출본(기획서·개요서)과 PLAN §10 이고,
    #   MVP 09-30 직후가 그 셋을 한 번에 맞출 수 있는 자리다.
    #   ★ 09-30 이 지나야 "무엇을 냈나" 가 확정되고, 그래야 개요서 표기와
    #     PLAN 우선순위를 같은 값으로 적는다. 그 전에 적으면 또 갈린다.
    #   ★ 셋을 같은 날로 묶은 것도 그 이유다. 따로 하면 서로 어긋난다.
    # ★ 2026-09-24 해소. [그림 13] 을 `render_figures.fig_xsec` 이 그리고
    #   `docx_figs --sync` 가 넣었다(§236). 아래 「이미지 작업이라 남긴다」의
    #   전제가 2026-09-23 에 뒤집혔는데(§221-1) 기한만 연장돼 있었다.
    # ★ 2026-09-16 해소. 개요서 판정 표기 · MVP 기한 둘을 지웠다. 연기 사유
    #   ("09-30 이 지나야 확정") 가 둘 다에 안 맞았다 — 표기는 대응표 한 열로
    #   끝나고, 기한은 지나기 전에 적어야 기한이다(DECISIONS §162-6).
    # ★ 2026-09-10 이관. D-30 인터뷰를 `sources.yaml` 의 `pending` 으로
    #   옮겼다(key: vehicle_spec_measured). 여기는 **우리가 할 일**을 재는
    #   기계인데 그것은 남이 하고 결과만 받는 일이라 기한이 와도 우리가
    #   할 수 있는 것이 없다 — 매주 울기만 하고, 우는 것 말고 대응이 없는
    #   빨간불은 사람이 검사를 끄게 만든다(§73).
    #
    #   `pending` 에 `fallback` 을 적었다. 결과가 안 와도 앞으로 간다 —
    #   관측 최대값으로 못박되 `wheelbase_verified` 는 false 로 남긴다.
    #   값을 정하는 것과 검증됐다고 적는 것은 다르다.
    # ★ 2026-09-03 해소. 네이버 넷을 지우고 FIELD_EXEMPT 를 걷었다.
    #   앵커가 사라졌으므로 이 줄도 함께 지운다 — 설계대로다.
)


def check_deferred() -> list[str]:
    today = _today()
    bad = []
    for due, rel, anchor, what in DEFERRED:
        p = ROOT / rel
        live = p.exists() and anchor in p.read_text(encoding="utf-8")
        if live and today > due:
            bad.append(f"기한 {due} 이 지났다 — {what} ({rel})")
        if not live:
            bad.append(f"해소됐다 — {what}. `doc_fsck.DEFERRED` 에서 그 줄을 "
                       f"지운다 (남겨두면 항상 통과하는 검사가 된다)")
    return bad



CHECKS = (
    ("① 스키마   문서가 드는 키 ↔ 실물이 쓰는 키", lambda led: check_schema(led)),
    ("② 경로     문서·설정이 가리키는 파일 ↔ 실재", lambda led: check_paths()),
    ("③ 부재선언 '없다' 고 적은 값 ↔ 실물", lambda led: check_absent(led)),
    ("④ 등재     사람이 만드는 계층 ↔ 대장", lambda led: check_field_ledger(led)),
    ("⑤ 만료     한시로 정한 것이 한시로 끝났는가", lambda led: check_expiry()),
    ("⑥ 기획서    고쳤는데 최종 수정일이 그대로인가", lambda led: check_docx_revised()),
    ("⑦ 명령     문서가 적은 셸 명령 ↔ 룰셋 · 진입점 · tools 실물", lambda led: check_commands()),
    ("⑧ 기한     미룬 것이 기한 안에 끝났는가 (양방향)", lambda led: check_deferred()),
)


def run() -> dict[str, list[str]]:
    led = _ledger()
    return {name: fn(led) for name, fn in CHECKS}


def main() -> int:
    out = run()
    total = 0
    for name, bad in out.items():
        mark = "OK " if not bad else "★  "
        print(f"{mark}{name}")
        for b in bad:
            print(f"      {b}")
        total += len(bad)
    print()
    if total:
        print(f"어긋난 곳 {total}건. 어느 쪽이 정본인지는 사람이 정한다.")
    else:
        print("문서와 실물이 구조상 일치한다.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
