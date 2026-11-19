#!/usr/bin/env python3
"""
pushdenom.py — **pushready 칸이 자기 분모를 말하게 한다** — ㉠(래칫)의 「래칫 N개 중 몇 개를 읽었나 · 넘기는 규칙 둘」과 ㉥(시험)의 「읽기 실측 N/M」을 초록일 때도 한 줄로 낸다.  (PLAN #259 · DECISIONS §835)

`tools/pushready.py` 의 `check_ratchet` · `check_tests` 가 부른다 — 칸이 읽은 출력에서 분모를 뽑아 `record` 에 쌓고 `lines` 가 푸시 가능 · 불가 보고 끝에 붙인다.

판별식   `skip_rule(mark, tool, name)` — ㉠ 가 **넘기는** 래칫 항목이 선언표(`RATCHET_SKIPS`)의 어느 규칙인가(없으면 None → 읽는다) · `reads_gap` — ㉥ 의 읽기 장부가 못 덮은 시험이 **새 시험으로 설명되는가**
① 본 몫(분모)      ㉠ = `ratchet.py` 의 「래칫 N개」 중 읽은 수(N − 넘긴 수) · ㉥ = `testpick` 의 「읽기 실측 n/M개 파일」
② 못 세는 값이 갈 칸  넘긴 항목은 규칙마다 따로 센다(`RATCHET_SKIPS` 의 키) · 장부가 못 덮은 시험은 새 시험 수로 설명하고 남는 것은 `설명 안 되는 몫` 이다 · 분모를 못 읽으면 「분모를 못 읽었다」를 낸다(0 이 아니다)
③ 전제와 우는 것   전제 = 넘기는 규칙은 **선언표에 든 둘뿐**이고(사유가 비면 안 된다) 장부가 못 덮은 시험은 새 시험이 전부다. 선언 밖 항목은 읽혀서 막고 · 설명 안 되는 몫이 있으면 ㉥ 가 막는다

IN    `ratchet.py` 의 출력 · `testpick --run` 의 출력(문자열) — 파일을 읽지 않는다
OUT   문자열 · 튜플. `record`/`lines` 가 쓰는 모듈 상태 한 칸(프로세스 안 · 파일은 안 쓴다)
PARAM `RATCHET_SKIPS`(넘기는 규칙 둘 · 사유)
밖    **막을지는 `pushready` 가 정한다**(여기는 분모만 센다) · 래칫 값이 옳은지 · 시험이 초록인지는 안 본다. 분모의 % 는 래칫으로 안 건다(범위 축소는 선언표가 막는다 — `uicheck` 와 같다).
부류  몸통   진입점이 **아니다.** `pushready.py` 가 import 한다  (DECISIONS §398)
"""
from __future__ import annotations

import re
import threading

#: ㉠ 가 `ratchet.py` 출력에서 **넘기는** 항목 — 키 → (판별식, 사유). 이 밖의 `✗` · `·` 는 전부 읽어 막는다. 사유가 비면 시험이 운다.
RATCHET_SKIPS: dict[str, tuple] = {
    "UNSEALED → ㉢": (lambda mark, tool, name: tool == "docseal.py" and name == "UNSEALED",
                      "도장이 아예 없는 절 수는 ㉢ 가 선언 `docseal.UNSEALED` 와 맞대어 막는다 — 같은 값을 두 칸이 세면 한 병에 막힘이 둘이다"),
    "mutate.py 의 ✗ 아닌 것 → ㉤": (lambda mark, tool, name: tool == "mutate.py" and (mark != "✗" or name == "—"),
                                 "변이 장부가 낡았거나 죽은 것은 ㉤ 가 맡고 · 조이는 쪽의 `--write` 는 변이 지문을 낡게 한다(㉠→㉤) — ✗ 느슨해지는 쪽만 ㉠ 가 읽는다"),
}

ITEM = re.compile(r"^\s+([✗·~]) (\S+) · (\S+)")
SUMMARY = re.compile(r"래칫 (\d+)개 · 낡음 (\d+)(?:.*?건너뜀 (\d+))?")
_READS = re.compile(r"실측 읽기 (\d+)/(\d+)개 파일")
_NEW = re.compile(r"낡은 시험 새: ?(.*)$", re.M)
_LOCK = threading.Lock()
_DENOM: dict[str, list[str]] = {}


def skip_rule(mark: str, tool: str, name: str) -> str | None:
    """넘기는 규칙의 키 — 없으면 None(읽는다)."""
    return next((k for k, (f, _) in RATCHET_SKIPS.items() if f(mark, tool, name)), None)


def ratchet_denom(out: str) -> list[str]:
    """㉠ 의 분모 줄들 — 「래칫 N개 중 읽은 수」와 넘기는 규칙마다 센 수 · 사유. 요약줄을 못 읽으면 그 말을 낸다."""
    m = SUMMARY.search(out)
    if m is None:
        return ["㉠ 분모를 못 읽었다 — `ratchet.py` 의 「래칫 N개」 줄이 없다(출력 꼴이 바뀌었나)"]
    n, ratchet_skip = int(m.group(1)), int(m.group(3) or 0)
    got = [k for ln in out.splitlines() if (it := ITEM.match(ln)) and (k := skip_rule(*it.groups()))]
    return [f"㉠ 래칫 {n}개 중 {n - len(got)}개를 읽었다 · 넘긴 {len(got)}개 · `ratchet.py` 가 못 잰 것 {ratchet_skip}개",
            *(f"    넘기는 규칙 — {k} ({got.count(k)}개): {why}" for k, (_, why) in RATCHET_SKIPS.items())]


def reads_gap(out: str) -> tuple[int, int, int] | None:
    """㉥ — (읽기 실측 n, 시험 파일 M, 새 시험으로 설명 안 되는 몫). 분모 줄이 없으면 None."""
    m = _READS.search(out)
    if m is None:
        return None
    n, total = int(m.group(1)), int(m.group(2))
    new = _NEW.search(out)
    return n, total, max(0, total - n - len(new.group(1).split() if new else []))


def tests_denom(out: str) -> list[str]:
    g = reads_gap(out)
    if g is None:
        return ["㉥ 분모를 못 읽었다 — `testpick` 의 「읽기 실측 n/M개 파일」 줄이 없다(출력 꼴이 바뀌었나)"]
    n, total, unexplained = g
    return [f"㉥ 읽기 실측 {n}/{total}개 파일({n / total:.1%}) · 못 덮은 {total - n}개 중 새 시험으로 설명 안 되는 몫 {unexplained}"
            + (" — 새 시험은 정적 스캔만이라 하한이다(낡음이 막는다)" if total - n else "")]


def gap_block(out: str) -> tuple[str, list[str], list[str]] | None:
    """설명 안 되는 몫이 있으면 막는 것 하나 — (무엇 · 자세히 · 사람이 칠 명령). 없으면 None."""
    g = reads_gap(out)
    if g is None or not g[2]:
        return None
    n, total, un = g
    return (f"읽기 장부가 {un}개 시험을 못 덮는데 새 시험으로 설명이 안 된다(읽기 실측 {n}/{total})", [f"장부에 없는 시험 {total - n}개 중 새 시험은 {total - n - un}개뿐이다"],
            ["uv run python tools/testpick.py --measure-reads --write --only <장부에 없는 시험…>   # 어느 시험인지는 --list 의 「장부에 없음」"])


def record(key: str, lines: list[str]) -> None:
    with _LOCK:
        _DENOM[key] = lines


def lines() -> list[str]:
    """쌓인 분모 줄 — 칸 순서(㉠ 다음 ㉥)."""
    with _LOCK:
        return [x for k in ("㉠", "㉥") for x in _DENOM.get(k, [])]
