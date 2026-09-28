#!/usr/bin/env python3
"""
sizecheck.py — **파일이 얼마나 긴가.** 양방향 래칫이다.

    uv run python tools/sizecheck.py            판정 (verify.sh · CI)
    uv run python tools/sizecheck.py --table    상한을 넘는 파일 전부를 표로
    uv run python tools/sizecheck.py --selftest ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-22 (DECISIONS §218-5 · 하토르 `check_file_size.py` 모범). 길이를 세는 검사가
  하나도 없었다. 실측으로 `tests/test_guards.py` 가 2,396줄 · `tools/dms.py` 가 1,250줄이고,
  둘 다 **한 번에 는 것이 아니라 배치마다 조금씩** 늘었다. 조금씩 느는 것은 어느 배치도
  「내가 늘렸다」고 느끼지 않는다 — 그래서 세는 자리가 있어야 한다.

★ 오늘 넘는 파일을 오늘 줄이라고 하지 않는다. `dupcheck --max` · `gate_parity` 의
  `RATCHET` 과 같은 방식이다 — **지금 값에서 시작해 내린다.** 넘는 파일은 `EXCEPTIONS` 에
  오늘 줄 수 그대로 박힌다.

── 판정 (양방향) ──────────────────────────────────────────────
    예외 없는 파일이 상한을 넘었다        실패 — 새로 넘었다. 쪼개거나 예외를 사유와 함께
    예외 파일이 기록보다 늘었다           실패 — 예외는 늘 자리가 아니다
    예외 파일이 기록보다 줄었다           실패 — **예외를 그 수로 내려라** (안 내리면 다시 는다)
    예외 파일이 상한 아래로 내려왔다      실패 — 예외를 지워라
    예외 파일이 없어졌다                  실패 — 예외를 지워라

★ 줄었을 때도 실패인 이유 — 느슨해진 래칫은 초록으로 위장한다. 2026-09-19 에 커버리지
  래칫이 14 인데 실물이 24% 인 것을 나흘간 아무도 몰랐다(PLAN §13 W4-9). 이 도구의 수는
  **선언된 개수**라 같음이 의미를 갖는다(verify.sh 「커버리지 래칫」 머리의 이산/연속 구분).

── 무엇을 세나 ────────────────────────────────────────────────
`src/` · `tools/` · `tests/` 아래 `.py` · `.sh` · `.mjs`. 줄 수는 `wc -l` 과 같게 센다.
`tests/` 는 시험 상한(700), 나머지는 코드 상한(600)이다 — 시험은 사례를 나열하므로
같은 일을 하는 코드보다 길다.
★ 추적 여부는 안 가린다. 커밋 **전에** 늘어난 것을 잡는 것이 목적이다.

IN    src/** · tools/** · tests/**
OUT   표준출력 (판정)
PARAM LIMITS · EXCEPTIONS
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# ★ 2026-09-24 (DECISIONS §244). `web/navi/src` 가 범위 밖이었다. 그래서 상한을
#   넘는 프런트 파일 셋(`OpsApp.tsx` 744 · `App.tsx` 640 · `domain/graph.ts` 627)이
#   **래칫에 한 번도 안 잡혔다.** 길이 상한은 「한 파일이 몇 가지 일을 하는가」를
#   재는 것이고 그 물음에 언어는 상관없다.
DIRS = ("src", "tools", "tests", "web/navi/src", "web/navi/test")
SUFFIX = (".py", ".sh", ".mjs", ".ts", ".tsx")
SKIP = {"__pycache__", ".venv", "node_modules", "fixtures"}

# ★ 상한. 한 곳에만 산다 — 부르는 쪽(verify.sh · contract.yml)은 인자를 안 적는다.
LIMITS = {"code": 600, "test": 700}

# ★ 알려진 예외 — **오늘 줄 수 그대로**(2026-09-22 실측). 느는 것도 줄어드는 것도 실패다.
#   줄였으면 여기 수를 같이 내린다. 상한 아래로 내려오면 줄을 지운다.
#   늘려야 할 때는 여기 수를 올리고 **왜 쪼개지 않는지** 커밋에 적는다.
EXCEPTIONS: dict[str, int] = {
    # 시험 (상한 700)
    # ★ 2026-09-26 (§258-10). 2430 → 2440. 경로 적재 셋에 `sys.modules` 등록 줄과
    #   SKIP 사유 강제를 다음 배치로 미룬 사유다.
    # ★ 2026-09-28 (DECISIONS §290-8). 2439 → 2447. `PYTHONPATH` 를 덮어쓰지 않고
    #   `src` 를 먼저 두는 여덟 줄이다 — 시험이 그것이 사는 체크아웃을 재게 한다.
    "tests/test_guards.py": 2447,
    # ★ 2026-09-23 (DECISIONS §222-6). 718. **쪼개지 않는다** — 이 파일은 「선언과 실물이
    #   같은가」 한 물음의 사례 목록이고, 선언이 늘면 같이 는다. 둘로 가르면 새 선언을
    #   어느 파일에 적어야 하는지가 또 하나의 기억거리가 되고, 그때 한쪽만 고치는 날이 온다.
    "tests/test_declaration_sync.py": 783,
    # ★ 2026-09-28 (DECISIONS §278-5·6). 723. **쪼개지 않는다** — 이 파일은
    #   「배치 도구가 규약을 지키는가」 한 물음의 사례 목록이고, 규약이 늘면
    #   같이 는다(`test_declaration_sync.py` 와 같은 사유). 둘로 가르면 새 규약을
    #   어느 파일에 적을지가 또 하나의 기억거리가 된다.
    # ★ 2026-09-28 (DECISIONS §282-1). 723 → 743. 「초록이라 말하고 스쿼시가
    #   거부됐다」를 무는 시험이다. 이 파일은 배치 도구 규약의 사례 목록이라
    #   규약이 늘면 는다.
    "tests/test_batch_tools.py": 743,
    # 코드 (상한 600)
    # ★ 2026-09-28 (DECISIONS §292-4). 1574 → 1588. `SAID_N` 에 숫자 꼴 갈래와
    #   자기검사 네 팔, 그리고 그 사유다. 그 한 갈래가 없어서 물림 수 어긋남
    #   10건이 조용히 통과하고 있었다 — 검사가 늘면 이 파일이 는 것이 맞다.
    "tools/dms.py": 1588,
    "src/firelane/ingest.py": 646,
    # ★ 2026-09-28 (DECISIONS §280-3). 1059 → 1068.  에 짝 하나와
    #   그 사유다. 이 파일은 프로브 다섯의 면제 목록이라 면제가 늘면 는다 —
    #   사유 없는 면제를 막는 것이 이 표의 목적이므로 줄 수로 줄일 자리가 아니다.
    # ★ 2026-09-28 (DECISIONS §283 · §286 · §288). 1068 → 1080. `EXEMPT_SCOPE`
    #   에 항목 **셋**과 사유다 — 오늘 새로 만든 도구 넷의 범위 선언이 ⑤ 를
    #   0 → 4 로 울렸고, 셋은 좁은 것이 규칙의 뜻이라 선언하고 하나는 넓혔다.
    #   이 파일은 **프로브 다섯의 면제 목록**이라 면제가 늘면 는다.
    # ★ 2026-09-28 (DECISIONS §290). 1080 → 1087. `EXEMPT_SCOPE` 에 항목 하나와
    #   사유다 — `test_cli_surface` 의 **정적 팔**이 ⑤ 를 울렸고, 동적 팔과 같은
    #   범위인 것이 규칙의 뜻이라 선언했다. 프로브 다섯의 면제 목록이므로 는다.
    "tools/deadcheck.py": 1087,
    # ★ 2026-09-23. 976 → 980 → 991. 「기획서 그림 ↔ 정본」(§221-1)과 「죽은 강제자
    #   참조」(§222-2)가 들어갔다. verify.sh 는 검사의 목록이라 검사가 늘면 늘어난다 —
    #   쪼개면 「어느 파일에 있나」 가 또 하나의 기억거리가 된다(§18-3).
    # ★ 2026-09-25 (DECISIONS §246). 1022 → 1030. 「문서 생성 블록 ↔ 실물」
    #   단계와 그 사유가 들어갔다. verify.sh 는 검사의 목록이므로 검사가 늘면
    #   는다 — 위 문단과 같은 이유로 쪼개지 않는다.
    # ★ 2026-09-25 (§258). 1030 → 1034. 커버리지 래칫을 28 → 32 로 올린 사유
    #   네 줄이다. 값만 바꾸고 사유를 안 적으면 다음 사람이 「왜 32냐」를 못 찾고,
    #   못 찾는 래칫은 곧 내려간다.
    # ★ 2026-09-25 (§258-8). 1034 → 1041. 「관문 호출 인자」 단계와 그 사유다.
    #   verify.sh 는 검사의 목록이라 검사가 늘면 는다 — 위 문단과 같은 이유로
    #   쪼개지 않는다.
    # ★ 2026-09-27 (DECISIONS §276-2). 600 → 622. 3단계가 「증분인가 교체인가」를
    #   **재고 나서** 판단하게 하는 22줄이다. **쪼개지 않는다** — `verify.sh` 와
    #   같은 이유다. 이 파일은 열차의 11단계를 순서대로 든 목록이고, 가르면
    #   「어느 단계가 어느 파일에 있나」가 또 하나의 기억거리가 된다(§18-3).
    #   그리고 실행 중에 가지를 바꾸므로 파일이 둘이면 **한쪽만 옛 판**이 될 수 있다.
    # ★ 2026-09-28 (§278-5). 622 → 623. 낱개 패치 규칙이 `fire-lane-` 접두사를
    #   보게 된 사유 한 줄이다.
    # ★ 2026-09-28 (§278-6). 623 → 632. CI 대기를 `tools/ci_wait.sh` 로 올리면서
    #   「빨강 / 모름」을 가르는 분기와 그 사유가 들어갔다. 종전에는 **비영이면
    #   전부 빨강**이었다 — 세 줄이 아홉 줄이 된 값이 그것이다.
    # ★ 2026-09-28 (DECISIONS §290-4). 632 → 650. **4c 단계**와 그 사유다 —
    #   배달물의 `EXPECT` 를 읽는 것이 저장소 전체에서 0개였다. 열차의 단계가
    #   늘었으므로 이 파일이 늘는 것이 맞다(위 문단과 같은 이유로 쪼개지 않는다).
    # ★ 2026-09-28 (DECISIONS §290-8). 650 → 654. `-d .git` 이 워크트리를 저장소가
    #   아니라고 해서 배달 예습을 빨갛게 만들었다 — git 에게 직접 묻는 한 줄과 그 사유다.
    "tools/fl.sh": 654,
    # ★ 2026-09-28 (DECISIONS §278-2·3). 1030 → 1041. 「기획서 개요 층」과
    #   「문서 말투」 두 단계와 그 사유다. verify.sh 는 검사의 목록이라 검사가
    #   늘면 는다 — 위 문단들과 같은 이유로 쪼개지 않는다.
    # ★ 2026-09-28 (DECISIONS §279-4·6). 1041 → 1054. 「내비 린트」 · 「사유 없는
    #   억제」 두 단계와 그 사유다. verify.sh 는 검사의 목록이라 검사가 늘면 는다.
    # ★ 2026-09-28 (DECISIONS §280-3). 1054 → 1064. 「계층 선언↔실물」 단계와
    #   그 사유다. MASTER §18-1·§18-7 이 강제자로 적어 둔 것을 이제 관문이 부른다.
    # ★ 2026-09-28 (DECISIONS §285). 1064 → 1099. **관문 다섯**과 그 사유다 —
    #   「계보 대장 정합」 · 「계보 그림 생성」 · 「취입 계약 선언」(레이크 불필요)
    #   과 「취입 계약 실물」 · 「대장 스키마↔실물」(레이크 필요). 문서가 관문이라
    #   이름까지 적어 두고 아무도 안 부르던 것들이다(§280). verify.sh 는 검사의
    #   목록이므로 **검사가 늘면 는 것이 맞다** — 이 파일이 안 크는 배치는
    #   관문을 안 붙인 배치다.
    # ★ 2026-09-28 (DECISIONS §286 · §288 · W13-7). 1099 → 1110. 단계 **둘**과
    #   그 사유다 — 「자기검사 전수」(선언된 `--selftest` 26개 중 16개를 아무도
    #   안 불렀다)와 「실측 층 지문」(재취득 불가 층에 지문이 없었다).
    # ★ 2026-09-28 (DECISIONS §289). 1110 → 1122. 「폭 교차대조」 단계와 그 사유다 —
    #   오염 안 된 외부 증인 둘(1:1,000 측량 도로폭 · 도로대장 명목폭)이 이미
    #   대장에 있었고 아무도 대지 않았다. verify.sh 는 검사의 목록이라 검사가 늘면 는다.
    # ★ 2026-09-28 (DECISIONS §290). +3. 커버리지 래칫 33→34 와 **F 가 그 권고를
    #   읽고도 안 조인 사실**을 그 자리에 적었다. 검사가 아니라 사유 세 줄이다.
    # ★ 2026-09-28 (DECISIONS §292-2). 1125 → 1130. 「패키지 import」의 손목록 31개를
    #   유도로 바꾼 다섯 줄과 사유다. 목록이 줄어들고 덮는 범위는 31 → 68 로 늘었다.
    "tools/verify.sh": 1130,
    "src/firelane/segments.py": 853,
    "tools/render_workflow.py": 635,
    "tools/golden.py": 613,
    "src/firelane/normalize_raw.py": 609,
    # ★ 2026-09-24. 프런트가 래칫에 처음 들어왔다. **오늘 수 그대로** 박는다 —
    #   래칫의 값어치는 「지금보다 나빠지지 않는다」이지 「지금이 옳다」가 아니다.
    #   셋 다 쪼갤 자리가 있고 그것은 `PLAN §1` 이 든다(#130).
    # ★ 2026-09-25 (PLAN §1 #130). 셋을 쪼갰다 — `OpsApp.tsx` 744→551 · `App.tsx`
    #   640→556 · `domain/graph.ts` 627→375. 상한 아래로 내려왔으므로 **줄을 지운다.**
    #   앞 문단을 남겨 둔다 — 프런트가 어떻게 들어왔는지는 기록으로 값이 있다.
}


def kind(rel: str) -> str:
    return "test" if rel.startswith("tests/") else "code"


def count_lines(p: Path) -> int:
    """`wc -l` 과 같다 — 개행 문자 수. 끝개행이 없는 마지막 줄은 안 센다."""
    return p.read_bytes().count(b"\n")


def measure(root: Path = ROOT) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix not in SUFFIX:
                continue
            rel = p.relative_to(root)
            if SKIP & set(rel.parts):
                continue
            out[rel.as_posix()] = count_lines(p)
    return out


def judge(counts: dict[str, int], exceptions: dict[str, int],
          limits: dict[str, int] = LIMITS) -> list[str]:
    """위반 목록. 비면 통과다. **순수 함수**라 시험이 합성 입력으로 부른다."""
    bad: list[str] = []
    for rel, n in sorted(counts.items()):
        lim = limits[kind(rel)]
        if rel in exceptions:
            want = exceptions[rel]
            if n <= lim:
                bad.append(f"{rel}: {n}줄 — 상한 {lim} 아래로 내려왔다. EXCEPTIONS 에서 지워라")
            elif n > want:
                bad.append(f"{rel}: {n}줄 > 예외 {want} — 늘었다. 예외는 늘 자리가 아니다")
            elif n < want:
                bad.append(f"{rel}: {n}줄 < 예외 {want} — 줄었다. EXCEPTIONS 를 {n} 으로 내려라"
                           " (안 내리면 다시 늘어도 안 운다)")
        elif n > lim:
            bad.append(f"{rel}: {n}줄 > 상한 {lim} — 새로 넘었다. 쪼개거나, 못 쪼개는 사유와"
                       " 함께 EXCEPTIONS 에 오늘 수로 적어라")
    for rel, want in sorted(exceptions.items()):
        if rel not in counts:
            bad.append(f"{rel}: 예외 {want} 인데 파일이 없다. EXCEPTIONS 에서 지워라")
        elif want <= limits[kind(rel)]:
            bad.append(f"{rel}: 예외 {want} 가 상한 {limits[kind(rel)]} 이하다 — 예외가 아니다")
    return bad


def selftest() -> int:
    """★ 빈 그물인가. 판정기가 다섯 갈래를 전부 우는지 합성 입력으로 본다."""
    lim = {"code": 10, "test": 20}
    cases = {
        "새로 넘음": ({"tools/a.py": 11}, {}),
        "늘어남": ({"tools/a.py": 13}, {"tools/a.py": 12}),
        "줄어듦": ({"tools/a.py": 11}, {"tools/a.py": 12}),
        "상한 아래": ({"tools/a.py": 9}, {"tools/a.py": 12}),
        "없어짐": ({}, {"tools/a.py": 12}),
    }
    dead = [name for name, (c, e) in cases.items() if not judge(c, e, lim)]
    if judge({"tools/a.py": 12, "tests/t.py": 20}, {"tools/a.py": 12}, lim):
        dead.append("정상 입력에서 운다")
    if not measure():
        dead.append("저장소에서 파일을 0개 셌다 — 수집기가 죽었다")
    if dead:
        print("✗ 판정기 자기검사 실패 — " + ", ".join(dead))
        return 1
    print(f"✓ 판정기 OK — 다섯 갈래가 울고 정상은 통과한다 · 파일 {len(measure())}개")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="파일 길이 양방향 래칫")
    ap.add_argument("--table", action="store_true", help="상한을 넘는 파일 전부를 표로")
    ap.add_argument("--selftest", action="store_true", help="판정기가 살아 있나")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    counts = measure()
    if not counts:
        print("✗ 파일을 0개 셌다 — 수집기가 죽었다")
        return 1
    if a.table:
        for rel, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lim = LIMITS[kind(rel)]
            if n > lim:
                tag = f"예외 {EXCEPTIONS[rel]}" if rel in EXCEPTIONS else "★ 미등재"
                print(f"  {n:>6}  {rel:<40} 상한 {lim} · {tag}")
    bad = judge(counts, EXCEPTIONS)
    if bad:
        print(f"✗ 파일 길이 {len(bad)}건")
        for b in bad:
            print(f"    {b}")
        return 1
    over = sum(1 for r, n in counts.items() if n > LIMITS[kind(r)])
    print(f"✓ 파일 {len(counts)}개 · 상한 코드 {LIMITS['code']} · 시험 {LIMITS['test']}"
          f" · 예외 {len(EXCEPTIONS)}개가 기록과 같다 (넘는 파일 {over})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
