#!/usr/bin/env python3
"""
layerfsck.py — `sources.yaml` 의 **계층 선언**과 디스크·git·기계 설정을 대조한다.

    python -m firelane.datalog fsck       ← 부르는 자리는 datalog 하나다

★ 2026-09-28. `datalog.py` 가 615줄로 상한 600 을 넘겨 여기로 나왔다(§283-6).
  `cmd_fsck` 는 `datalog` 의 이름 중 `ROOT` 하나만 쓰던 **자족 덩어리**였다 —
  대장을 읽고 쓰는 일(record · graph · impact · check)과 계층 실물을 감사하는
  일은 애초에 다른 일이다. 길이가 그것을 말해 주었다.

★ 명령 이름은 `datalog fsck` 로 그대로 둔다. **부르는 자리가 둘이 되면
  안 된다**(2족). `datalog.COMMANDS` 가 여기 함수를 가리킨다.

IN    sources.yaml(layers) · 디스크 · git · .gitignore
OUT   없음 (검사 · 어긋나면 종료 1)
PARAM 없음
밖    **데이터 내용은 안 본다.** 층이 선언대로 있고 git 이 선언대로 무시하는지만
      본다. 층 안의 파일이 옳은지는 `lakecheck` · `contract` 소관이다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from firelane import paths
from firelane.paths import ROOT


def cmd_fsck() -> None:
    """`sources.yaml` 의 layers 선언과 디스크·git·기계 설정을 대조한다.

    ★ 2026-08-24 신설. 이 저장소가 반복해 배운 것은 하나다 —
      **측정은 하는데 대조가 없다.** 계층도 같았다. 문서가 여섯이라 적고
      코드가 넷만 알아도 아무도 몰랐고, 없는 계층을 쓰려던 도구는 자기
      자리를 발명했다(SSD 루트 11.7MB).
    """
    import subprocess

    from firelane import layers as L

    bad: list[str] = []
    warn: list[str] = []
    print("── 계층 fsck")

    for n in L.names():
        pol, p = L.policy(n), L.path(n)
        mark = "OK  " if p.is_dir() else "없음"
        note = ""
        # ① required — 조용한 폴백을 금지한다
        if pol["required"] and not p.is_dir():
            bad.append(f"{n}: required 인데 없다 — {p}")
            mark = "★없음"
        if pol.get("status") == "미구현":
            note = "  (선언상 미구현)"
        # ② base 가 선언대로인가
        want = L.expected_base(n)
        try:
            p.relative_to(want)
        except ValueError:
            bad.append(f"{n}: base={pol['base']} 인데 {want} 아래가 아니다 — {p}")
        print(f"  {mark} {n:11s} {pol['base']:5s} {p}{note}")

    # ③ naming — 규칙 위반 파일
    print("\n── 파일명 규칙")
    for n in L.names():
        rx = pol_rx = L.policy(n).get("naming")
        p = L.path(n)
        if not rx or not p.is_dir():
            continue
        import re as _re
        pat = _re.compile(pol_rx)
        off = [str(q.relative_to(p)) for q in p.rglob("*")
               if q.is_file() and not q.name.startswith("_")
               and not pat.match(str(q.relative_to(p)))]
        print(f"  {n:11s} 위반 {len(off)}건")
        for q in off[:5]:
            bad.append(f"{n}: 명명규칙 위반 — {q}")

    # ④ committed 선언 ↔ .gitignore 실제
    print("\n── git 추적")
    for n in L.names():
        pol, p = L.policy(n), L.path(n)
        try:
            rel = p.relative_to(ROOT)
        except ValueError:
            continue                     # 저장소 밖이면 git 이 볼 일이 없다
        # ★ 백업 대상인데 저장소 밖인 계층(raw · quarantine)은 여기 안 온다.
        #   그쪽은 datalog verify 가 sha 로 본다.
        r = subprocess.run(["git", "check-ignore", "-q", str(rel)],
                           cwd=ROOT, capture_output=True)
        ignored = (r.returncode == 0)
        # ★ 2026-08-24. 폴더만 보면 안 된다. `.gitignore` 가 폴더를 막고
        #   `!` 로 몇 개만 여는 패턴이 있다(processed 넷). 선언의
        #   committed_exceptions 와 실제 추적 목록을 대조한다.
        exc = set(pol.get("committed_exceptions") or [])
        tracked = set()
        if rel:
            out = subprocess.run(["git", "ls-files", str(rel)], cwd=ROOT,
                                 capture_output=True, text=True).stdout.split()
            tracked = {Path(x).name for x in out}
        if exc:
            miss, extra = sorted(exc - tracked), sorted(tracked - exc)
            ok = not miss and not extra
            print(f"  {'OK  ' if ok else '★   '} {n:11s} "
                  f"예외 {len(exc)}개 · 추적 {len(tracked)}개")
            for q in miss:
                bad.append(f"{n}: 선언은 {q} 를 추적한다는데 git 이 모른다")
            for q in extra:
                bad.append(f"{n}: git 이 {q} 를 추적하는데 선언에 없다")
        else:
            ok = (ignored != bool(pol["committed"]))
            print(f"  {'OK  ' if ok else '★   '} {n:11s} "
                  f"committed={pol['committed']} · gitignore={ignored}")
            if not ok:
                bad.append(f"{n}: committed={pol['committed']} 인데 "
                           f"gitignore={ignored} — 선언과 실제가 다르다")

    # ⑤ regenerable:false 인데 커밋도 안 되고 백업도 아니면 소실 대기
    print("\n── 소실 위험 (R2)")
    for n in L.names():
        pol = L.policy(n)
        if pol["regenerable"] or pol["committed"] or pol["backup"]:
            continue
        if not L.path(n).is_dir():
            continue
        warn.append(f"{n}: 재생성 불가인데 커밋도 백업도 아니다 — 소실 대기")
        print(f"  ★    {n}")
    if not warn:
        print("  없음")

    # ⑥ backup — 마지막 백업 시각
    print("\n── 백업")
    for n in L.of("backup"):
        p = L.path(n)
        print(f"  {n:11s} {'있음' if p.is_dir() else '없음'}  {p}")
    print("  ★ 마지막 백업 시각은 datalog verify DIR 로 확인한다")

    # ⑦ 기계 설정 — 환경변수도 검사 대상이다
    print("\n── 기계 설정")
    if paths.env("FIRE_LANE_RAW"):
        bad.append("FIRE_LANE_RAW(폐기) 가 설정돼 있다 — "
                   "FIRE_LANE_DATA 를 덮어써 기계 간 산출물이 갈린다")
        print("  ★    FIRE_LANE_RAW 잔존")
    else:
        print("  OK   FIRE_LANE_RAW 없음")
    if not paths.env("FIRE_LANE_DATA"):
        warn.append("FIRE_LANE_DATA 미설정 — raw 가 저장소 안으로 떨어진다")
        print("  ★    FIRE_LANE_DATA 미설정")
    else:
        print("  OK   FIRE_LANE_DATA 설정됨")
    # ★ 2026-09-18 (W1b). 종전에는 `core.hooksPath == ".githooks"` 를 요구했고,
    #   그것은 `dms.py::hook/local-hooksPath`(로컬이 설정돼 있으면 실패)와 정확히
    #   반대였다 — 어느 기계든 한쪽은 항상 울었다(2족 기존 인스턴스).
    #   구조는 이렇다: **전역 훅이 주인이고, 후보 경로에서 저장소 훅을 찾아 부른다.**
    #   그러니 볼 것은 셋이다 — 전역이 있는가 · 로컬이 안 덮는가 ·
    #   저장소 훅이 실행 가능한가(전역이 `[ -x ]` 로 고른다).
    # ★ 도달 자체는 여기서 안 잰다. 그것은 실행이 필요하고
    #   `.githooks/global-chain.sh --check` 가 탐침으로 한다 — `doctor` 는 관측이다.
    def _cfg(scope: str) -> str:
        return subprocess.run(["git", "config", scope, "core.hooksPath"],
                              cwd=ROOT, capture_output=True, text=True).stdout.strip()

    g, loc = _cfg("--global"), _cfg("--local")
    hook = ROOT / ".githooks" / "pre-commit"
    if not g:
        warn.append("전역 core.hooksPath 미설정 — 자격증명 검사가 어느 저장소에도 안 돈다. "
                    "git config --global core.hooksPath ~/.githooks")
        print("  ★    전역 core.hooksPath 없음")
    elif loc:
        warn.append(f"로컬 core.hooksPath({loc}) 가 전역을 이긴다 — 자격증명 검사가 사라진다. "
                    "git config --local --unset core.hooksPath")
        print(f"  ★    로컬 core.hooksPath = {loc} (전역을 덮는다)")
    elif not (hook.exists() and hook.stat().st_mode & 0o111):
        warn.append(".githooks/pre-commit 이 없거나 실행 불가 — 전역 훅이 후보로 안 집는다. "
                    "chmod +x .githooks/pre-commit")
        print("  ★    .githooks/pre-commit 실행 불가")
    else:
        print(f"  OK   전역 훅 {g} · 저장소 훅 실행 가능 (도달은 global-chain.sh --check)")

    print()
    for w in warn:
        print(f"  ⚠ {w}")
    for b in bad:
        print(f"  ★ {b}")
    print(f"\n{'계층 선언과 실물이 일치한다' if not bad else f'★ {len(bad)}건 어긋남'}")
    sys.exit(1 if bad else 0)
