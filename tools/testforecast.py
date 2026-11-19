#!/usr/bin/env python3
"""
testforecast.py — **시험 묶음이 자기 예보를 말하게 하고 · pre-push 의 예산 초과를 한 번의 측정이 아니라 최근 회차의 중앙값으로 판다.**  (PLAN #264 · DECISIONS §837)

    uv run python tools/testpick.py --forecast [--range A..B …]       정확도 단계별 표(읽기 정확도가 오르면 ㉥ 의 초가 얼마나 느는가)
    uv run python tools/testforecast.py judge --file F --secs 31.2 --key K --budget 30    pre-push 훅이 부른다(기록을 더하고 한 줄을 낸다)

`tools/testpick.py` 가 `accuracy_line` · `hook_line` · `forecast_table` 을 부르고 `.githooks/pre-push` 가 `judge` 를 부른다. 예산 · 시험 묶음 선택은 안 건드린다 — **말만 한다**(래칫은 그대로다).

판별식   `judge(prev, now, budget, n)` — 최근 `n` 회(이번 포함)의 **중앙값**이 예산을 넘으면 운다 · 이번 회차만 넘으면 「이번 회차 S초(중앙값 M초)」로 **알리기만** 한다
① 본 몫(분모)      기록이 `n` 개 찼으면 최근 `n` 회 · 그 전에는 「기록 k/n」 — 중앙값 칸이 안 찬 채로 울지 않는다. 같은 훅 · 같은 게이트 파일의 기록만 센다(`key`)
② 못 세는 값이 갈 칸  초록으로 끝난 회차만 쌓인다(빨간 회차는 게이트가 일찍 멈춰 초가 짧다 — 쌓으면 중앙값이 낮아진다) · 기록이 없는 새 체크아웃은 「기록 0/n」으로 말한다
③ 전제와 우는 것   전제 = 호스트 흔들림이 회차마다 독립에 가깝다(같은 트리에서 22.5 ~ 37.0초 — DECISIONS §836) · 진짜 느려짐은 `n` 회에 걸쳐 지속된다. **벗어나면 운다:** 느려짐이 한두 회차짜리 폭주(62초 한 번)면
  중앙값이 안 울고 「이번 회차」 알림만 선다 · 느려짐이 지속되면 `(n+1) ÷ 2` 번째 회차에 운다(DECISIONS §837 표)

판별식 둘  `judge`(예산) 에 더해 `ratio_verdict(prev, now)` — **예보와 실측의 비**를 같은 축의 최근 `N_RATIO` 회 안에서 본다(DECISIONS §838). 보정 예보 = 모형 추정 × 같은 축 최근 비의 중앙값.
  울음 = 최근 회차들의 **보정 오차**(비 ÷ 그 회차 직전 중앙값, 1 이상으로 접은 값)의 중앙값이 `BAND` 를 넘을 때 · 한 회차만 `SPIKE` 를 넘으면 알리기만 한다
  ① 본 몫  직전 기록이 `MIN_RATIO` 개 이상인 회차만 센다 — 덜 찼으면 「기록 k/3」을 말하고 울지 않는다 · 보정도 안 한다 ② 못 세는 값  빨간 회차(비가 안 쌓인다) · 다른 축의 기록은 센 몫 밖이다 · 보정을 못 하면 모형 추정만 말한다
  ③ 전제  **한 축의 비가 안정이다**(훅 축: 열세 회 중 열하나가 ×0.73 ~ 0.85, 둘이 호스트 흔들림 ×1.35 ~ 1.45). 벗어나면 운다 — ㉥ 축은 비가 범위마다 갈려(×0.82 ~ ×1.40, 표본 넷) 보정이 안 맞고 **그래서 울 수 있다**
IN    기록 파일 둘(`<git 공용 디렉터리>/fire-lane-prepush-secs` · 비 기록 `fire-lane-forecast-ratios` — **추적 안 하는** 파일: 추적하면 푸시마다 바뀌고 훅 자신의 「추적 파일이 더럽다」 검사가 다음 푸시를 막는다) · 시간 장부 · 읽기 장부
OUT   화면 한 줄들 · `judge` 가 기록 한 줄을 더한다(최근 `KEEP` 줄만 남긴다) · `testpick --run` 이 초록으로 끝나면 비 기록 한 줄을 더한다
PARAM `N_RECENT`(중앙값을 재는 회차 수) · `N_RATIO` · `MIN_RATIO` · `BAND` · `SPIKE`(비 판정 · DECISIONS §838) · `KEEP`(기록 보존 줄 수) · `FORECAST_PAR`(㉥ 초를 나누는 병렬 · DECISIONS §836 표와 같다)
밖    **예산 30초의 근거는 만들지 않는다**(아래 `BUDGET_NOTE`) · 우는 것은 경고일 뿐 푸시를 막지 않는다 · 호스트가 흔들리는 원인은 안 가른다
부류  조사   읽기 전용으로 수를 낸다(`judge` · `append_ratio` 만 추적 안 하는 기록 파일에 한 줄을 더한다). `testpick.py` 가 함수를 import 한다
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

N_RECENT = 5       # 회차 — 중앙값을 재는 창. 왜 5 인가는 DECISIONS §837 이 든다(거짓 울음 · 진짜 울음의 지연을 셈)
KEEP = 20          # 줄 — 기록 파일에 남기는 최근 회차 수
N_RATIO = 5        # 회차 — 비의 중앙값을 재는 창(예산 창과 같은 5 — DECISIONS §837 이 왜 5 인지 든다)
MIN_RATIO = 3      # 개 — 직전 기록이 이만큼은 있어야 보정하고 오차를 센다(중앙값이 셋 미만의 점에 기대지 않게)
BAND = 1.25        # 배 — 보정 오차의 중앙값이 이 배를 넘으면 운다. 훅 축의 평온한 회차 오차는 최대 ×1.06 이었다(열두 회 재생 · DECISIONS §838 표). ㉥ 축은 표본 넷이라 아직 셀 수 없다
SPIKE = 1.5        # 배 — 한 회차의 보정 오차가 이 배를 넘으면 알리기만 한다(훅 축의 호스트 흔들림 ×1.73 · ×1.86 이 여기 걸린다)
RATIO_FILE = "fire-lane-forecast-ratios"
FORECAST_PAR = 4   # ㉥ 초 = 닿는 시험의 장부초 합 ÷ 이 값 — DECISIONS §836 표가 쓴 나눔이다

#: ★ 예산 30초의 근거 — **근거가 없다.** 출처는 DECISIONS §580(2026-10-25 · 「30초 안에 드는 묶음만」)과 §586(「푸시 직전 묶음은 한 호흡 안이어야 사람이 안 우회한다」)이고
#: 그때 훅이 16.4초여서 정한 **여유**였다. 사람이 견디는 시간을 잰 값이 아니다. 근거를 만들려면 사람이 기다리는 시간을 재야 하고 그것은 지금 할 일이 아니다 —
#: 근거 없는 수를 다른 근거 없는 수로 바꾸는 것은 아무것도 아니라서 수는 그대로다(훅의 `BUDGET` · `testpick.DEFAULT_BUDGET` 28 · 이 상수가 한 곳을 가리킨다).
BUDGET_NOTE = "예산 30초 — 근거 없음(DECISIONS §580 · §586 · 그때 훅 16.4초여서 정한 여유 · 사람이 견디는 시간을 잰 값이 아니다)"


def axis_tag(load: float, touched: bool) -> str:
    """어느 축의 수인가 — 같은 식(`시동 + (남의 일 + 장부초) ÷ 병렬`)이 **남의 일 값**으로 두 축을 맡는다. 훅 축은 60 · ㉥ 축은 0 이라 방향이 반대다(DECISIONS §838)."""
    if load > 0:
        return f"pre-push 묶음 · 남의 일 {load:g}"
    return "닿는 시험 포함 · 남의 일 0" if touched else "묶음만 · 남의 일 0"


def accuracy_line(fresh: int, total: int, est: float, budget: float, reads_used: bool, axis: str = "") -> str:
    """읽기 정확도 N/M · 예상 S초 · 예산 B초 — 한 줄. `reads_used` 가 거짓이면 그 선택이 읽기 장부를 안 읽는다는 것을 같이 적는다(정확도가 올라도 이 초는 안 는다)."""
    tail = "" if reads_used else " · 이 선택은 읽기 장부를 안 읽는다(--no-touched — 정확도가 올라도 이 초는 안 는다)"
    tag = f"(모형 · {axis})" if axis else ""
    return f"읽기 정확도 {fresh}/{total}개 파일(실측 · 낡지 않음) · 예상 {est:.1f}초{tag} · 예산 {budget:g}초{tail}"


def over_budget_warning(est: float, budget: float) -> str | None:
    """예상이 예산을 넘으면 경고 한 줄 — 경고만 한다(예산 · 래칫은 안 건드린다)."""
    return f"⚠ 예상 {est:.1f}초가 예산 {budget:g}초를 넘는다(경고만 · 예산은 안 건드린다)" if est > budget else None


def hook_line(info: dict, actual: float | None = None, new_names: int | None = None, axis: str = "") -> str:
    """pre-push 가 말하는 예보 줄 — 「추정 E · 새 시험 n개 +k초 · 실측」. 새 시험은 장부에 없어 중앙값으로 치고 **예산과 무관하게 든다**(그래서 짧은 시험을 밀어낸다)."""
    n = len(info.get("new", [])) if new_names is None else new_names
    head = f"예보 [{axis}] 모형 추정 {info['est']:.1f}초" if axis else f"예보 추정 {info['est']:.1f}초"
    parts = [head, f"새 시험 {n}개가 {info.get('new_est', 0.0):.1f}초를 먹는다(장부에 없음 · 중앙값 {info.get('median', 0.0):.1f}장부초로 침 · 짧은 시험 {info.get('displaced', 0)}개를 묶음 밖으로 밀었다)"]
    if actual is not None and info["est"] > 0:
        parts.append(f"실측 {actual:.1f}초(실측÷추정 ×{actual / info['est']:.2f})")
    return " · ".join(parts)


def forecast_table(ranges: dict[str, list[str]], texts: dict[str, str], raw_reads: dict[str, list[str]], ledger: dict[str, float],
                   touching: Callable, ambient: Callable, shares: tuple[float, ...] = (0.9, 0.5, 0.3, 0.1), par: int = FORECAST_PAR) -> list[str]:
    """정확도 단계별 표 — 바뀐 범위 × (정적 스캔만 · 배경 문턱 `shares`) 마다 닿는 시험 수 · 정답 대비 · ㉥ 추가 초(`--no-cap`).

    정답 = 배경을 안 빼고 **실제로 연** 파일 전부 ∪ 정적 스캔이다. 「정답 대비」 = 단계의 수 ÷ 정답의 수. 시험이 정적 · 실측 몫을 못 나눈 새 시험은 정적만이다.
    ㉥ 추가 초 = max(닿는 시험의 장부초 합 ÷ `par`, 가장 긴 시험 하나)(장부에 없는 시험은 장부 중앙값으로 친다) — 가장 긴 시험 항이 없던 옛 식은 5개 시험 범위에서 실측 28.4초 대 10.3초(×2.74)였다."""
    med = statistics.median(ledger.values()) if ledger else 0.0
    amb = {s: set(ambient(raw_reads, s)) for s in shares}      # 문턱마다 한 번만 센다(파일마다 다시 세면 수 분이 든다)
    steps = [("A 정적 스캔만", {})] + [(f"배경 문턱 {s:g}", {k: [p for p in v if p not in amb[s]] for k, v in raw_reads.items()}) for s in shares]
    out = ["| 바뀐 범위 | " + " | ".join(name for name, _ in steps) + " |", "|---|" + "---|" * len(steps)]
    for label, changed in ranges.items():
        truth = touching(changed, texts, raw_reads)
        denom = max(len(truth), 1)
        cells = []
        for _, reads in steps:
            t = touching(changed, texts, reads)
            secs = max(sum(ledger.get(n, med) for n in t) / par, max((ledger.get(n, med) for n in t), default=0.0))   # 묶음의 벽시계는 가장 긴 시험 하나보다 짧을 수 없다
            cells.append(f"{len(t)}개 · 정답 대비 {len(t) / denom:.0%} · {secs:.0f}초")
        out.append(f"| {label}({len(changed)}파일) | " + " | ".join(cells) + " |")
    out.append(f"정답 = 배경을 안 빼고 실제로 연 파일 ∪ 정적 스캔 · ㉥ 초 = max(장부초 합 ÷ {par}, 가장 긴 시험) · 시동 · 장부 낡음은 안 센다(실측÷표 ×0.82 ~ ×1.40, 표본 넷 — 하한으로 읽는다) · 상한 없음(`--no-cap`) · 훅은 읽기 장부를 안 읽는다(`--no-touched`)")
    return out


# ── pre-push 예산 판정 — 단일 측정이 아니라 최근 회차의 중앙값 ─────────────────────────────

def read_records(path: Path, key: str) -> list[float]:
    """`key` 가 같은 기록의 초 — 오래된 것부터. 파일이 없거나 깨진 줄은 건너뛴다(기록이 없으면 빈 목록 = 「기록 0」)."""
    out: list[float] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        f = ln.split("\t")
        if len(f) >= 3 and f[2] == key:
            try:
                out.append(float(f[1]))
            except ValueError:
                continue
    return out


def append_record(path: Path, secs: float, key: str, keep: int = KEEP) -> None:
    """한 줄(`시각 TAB 초 TAB 키`)을 더하고 최근 `keep` 줄만 남긴다. 쓰지 못하면 조용히 넘어간다 — 기록은 부가이고 훅이 이 때문에 죽지 않는다."""
    try:
        old = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        path.write_text("\n".join([*old, f"{int(time.time())}\t{secs:.1f}\t{key}"][-keep:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def judge(prev: list[float], now: float, budget: float, n: int = N_RECENT) -> tuple[str, str]:
    """순수 함수 — (등급, 한 줄). 등급: `cry`(중앙값이 예산 초과) · `note`(이번만 초과) · `short`(기록이 `n` 개 미만) · `ok`.

    창 = 이번 회차를 포함한 최근 `n` 회. 창이 덜 찼으면 중앙값이 없다 — 이번만 초과해도 **울지 않고** 알린다(기록 k/n)."""
    win = [*prev, now][-n:]
    if len(win) < n:
        msg = f"기록 {len(win)}/{n} — 중앙값은 {n}회가 쌓인 뒤에 낸다"
        return "short", (f"이번 회차 {now:.1f}초가 예산 {budget:g}초를 넘었다({msg})" if now > budget else f"이번 회차 {now:.1f}초({msg})")
    med = statistics.median(win)
    if med > budget:
        return "cry", f"최근 {n}회 중앙값 {med:.1f}초가 예산 {budget:g}초를 넘었다(이번 회차 {now:.1f}초 · 흔들림이 아니라 느려진 것이다)"
    if now > budget:
        return "note", f"이번 회차 {now:.1f}초(중앙값 {med:.1f}초) — 예산 {budget:g}초를 넘었으나 최근 {n}회 중앙값은 안이다(호스트 흔들림으로 읽는다)"
    return "ok", f"최근 {n}회 중앙값 {med:.1f}초(이번 회차 {now:.1f}초 · 예산 {budget:g}초)"


# ── 예보와 실측의 비 — 같은 축의 최근 회차 안에서 본다 ─────────────────────────────────────

def read_ratios(path: Path, axis: str) -> list[float]:
    """`axis` 가 같은 기록의 비(실측÷모형 추정) — 오래된 것부터. 깨진 줄 · 없는 파일은 건너뛴다. 줄 = `시각 TAB 비 TAB 축 TAB 추정 TAB 실측`."""
    out: list[float] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        f = ln.split("\t")
        if len(f) >= 3 and f[2] == axis:
            try:
                r = float(f[1])
            except ValueError:
                continue
            if r > 0:
                out.append(r)
    return out


def append_ratio(path: Path, est: float, secs: float, axis: str, keep: int = KEEP) -> None:
    """비 한 줄을 더하고 최근 `keep` 줄만 남긴다. 못 쓰면 조용히 넘어간다 — 기록은 부가이고 시험 묶음이 이 때문에 죽지 않는다(`append_record` 와 같다)."""
    if est <= 0 or secs <= 0:
        return
    try:
        old = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        path.write_text("\n".join([*old, f"{int(time.time())}\t{secs / est:.3f}\t{axis}\t{est:.1f}\t{secs:.1f}"][-keep:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def corrected(prev: list[float], est: float, n: int = N_RATIO, k_min: int = MIN_RATIO) -> tuple[float | None, str]:
    """(보정 예보 초 | None, 한 줄). 같은 축 최근 `n` 회 비의 **중앙값**을 모형 추정에 곱한다. 직전 기록이 `k_min` 개 미만이면 보정 없이 「기록 k/k_min」을 말한다."""
    win = prev[-n:]
    if len(win) < k_min:
        return None, f"보정 없음 — 같은 축 기록 {len(win)}/{k_min}(모형 추정만 말한다)"
    m = statistics.median(win)
    return est * m, f"보정 예보 {est * m:.1f}초(같은 축 최근 {len(win)}회 실측÷추정 중앙값 ×{m:.2f} · 최소 ×{min(win):.2f} 최대 ×{max(win):.2f})"


def _fold(r: float, m: float) -> float:
    return max(r / m, m / r)


def ratio_verdict(prev: list[float], now: float, n: int = N_RATIO, k_min: int = MIN_RATIO, band: float = BAND, spike: float = SPIKE) -> tuple[str, str]:
    """순수 함수 — (등급, 한 줄). 등급: `cry` · `note`(이번만 `spike` 초과) · `short`(센 몫이 되는 회차가 `k_min` 미만) · `ok`.

    보정 오차 = 그 회차의 비를 **직전 `n` 회 중앙값**으로 보정했을 때의 어긋남(1 이상으로 접는다). 직전 기록이 `k_min` 개 이상인 회차만 센다.
    창 = 이번을 포함한 최근 `n` 회 중 센 수 있는 것들 — 그 오차들의 중앙값이 `band` 를 넘으면 운다(보정이 계속 틀린다 = 모형이나 호스트가 바뀌었다)."""
    seq = [*prev, now]
    errs = [_fold(seq[i], statistics.median(seq[max(0, i - n):i])) for i in range(max(k_min, len(seq) - n), len(seq))]
    if len(errs) < k_min:
        return "short", f"비 판정은 센 수 있는 회차가 {k_min} 개 쌓인 뒤에 낸다(지금 {len(errs)}/{k_min} · 이번 비 ×{now:.2f})"
    med = statistics.median(errs)
    if med > band:
        return "cry", f"보정이 안 맞는다 — 최근 {len(errs)}회 보정 오차 중앙값 ×{med:.2f}가 ×{band:g}를 넘었다(이번 비 ×{now:.2f} · 모형이나 호스트가 바뀌었다 · 예보를 믿지 마라)"
    if errs[-1] > spike:
        return "note", f"이번 회차 비 ×{now:.2f}는 보정에서 ×{errs[-1]:.2f} 벗어났다(최근 {len(errs)}회 오차 중앙값 ×{med:.2f}는 안이다 · 호스트 흔들림으로 읽는다)"
    return "ok", f"비 판정 안 — 최근 {len(errs)}회 보정 오차 중앙값 ×{med:.2f}(밴드 ×{band:g})"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="testforecast", description=__doc__.split("판별식")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge", help="이번 회차를 기록에 더하고 한 줄을 낸다(훅이 부른다 · 종료 코드 2 = 중앙값이 예산 초과 · 그 밖은 0)")
    j.add_argument("--file", required=True, type=Path)
    j.add_argument("--secs", required=True, type=float)
    j.add_argument("--key", required=True)
    j.add_argument("--budget", required=True, type=float)
    j.add_argument("--n", type=int, default=N_RECENT)
    a = ap.parse_args(argv)
    prev = read_records(a.file, a.key)
    level, msg = judge(prev, a.secs, a.budget, a.n)
    append_record(a.file, a.secs, a.key)
    print(("\033[33m⚠ " if level == "cry" else "  ") + msg + ("\033[0m" if level == "cry" else ""))
    return 2 if level == "cry" else 0


if __name__ == "__main__":
    sys.exit(main())
