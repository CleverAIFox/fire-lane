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


def _today() -> str:
    """오늘(KST).

    ★ 시간대를 명시한다. `date.today()` 는 실행 머신의 시간대를 쓰는데
      CI 는 UTC 이고 사람은 KST 다. 게이트가 아홉 시간 늦게 운다.
      `.ruff-strict.toml` 의 DTZ011 이 이것을 막는다.

    ★ 계산을 한 곳에 둔다. 종전에는 `check_expiry` 안에만 있었고
      `check_deferred` 가 생기면서 두 벌이 됐다(§73 과 같은 형태).
    """
    import datetime as _dt
    return _dt.datetime.now(
        tz=_dt.timezone(_dt.timedelta(hours=9))).date().isoformat()


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "sources.yaml"
PIPE_README = ROOT / "src/firelane/README.md"

# ★ 등재가 아직 안 된 field 파일. **늘리지 마라.** 여기 있는 동안은 그 파일이
#   무엇인지 저장소가 설명하지 못한다. PLAN 이 이 목록의 처리를 든다.
FIELD_EXEMPT = {
    "fieldsheet.md",            # sources.yaml consumers 가 든다
    # ── 2026-09-02. DECISIONS §42 네이버 준-실측 실험의 산출 넷.
    #    봉인·해제 도구(naver_check · naver_page · naver_join)는 PLAN §6-8 이
    #    "삭제됨" 으로 적는다 — **도구가 없어 봉인을 풀 수도 없다.**
    #    field 는 재생성 불가 등급이라 지우지 않고 판단을 이탈 전에 둔다.
    #    해소 = 넷을 interim 으로 내리거나 대장에 등재하고 이 다섯 줄을 지운다.
    #    기한은 `DEFERRED` 가 든다(2026-09-02).
    ".naver_sealed.csv", "naver_check.csv",
    "naver_check.html", "naver_near.json",
}

# ★ 한시 유예. **늘리지 마라.** 사유와 해소 조건을 함께 적는다(§80 과 같은 형태).
PATH_EXEMPT = {
    # 2026-09-01. 파일이 광인사 그램에만 있다. UI 담당이 커밋하면 해소된다.
    #   config.js:327 · vehicle.js:187 이 fetch 하고, 없으면 화면이
    #   "제원 미확인" 만 띄운다. PLAN 이 이 항목을 든다.
    "web/assets/vehicles/profiles.json",
}

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
SCAN_GLOBS = ("docs/MASTER.md", "sources.yaml", "web/config.js",
              "web/js/**/*.js", "src/firelane/README.md", "README.md",
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
            if p not in PATH_EXEMPT and not (ROOT / p).exists()]


# ── 3. 부재 선언 — "없다" 고 적은 값이 실물에 있는가 ──────────────
def check_absent(led: dict) -> list[str]:
    """`absent:` 선언을 실물과 **양방향**으로 대조한다.

    ★ `absent` 는 "어디에도 없다" 가 아니라 **"이 출처에 없다"** 다.
      스코프가 없으면 후자로 읽히고, 2026-09-02 에 셋 다 거짓 선언으로
      드러났다 — `profiles.json` 이 커밋되자 값이 다 있었다.

    ★ 이름을 추측하지 않는다. 종전에는 `turn_radius_m` 을 camelCase 로
      바꾸고 접미를 떼어 찾았는데 실물은 `turningRadius` 였다. **우연히
      엇갈려 통과했다.** 소화전 속성이 `속성 0종` 으로 조용히 발행된 것과
      같은 형태다(DECISIONS §49). `json_key` 로 못박는다.

    판정 둘 —
        elsewhere 있음   그 파일에 json_key 가 **있어야** 한다. 없으면
                        이름이 바뀐 것이고 선언이 낡았다
        elsewhere 없음   진짜 부재. 저장소 어디에도 **없어야** 한다
    """
    entries: list[tuple[str, str, object]] = []

    def walk(node, trail: str):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "absent" and isinstance(v, dict):
                    entries.extend((trail or "(최상위)", f, s)
                                   for f, s in v.items())
                else:
                    walk(v, f"{trail}.{k}" if trail else k)

    walk(led, "")
    if not entries:
        return []

    bad: list[str] = []
    hay: list[tuple[str, str]] = []
    for g in ("web/**/*.json", "web/**/*.js", "data/field/*.csv",
              "data/processed/*.json"):
        for f in ROOT.glob(g):
            if f.is_file():
                hay.append((str(f.relative_to(ROOT)),
                            f.read_text(encoding="utf-8", errors="ignore")))

    for where, field, spec in entries:
        tag = f"{where}.absent.{field}"
        if not isinstance(spec, dict):
            bad.append(f"{tag} 이 스코프를 안 든다. `in:` · `json_key:` 를 "
                       f"적는다 — absent 는 '어디에도 없다' 가 아니라 "
                       f"'그 출처에 없다' 이다(DECISIONS §91)")
            continue
        for need in ("in", "json_key"):
            if not spec.get(need):
                bad.append(f"{tag} 에 `{need}:` 가 없다")
        key = spec.get("json_key")
        if not key:
            continue
        src = spec.get("elsewhere")
        if src:
            p = ROOT / src
            if not p.exists():
                bad.append(f"{tag}.elsewhere 가 가리키는 {src} 이 없다")
            elif f'"{key}"' not in p.read_text(encoding="utf-8",
                                               errors="ignore"):
                bad.append(f"{tag} 은 {src} 에 `{key}` 로 있다고 하는데 "
                           f"그 키가 없다. 이름이 바뀌었거나 선언이 낡았다 "
                           f"— 추측으로 메우지 않는다(§49)")
        else:
            hits = sorted({p for p, t in hay if f'"{key}"' in t})
            if hits:
                bad.append(f"{tag} 은 없다고 선언했는데 "
                           f"{' · '.join(hits[:3])} 에 `{key}` 가 있다. "
                           f"`elsewhere:` 로 어디에 있는지 적는다")
    return bad


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


# ── 5. 만료 — 한시가 한시로 끝나는가 ──────────────────────────
# ★ 오창준 이탈일. 09-02 이 마지막 근무일이고 09-08 부터 없다.
#   그날까지 bypass 를 회수하고 admin 을 축소해야 한다.
DEPARTURE = "2026-09-02"
LEAVING = "AIMasterFox"

_BANNER = """
  ████████████████████████████████████████████████████████████
  ██                                                        ██
  ██   기한이 지난 예외가 살아 있다. 이건 경고가 아니다.      ██
  ██   회수하기 전에는 이 검사가 안 풀린다.                  ██
  ██                                                        ██
  ████████████████████████████████████████████████████████████
"""

_TODO = """
  ── 할 일 (전부 끝나야 초록이 된다) ─────────────────────────
   1  GitHub 룰셋에서 bypass_actors 를 전부 비운다
        Settings → Rules → main · dev · part/* → Bypass list 비우기
        확인:  uv run python tools/ruleset_check.py
   2  tools/ruleset_check.py 의 ADMINS 에서 이탈자를 뺀다
   3  @woongtopia/gis 팀에서 이탈자를 뺀다
        CODEOWNERS 파일은 고치지 않는다 — 팀에서 빼면 리뷰가 자동으로
        남은 gis 팀원에게 넘어간다(MASTER §8)
   4  web/playbook.html 의 BYPASS 카드를 통째로 지운다
   5  MASTER §12-1 의 회수일 서술을 지운다
   6  doc_fsck.py 의 DEPARTURE · LEAVING 두 줄을 지운다  ← 이 검사를 끈다
  ────────────────────────────────────────────────────────────
"""


def check_expiry() -> list[str]:
    """기한이 지난 예외가 남아 있는가.

    ★ 2026-09-02. `§80` 이 bypass 를 **한시** 부여하고 회수를 사람 기억에
      맡겼다. 한시가 한시로 끝나려면 시계가 있어야 한다. 여기 있는 것은
      알림이 아니라 **게이트**다 — 날짜가 지나면 CI 가 빨간불이 되고
      회수하기 전에는 안 풀린다.

    ★ 날짜만 보지 않는다. **회수됐는지까지 본다** —
      `ruleset_check.ADMINS` 에 이탈자가 남아 있으면 실패한다. 날짜만
      보면 "카드를 지웠으니 됐다" 로 끝나고 룰셋은 그대로 남는다.
      룰셋 실물은 관리자 토큰이 있어야 읽으므로 `ruleset_check` 가 보고,
      이쪽은 **그 도구가 무엇을 기대하는지**를 본다.

    ★ 실패 메시지를 크게 낸다. 빨간 줄 하나면 다른 팀원이 무슨 일인지
      모르고 당황한다. 무엇을 해야 하는지가 화면에 다 있어야 한다.
    """
    today = _today()
    bad, seen = [], {}

    for g in ("web/*.html", "docs/*.md"):
        for f in ROOT.glob(g):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for d in re.findall(r'data-expires="(\d{4}-\d{2}-\d{2})"', txt):
                seen.setdefault(d, []).append(str(f.relative_to(ROOT)))

    # 화면과 MASTER 가 같은 날짜를 드는가 — 지나기 전에도 본다
    mst = (ROOT / "docs/MASTER.md").read_text(encoding="utf-8")
    m = re.search(r"(\d{4}-\d{2}-\d{2})\s*[에]?\s*회수", mst)
    if seen and DEPARTURE not in seen:
        bad.append(f"화면의 data-expires 는 {' · '.join(sorted(seen))} 인데 "
                   f"이탈일은 {DEPARTURE} 다. 하나로 맞춰라")
    if m and m.group(1) != DEPARTURE:
        bad.append(f"MASTER 는 회수일을 {m.group(1)} 로 적는데 "
                   f"이탈일은 {DEPARTURE} 다")

    if today <= DEPARTURE:
        return bad

    # ── 기한이 지났다. 여기서부터는 크게 운다 ──────────────────
    bad.append(_BANNER.rstrip())
    bad.append(f"이탈일 {DEPARTURE} 이 지났다 (오늘 {today}).")

    rs = ROOT / "tools/ruleset_check.py"
    if rs.exists() and LEAVING in rs.read_text(encoding="utf-8"):
        bad.append(f"★ ruleset_check.ADMINS 에 {LEAVING} 이 아직 있다 — "
                   "룰셋을 회수하지 않았거나 명단을 안 고쳤다")
    for d, where in sorted(seen.items()):
        if d <= DEPARTURE:
            bad.append(f"★ {' · '.join(where)} 의 BYPASS 카드가 남아 있다")
    if m:
        bad.append("★ MASTER §12-1 에 회수일 서술이 남아 있다")
    bad.append(_TODO.rstrip())
    return bad


# ── 6. 기획서 최종 수정일 ──────────────────────────────────────
def check_docx_revised() -> list[str]:
    """기획서를 고쳤는데 표지의 최종 수정일이 그대로인가.

    ★ 2026-09-02. 표지가 `2026. 08. 14.` 하나만 들고 있었고 그 뒤로 다섯 번
      고쳤다. **외부가 읽는 유일한 문서라 날짜가 곧 신뢰다** — 심사위원이
      8월 문서를 받으면 그동안 아무것도 안 한 것으로 읽는다.

    ★ 파일 mtime 이 아니라 **git 이 아는 마지막 수정 커밋일**과 비교한다.
      mtime 은 clone 하면 전부 오늘이 된다.
    """
    import subprocess
    docs = list(ROOT.glob("docs/*.docx"))
    if not docs:
        return []
    f = docs[0]
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ad", "--date=short", "--", str(f)],
            cwd=ROOT, capture_output=True, text=True, timeout=10)
        last = r.stdout.strip()
    except Exception:                                     # noqa: BLE001
        return []
    if not last:
        return []
    try:
        import docx as _dx
        txt = "\n".join(x.text for x in _dx.Document(str(f)).paragraphs[:40])
    except Exception:                                     # noqa: BLE001
        return []
    shown = re.findall(r"20\d\d\.\s*\d{1,2}\.\s*\d{1,2}", txt)
    if not shown:
        return [f"{f.name} 표지에 날짜가 없다. 작성일과 최종 수정일을 적어라"]
    norm = {re.sub(r"[.\s]", "", s) for s in shown}
    if re.sub(r"-", "", last) not in norm:
        return [f"{f.name} 의 마지막 수정 커밋은 {last} 인데 표지는 "
                f"{' · '.join(shown)} 만 든다. 최종 수정일을 갱신해라"]
    return []


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
    ("2026-09-04", "docs/PLAN.md",
     "그림 자체가 여전히 반경 5m 원을 그린다", "기획서 [그림 13] 재생성"),
    ("2026-09-04", "docs/PLAN.md",
     "개요서가 §10-2 확정 전에 쓰였다", "개요서 판정 표기를 4종으로"),
    ("2026-09-04", "docs/PLAN.md",
     "PLAN §10 우선순위에 그 날짜를 넣는 것만 남았다", "MVP 09-30 을 PLAN §10 에"),
    ("2026-09-02", "docs/PLAN.md",
     "한 달째 미착수이고 공문도 안 나갔다", "D-30 인터뷰 일정 확정"),
    # ★ 앵커가 이 파일 자신이다. 넷을 치우고 FIELD_EXEMPT 를 비우면
    #   이 줄이 "해소됐다" 로 울어 스스로 지워지기를 요구한다.
    ("2026-09-02", "tools/doc_fsck.py",
     '".naver_sealed.csv"', "data/field 네이버 잔류 4건 처분 (PLAN §6-8)"),
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
