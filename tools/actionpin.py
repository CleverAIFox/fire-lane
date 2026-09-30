#!/usr/bin/env python3
"""
actionpin.py — **액션이 어느 코드로 도는가.** 고정과 시간 상한.

    uv run python tools/actionpin.py            판정 (verify.sh · CI) — 그물만 읽는다
    uv run python tools/actionpin.py --write     태그를 풀어 그 자리에서 고친다 (네트워크)
    uv run python tools/actionpin.py --selftest  ★ 판정기가 살아 있나

── 왜 생겼나 (PLAN §13 W13-6 · DECISIONS §324) ─────────────────
`uses: actions/checkout@v7` 은 **코드를 가리키지 않는다.** `v7` 은 옮겨 다니는
이름표라 그 이름표를 쥔 쪽이 언제든 다른 커밋에 다시 붙일 수 있고, 그러면
**우리 CI 가 조용히 다른 코드를 돌린다.** 우리가 고친 것이 없는데 결과가
바뀌고, 바뀐 줄도 모른다 — 족 1(무음 통과)이다.

같은 자리에서 둘째가 걸린다. 작업에 `timeout-minutes` 가 없으면 GitHub 기본
상한(**6시간**)까지 매달린다. `verify.sh` 는 제 안에서 단계마다 시간을 재는데
CI 쪽에는 그 그물이 없었다.

★ 그래서 이 도구가 무는 것은 **인스턴스가 아니라 족**이다. 워크플로를 한 번
  고정하는 것은 배치가 하고, 「다음에 누가 태그로 되돌리는 것」을 막는 것이
  이 검사다(PLAN §13-5 규칙 1). 워크플로가 새로 생겨도 자동으로 물린다.

── 판정 셋 ────────────────────────────────────────────────────
    ① 고정    저장소 밖 `uses:` 가 40자리 커밋 지문인가
    ② 표기    그 줄 꼬리에 `# <태그>` 가 있는가
    ③ 상한    모든 작업이 `timeout-minutes` 를 갖는가

★ ②가 왜 판정인가 — 지문만 있으면 **사람이 어느 판인지 못 읽는다.** 못 읽으면
  갱신을 못 하고, 갱신을 못 하면 반년 뒤 「무서워서 못 건드리는 줄」이 된다.
  그것은 고정의 목적(아는 코드를 돌린다)과 반대다.

★ ③에서 **재사용 워크플로 호출 작업(`uses:` 인 작업)은 뺀다.** GitHub 가 그
  작업에 `timeout-minutes` 를 거부한다 — 넣으면 워크플로가 통째로 안 돈다.
  상한은 불려가는 쪽 작업들이 각자 든다.

IN    .github/workflows/*.yml · .github/workflows/*.yaml
OUT   표준출력 (판정) · --write 면 워크플로 파일
밖    **액션이 안전한가는 안 본다.** 이 검사가 드는 것은 「우리가 아는 코드가
      도는가」다. 어느 액션을 쓸지는 사람이 정한다.
      **판을 올리지 않는다.** `--write` 는 **적힌 태그**를 풀 뿐이고, `v7` 을
      `v8` 로 올리는 것은 사람의 판단이다.
      **저장소 안 액션(`./…`)은 안 본다.** 우리 트리에 있으므로 이미 고정이다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows"

#: `uses:` 한 줄. 꼬리 주석을 따로 잡는다 — 그것이 판정 ②다.
USES = re.compile(r"^(?P<head>\s*(?:-\s+)?uses:\s*)(?P<ref>\S+)(?P<tail>\s*#.*)?$")

#: 40자리 커밋 지문.
SHA = re.compile(r"^[0-9a-f]{40}$")

#: 꼬리 주석에서 읽는 태그. `# v7` · `# v7 — 왜` 둘 다 받는다.
TAG = re.compile(r"#\s*(?P<tag>v[\w.\-]+|[\w.\-]*\d[\w.\-]*)")


def workflows() -> list[Path]:
    if not WF.is_dir():
        return []
    return sorted(p for p in WF.iterdir()
                  if p.suffix in (".yml", ".yaml") and p.is_file())


def where(p: Path) -> str:
    """보고용 경로. ★ 트리 밖(시험의 임시 폴더)이면 `relative_to` 가 죽는다 —
    판정기가 **제 시험 안에서만 죽는** 것이 제일 나쁘다."""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return p.name


def is_local(ref: str) -> bool:
    """저장소 안 액션·재사용 워크플로. 이미 우리 트리라 고정할 것이 없다."""
    return ref.startswith(("./", "../"))


def split_ref(ref: str) -> tuple[str, str]:
    """`owner/repo@ref` → (`owner/repo`, `ref`). `@` 가 없으면 판이 없는 것이다."""
    repo, _, rev = ref.partition("@")
    return repo, rev


# ── ① · ② 고정과 표기 ──────────────────────────────────────────

def pin_faults() -> list[str]:
    out: list[str] = []
    for p in workflows():
        rel = where(p)
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            m = USES.match(line)
            if not m:
                continue
            ref = m.group("ref").strip("'\"")
            if is_local(ref):
                continue
            repo, rev = split_ref(ref)
            if not rev:
                out.append(f"{rel}:{n} `{ref}` — 판이 없다. 기본 가지가 돈다")
                continue
            if not SHA.match(rev):
                out.append(f"{rel}:{n} `{repo}@{rev}` — **떠 있는 이름표다.** "
                           f"그 이름표를 옮기면 다른 코드가 돈다")
                continue
            if not (m.group("tail") and TAG.search(m.group("tail"))):
                out.append(f"{rel}:{n} `{repo}` — 지문만 있고 **어느 판인지 안 적혔다.** "
                           f"꼬리에 `# v7` 처럼 적어라. 못 읽으면 갱신을 못 한다")
    return out


# ── ③ 시간 상한 ────────────────────────────────────────────────

def jobs(text: str) -> dict[str, list[str]]:
    """`jobs:` 아래 두 칸 들여쓴 열쇠 → 그 블록의 줄들.

    ★ YAML 파서를 안 쓴다. `on:` 이 YAML 1.1 에서 `True` 로 읽히는 등
      워크플로는 파서마다 다르게 보이고, 여기서 묻는 것은 **줄의 생김새**다.
    """
    lines = text.splitlines()
    out: dict[str, list[str]] = {}
    top = None
    cur: str | None = None
    for line in lines:
        if line and not line[0].isspace():
            top = line.split(":", 1)[0]
            cur = None
            continue
        if top != "jobs":
            continue
        m = re.match(r"^  ([A-Za-z_][\w\-]*):\s*$", line)
        if m:
            cur = m.group(1)
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def calls_workflow(block: list[str]) -> bool:
    """재사용 워크플로 호출 작업인가. **GitHub 가 여기 상한을 거부한다.**"""
    return any(re.match(r"^    uses:\s*\S", ln) for ln in block)


def timeout_faults() -> list[str]:
    out: list[str] = []
    for p in workflows():
        rel = where(p)
        for name, block in jobs(p.read_text(encoding="utf-8")).items():
            if calls_workflow(block):
                continue
            if not any(re.match(r"^    timeout-minutes:\s*\d+", ln) for ln in block):
                out.append(f"{rel} · 작업 `{name}` — `timeout-minutes` 가 없다. "
                           f"매달리면 **기본 6시간**을 태운다")
    return out


# ── --write ───────────────────────────────────────────────────

def resolve(repo: str, tag: str) -> str:
    """`git ls-remote` 로 태그를 커밋 지문으로 푼다. 네트워크가 필요하다.

    ★ 주석 태그(annotated)면 `^{}` 줄이 **가리키는 커밋**이다. 그 줄을 안 보면
      태그 개체의 지문을 박게 되고, GitHub 는 그것으로 액션을 못 받는다.
    """
    r = subprocess.run(  # noqa: S603 — PATH 의 git 이다
        ["git", "ls-remote", f"https://github.com/{repo}",  # noqa: S607 — PATH 의 git 이다
         f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"{repo}@{tag} — ls-remote 실패: {r.stderr.strip()[:120]}")
    peeled = plain = ""
    for ln in r.stdout.splitlines():
        sha, _, ref = ln.partition("\t")
        if ref.endswith("^{}"):
            peeled = sha
        elif ref:
            plain = sha
    got = peeled or plain
    if not SHA.match(got):
        raise RuntimeError(f"{repo}@{tag} — 그 태그가 없다")
    return got


def write() -> int:
    """적힌 태그를 지문으로 바꾼다. **판은 안 올린다.**"""
    cache: dict[tuple[str, str], str] = {}
    changed = 0
    for p in workflows():
        lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        hit = False
        for i, line in enumerate(lines):
            m = USES.match(line.rstrip("\n"))
            if not m:
                continue
            ref = m.group("ref").strip("'\"")
            if is_local(ref):
                continue
            repo, rev = split_ref(ref)
            tail = m.group("tail") or ""
            if SHA.match(rev):
                # 이미 고정. 표기만 없으면 그것은 **사람이 적을 일**이다 —
                # 어느 태그였는지 이 도구가 짐작하면 거짓을 적는다.
                continue
            if not rev:
                print(f"  ✗ {p.name} `{ref}` — 판이 없다. 사람이 태그를 적어라")
                continue
            key = (repo, rev)
            if key not in cache:
                cache[key] = resolve(repo, rev)
            note = tail if TAG.search(tail) else f"  # {rev}"
            lines[i] = f"{m.group('head')}{repo}@{cache[key]}{note}\n"
            print(f"  · {p.name}  {repo}@{rev} → {cache[key][:12]}…")
            hit, changed = True, changed + 1
        if hit:
            p.write_text("".join(lines), encoding="utf-8")
    print(f"\n고정 {changed}줄" if changed else "\n바꿀 것이 없다")
    return 0


# ── 판정 · 자기검사 ────────────────────────────────────────────

def check() -> int:
    wfs = workflows()
    print(f"워크플로 {len(wfs)}개 — {' · '.join(p.name for p in wfs)}")
    if not wfs:
        print("✗ 워크플로가 하나도 없다 — **빈 그물이다.** 경로가 맞는지 봐라")
        return 1
    pins, tos = pin_faults(), timeout_faults()
    for f in pins:
        print(f"  ✗ {f}")
    for f in tos:
        print(f"  ✗ {f}")
    if pins or tos:
        print(f"\n✗ 고정 {len(pins)}건 · 상한 {len(tos)}건")
        print("  uv run python tools/actionpin.py --write   (고정은 도구가 한다)")
        return 1
    n = sum(1 for p in wfs for ln in p.read_text(encoding="utf-8").splitlines()
            if (m := USES.match(ln)) and not is_local(m.group("ref").strip("'\"")))
    print(f"✓ 밖 액션 {n}줄 전부 지문 고정 · 작업 전부 시간 상한")
    return 0


def selftest() -> int:
    """★ 셋을 실제로 가르는가. 파일을 안 읽고 합성 문자열로 본다."""
    fails: list[str] = []

    def uses(line: str) -> tuple[str, str, str]:
        m = USES.match(line)
        assert m, line
        return (m.group("ref"), m.group("tail") or "", m.group("head"))

    sha = "3d3c42e5aac5ba805825da76410c181273ba90b1"
    ref, tail, _ = uses(f"      - uses: actions/checkout@{sha}  # v7")
    if not SHA.match(split_ref(ref)[1]):
        fails.append("고정된 줄을 안 고정으로 읽는다")
    if not TAG.search(tail):
        fails.append("꼬리의 태그를 못 읽는다 — 표기 판정이 헛돈다")
    if TAG.search(uses("      - uses: a/b@" + sha)[1]):
        fails.append("꼬리가 없는데 태그가 있다고 읽는다 — 빈 그물")
    if SHA.match(split_ref(uses("      - uses: actions/checkout@v7")[0])[1]):
        fails.append("떠 있는 태그를 지문으로 읽는다 — **이 도구의 존재 이유다**")
    if not is_local(uses("      - uses: ./.github/actions/stage-site")[0]):
        fails.append("저장소 안 액션을 밖으로 읽는다")
    if SHA.match("3D3C42E5AAC5BA805825DA76410C181273BA90B1"):
        fails.append("대문자 지문을 받는다 — GitHub 는 소문자만 쓴다")

    # ★ ③ 작업 가르기. 재사용 호출을 안 빼면 워크플로가 통째로 안 돈다.
    sample = ("name: x\non:\n  push:\njobs:\n  gate:\n    uses: ./.github/workflows/c.yml\n"
              "  build:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 30\n"
              "  bare:\n    runs-on: ubuntu-24.04\n    steps:\n      - run: x\n")
    js = jobs(sample)
    if set(js) != {"gate", "build", "bare"}:
        fails.append(f"작업을 못 가른다 — {sorted(js)}")
    if not calls_workflow(js.get("gate", [])):
        fails.append("재사용 호출 작업을 못 가른다 — 거기 상한을 넣으면 CI 가 죽는다")
    if calls_workflow(js.get("build", [])):
        fails.append("보통 작업을 재사용 호출로 읽는다")
    if "on" in js:
        fails.append("`jobs:` 밖의 열쇠를 작업으로 읽는다")

    # ★ 반대 방향 — 실물에서 무엇이든 세는가. 0이면 그물이 비었다.
    if not workflows():
        fails.append("워크플로를 하나도 못 찾는다 — 빈 그물이다")

    for f in fails:
        print(f"  ✗ {f}")
    print("✓ 자기검사 통과 · 판별식 11" if not fails else f"✗ {len(fails)}건")
    return 1 if fails else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="적힌 태그를 커밋 지문으로 바꾼다 (네트워크)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.write:
        return write()
    return check()


if __name__ == "__main__":
    sys.exit(main())
