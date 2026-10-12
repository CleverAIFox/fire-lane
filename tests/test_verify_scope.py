"""영향 범위 선언 — `verify.sh --since` 가 **조용히 건너뛰지 않는가** (W7-2).

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-19. `--since=REF` 를 만들면서 **만든 그 자리에서 1족을 냈다.**

    _touches $_scope          ← 안 따옴표

셸이 `web/navi/*` 를 **실제 파일 목록으로 펼쳐버린다.** 패턴이 패턴으로
도착하지 않고 직계 자식 목록이 되므로 `web/navi/src/App.tsx` 를 **못 잡는다.**
즉 내비를 고쳤는데 「내비 타입 검사」가 조용히 건너뛰어진다 —
**초록불인데 아무것도 안 본** 상태다. 실측으로 잡았고 `set -f` 로 고쳤다.

★ 이 파일이 존재하는 이유가 그것이다. 범위 기반 실행은 **빨라지는 대신
  안 도는 것이 생기는** 기능이라, 「안 돈 것이 안 돌아야 했던 것인가」를
  기계가 물어야 한다. 사람이 읽어서 맞히는 것은 한 번은 되고 두 번은 안 된다.

★ 안전망은 셋이다.
    ① 미선언은 항상 돈다 — 손목록이 빠져도 안전한 쪽으로 틀린다
    ② `--since` 는 `부분 실행` 안전장치를 켠다 — 봉인·수용이 불가능하다
    ③ 이 파일 — 선언이 떠 있거나, 없는 경로를 가리키거나,
       매칭이 죽으면 운다
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "tools" / "verify.sh"

SCOPE_LINE = re.compile(r'^\s*scope "([^"]*)"', re.M)


VAR_LINE = re.compile(r'^([A-Z_]+)="([^"]*)"', re.M)


def _patterns() -> set[str]:
    """선언에 쓰인 패턴 전부. **변수는 펼친다.**

    ★ 2026-09-20. 종전에는 리터럴만 읽었고, `scope "$CODE_SCOPE"` 가
      들어오자 `$CODE_SCOPE` 라는 **경로가 없다**고 울었다. 검사가 자기
      대상의 문법 절반을 몰랐던 것이다 — 그대로 두면 변수를 쓰는 선언은
      영영 못 쓰거나, 이 시험을 끄게 된다.
    """
    src = VERIFY.read_text(encoding="utf-8")
    env = {m.group(1): m.group(2) for m in VAR_LINE.finditer(src)}
    out: set[str] = set()
    for m in SCOPE_LINE.finditer(src):
        for tok in m.group(1).split():
            if tok.startswith("$"):
                name = tok[1:].strip("{}")
                assert name in env, f"scope 가 모르는 변수를 쓴다 — {tok}"
                out.update(env[name].split())
            else:
                out.add(tok)
    return out


def test_scope_declarations_are_all_attached() -> None:
    """떠 있는 선언이 없는가.

    ★ 판정을 **여기서 다시 구현하지 않는다.** `verify.sh --scope-list` 가
      정본이고 이 시험은 그것을 부를 뿐이다 — 파싱 규칙을 두 곳에 적으면
      그 순간 2족이 된다.
    ★ `--scope-list` 는 아무것도 실행하지 않는다(정적 읽기).
    """
    r = subprocess.run(["bash", str(VERIFY), "--scope-list"],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, (
        "어느 단계에도 안 붙은 `scope` 선언이 있다.\n"
        + r.stdout[-1500:]
        + "\n  붙지 않은 선언은 아무 일도 안 하면서 「범위를 적었다」고\n"
        + "  믿게 만든다 — 있다고 적혀 있으면 사람이 안 본다.")


def test_scope_patterns_point_at_real_paths() -> None:
    """선언이 **실재하는 뿌리**를 가리키는가.

    ★ `web/nav/*` 처럼 한 글자만 틀려도 그 단계는 `--since` 에서 **영원히
      건너뛰어진다.** 아무것도 안 울고, 빨라졌다고 느낀다. 최악의 형태다.
    """
    bad = []
    for pat in sorted(_patterns()):
        root = pat.split("*", 1)[0].rstrip("/")
        if root and not (ROOT / root).exists():
            bad.append(f"  scope \"{pat}\" — `{root}` 가 저장소에 없다")
    assert not bad, (
        "영향 범위 선언이 없는 경로를 가리킨다.\n" + "\n".join(bad)
        + "\n  한 글자만 틀려도 그 단계는 --since 에서 영영 안 돈다.")


@pytest.mark.parametrize(
    ("changed", "pattern", "want"),
    [
        # ★ 회귀 — 이것이 2026-09-19 에 실제로 틀렸던 조합이다.
        ("web/navi/src/App.tsx", "web/navi/*", True),
        ("web/navi/src/ui/Panel.tsx", "web/* tools/*.mjs", True),
        ("src/firelane/seg/width.py", "src/* tools/*", True),
        ("docs/PLAN.md", "docs/*", True),
        ("docs/PLAN.md", "web/navi/*", False),
        ("web/data/x.json", "data/*", False),
        (".github/workflows/contract.yml", ".github/*", True),
    ],
)
def test_touches_matches_nested_paths(changed: str, pattern: str, want: bool) -> None:
    """`_touches` 가 **깊은 경로**를 잡는가 — 프로브가 살아 있는가.

    ★ 함수를 `verify.sh` 에서 **그대로 떼어다** 돌린다. 여기에 같은 로직을
      다시 적으면 이 시험은 자기가 적은 것을 시험하게 된다 — 그러면 진짜
      `verify.sh` 가 고장나도 초록이다(`deadcheck ①` 가 묻는 그 물음).
    """
    src = VERIFY.read_text(encoding="utf-8")
    m = re.search(r"^_touches\(\) \{.*?^\}", src, re.M | re.S)
    assert m, "verify.sh 에서 _touches 를 못 찾았다 — 이 시험이 빈 그물이 됐다"

    script = f'CHANGED="{changed}"\n{m.group(0)}\n_touches "{pattern}"'
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    got = r.returncode == 0
    assert got is want, (
        f"_touches 가 틀렸다 — 바뀐 것 {changed!r} · 범위 {pattern!r}\n"
        f"  기대 {'돈다' if want else '건너뜀'} · 실제 {'돈다' if got else '건너뜀'}\n"
        "  범위가 좁으면 고친 것을 검사하지 않고 초록이 뜬다.\n"
        "  (2026-09-19: 인자를 안 따옴표로 넘겨 셸이 패턴을 파일 목록으로\n"
        "   펼쳤고 `web/navi/*` 가 `web/navi/src/App.tsx` 를 못 잡았다)")


def test_since_forces_partial_run_safety_net() -> None:
    """`--since` 가 `부분 실행` 안전장치를 켜는가.

    ★ 이것이 없으면 `--since` 로 돈 반쪽 로그를 `dms.py seal` 이 전수로
      착각하고 봉인한다 — `--fast` 가 2026-09-15 에 그랬던 자리다.
    ★ 문자열로 본다. 실제로 돌리려면 레이크와 의존성이 필요하고, 여기서
      묻는 것은 「조건에 `--since` 가 들어 있는가」 하나다.
    """
    src = VERIFY.read_text(encoding="utf-8")
    m = re.search(r'^if \[ -n "\$ONLY" \].*$', src, re.M)
    assert m, "`부분 실행` 안전장치의 조건줄을 못 찾았다"
    assert '-n "$SINCE"' in m.group(0), (
        "`--since` 가 `부분 실행` 안전장치에 안 걸려 있다.\n"
        f"  지금: {m.group(0).strip()}\n"
        "  건너뛴 것은 통과가 아니다 — 범위 기반 실행은 수용이 아니라\n"
        "  고치는 중에 쓰는 되먹임 도구다(§13-5 규약 6).")


# ★ 2026-09-20 (W7-3). 선언을 12 → 20 으로 올리면서 **여덟이 같은 범위**를
#   쓰게 됐다. 손으로 여덟 번 적으면 한쪽만 넓히는 사고가 나고, 그때
#   좁은 쪽 단계는 **고친 것을 안 보고 초록**이 된다 — W3-11 과 같은 자리다.
PIPE_STEPS = (
    "파이프라인 전량", "golden 판정 불변", "golden 게이트 해제 경로",
    "커밋된 web/data 가 최신인가", "레이크 선언↔실물", "레이크 정리 대상",
    "레이크 관문", "norm 계보 재현",
)


def test_pipeline_family_shares_one_scope_home() -> None:
    """파이프라인에 기대는 단계들이 **같은 변수**를 쓰는가."""
    src = VERIFY.read_text(encoding="utf-8")
    assert "CODE_SCOPE=" in src, "`CODE_SCOPE` 정본이 없다"
    assert src.count("CODE_SCOPE=") == 1, "`CODE_SCOPE` 의 집이 둘 이상이다"
    bad = []
    for name in PIPE_STEPS:
        # ★ 2026-10-11 (DECISIONS §456-1 ⑨). **주석 줄은 건너뛴다.** 단계가
        #   제 물음을 적는 `# asks:` 줄이 그 사이에 들어왔고, 주석 하나가
        #   끼었다고 범위의 집이 달라지는 것은 아니다. 묻는 것은 「그 단계가
        #   공용 범위를 쓰는가」이지 「두 줄이 붙어 있는가」가 아니다.
        m = re.search(rf'^((?:\s*#.*\n)*)(.*)\n(?:\s*#.*\n)*\s*step "{re.escape(name)}"',
                      src, re.M)
        if not m or 'scope "$CODE_SCOPE"' not in m.group(2):
            bad.append(f"  {name} — 바로 위 줄이 `scope \"$CODE_SCOPE\"` 가 아니다")
    assert not bad, (
        "파이프라인 계열 단계가 공용 범위를 안 쓴다.\n" + "\n".join(bad)
        + "\n\n  손으로 여덟 번 적으면 한쪽만 넓히게 되고, 좁은 쪽은\n"
          "  고친 것을 안 보고 초록이 뜬다(PLAN §13 W3-11 과 같은 족).")


def test_code_scope_covers_everything_that_moves_output() -> None:
    """공용 범위가 **산출에 닿는 층을 다 덮는가.**

    ★ 이 시험은 「좁아지는 것」만 잡는다. 넓은 것은 결함이 아니다 —
      과하게 도는 쪽은 느릴 뿐이고, 좁은 쪽은 **거짓 초록**이다.
    """
    src = VERIFY.read_text(encoding="utf-8")
    m = re.search(r'^CODE_SCOPE="([^"]*)"', src, re.M)
    assert m, "`CODE_SCOPE` 선언을 못 읽었다"
    pats = set(m.group(1).split())
    # 봉인 `code` 가 `uv.lock` 까지 세고(shardseal.code_print), `cfg` 는 대장을 센다.
    for need in ("src/*", "tools/*", "data/*", "sources.yaml", "uv.lock"):
        assert need in pats, (
            f"`{need}` 가 CODE_SCOPE 에 없다 — 그 층을 고친 배치가 파이프라인을\n"
            "  안 돌고 초록이 뜬다. 봉인 code 는 uv.lock 까지, cfg 는 대장까지 센다.")


#: ★ 2026-10-10 (DECISIONS §457). 여기 있던 **손으로 적은** `SCOPE_FLOOR = 33` 을
#:   지웠다. 실측이 82 가 될 때까지 **49 뒤처져 있었고**, 그 사이 선언이 썩어도
#:   안 울었다. 손으로 적은 바닥은 그 자체가 낡는다(이 저장소가 세 번 겪었다 —
#:   23 → 33 → 31 → 33 이 전부 사람이 옮긴 수다).
#:   바닥의 집은 이제 `tools/scopedecl.py` 의 `RATCHETS["VERIFY_NO_SCOPE"]` 이고
#:   `ratchet.py --write` 가 **조이는 쪽으로만** 움직인다. 세는 양도 바꿨다 —
#:   「선언이 몇인가」가 아니라 **「미선언이 몇인가」**다. 미선언 단계는 영향 범위를
#:   아무도 모르는 상태이고, 그 수가 늘면 운다.
#: ★ 이 시험이 남아서 묻는 것은 **다른 물음**이다 — 아래 ★.


def test_the_two_scope_counters_agree() -> None:
    """선언 수를 재는 **두 자가 같은 답을 내는가.**

    ★ 2026-10-10 (DECISIONS §457). `verify.sh --scope-list` 는 셸이 제 단계를
      돌며 세고, `scopedecl.verify_scope_counts()` 는 그 파일을 **밖에서 읽어**
      센다. 둘이 갈리면 래칫이 재는 수가 실물과 다르다는 뜻이고, 그때
      `VERIFY_NO_SCOPE` 는 **아무것도 안 지킨다.**

    ★ 이 저장소가 그 족을 여러 번 겪었다 — 「자가 틀리면 그 수는 수가 아니다」.
      래칫을 믿으려면 그 수를 내는 자를 따로 대야 한다.
    """
    import re

    import scopedecl
    r = subprocess.run(["bash", str(VERIFY), "--scope-list"],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    m = re.search(r"선언 (\d+) · 미선언 (\d+) · 단계 (\d+)", r.stdout)
    assert m, "--scope-list 가 합계 줄을 안 낸다"
    shell = (int(m.group(1)), int(m.group(2)))
    direct = scopedecl.verify_scope_counts()
    assert shell == direct, (
        f"두 자가 다른 답을 낸다 — `--scope-list` {shell} vs "
        f"`scopedecl.verify_scope_counts()` {direct}\n"
        "  래칫 `VERIFY_NO_SCOPE` 가 뒤쪽 수를 쓴다. 갈리면 그 래칫은 아무것도\n"
        "  안 지킨다. 두 파서 중 어느 쪽이 틀렸는지 읽어라.")
    assert sum(shell) == int(m.group(3)), (
        f"선언 {shell[0]} + 미선언 {shell[1]} 이 단계 {m.group(3)} 과 안 맞는다")

    # ★ 카나리아 — 합성 결함을 **양쪽으로** 민다(§445 의 정의).
    #   이것이 없으면 파서가 늘 `(0, 0)` 을 내도 위 대조가 통과한다.
    _one = 'scope "src/*"\nstep "가" uv run x\n'
    _bare = 'step "나" uv run y\n'
    assert scopedecl.verify_scope_counts(_one) == (1, 0), "선언을 못 센다"
    assert scopedecl.verify_scope_counts(_bare) == (0, 1), "미선언을 못 센다"
    assert scopedecl.verify_scope_counts(_one + _bare) == (1, 1), "둘을 못 가른다"
    # ★ 선언은 **한 단계에만** 걸린다 — verify.sh 의 `step()` 이 그렇게 돈다.
    assert scopedecl.verify_scope_counts(_one + _bare + _bare) == (1, 2), \
        "선언이 다음 단계로 새고 있다"
    assert not scopedecl.verify_scope_counts("")[0], "빈 글에서 선언을 센다"
    assert not scopedecl.verify_scope_counts("")[1], "빈 글에서 미선언을 센다"


def test_every_shared_tool_step_says_what_it_asks() -> None:
    """같은 검사기를 두 단계 이상이 부르면 **그 단계가 제 물음을 적는가.**

    ★ 2026-10-11 (DECISIONS §456-1 ⑨). `tools/toolindex.py` 가 「도구마다 제
      설명이 한 벌 있는가」를 드는데 그 단위가 **도구**다. 하위명령이 다르면
      묻는 것이 다른데 그 차이를 적은 자리가 없었다 — 단계 이름이 유일한
      힌트였고, 그래서 「이 단계가 무엇을 묻나」를 기계가 못 물었다.

    ★ 글자까지 같은 선언 둘은 **선언이 아니다.** 베끼면 갈린다(2족) — 그
      자리가 바로 `toolindex` 가 「설명이 다른 도구와 글자 그대로 같다」를
      실패로 두는 사유다.
    """
    import scopedecl

    assert not scopedecl.step_ask_gaps(), (
        "같은 검사기를 부르는 단계가 제 물음을 안 적었다:\n  "
        + "\n  ".join(scopedecl.step_ask_gaps()))

    # ★ 카나리아 — 합성 결함을 **양쪽으로** 민다(§445 의 정의).
    _two = ('scope "x"\nstep "가" uv run python tools/golden.py check\n'
            'scope "x"\nstep "나" uv run python tools/golden.py selftest\n')
    assert len(scopedecl.step_ask_gaps(_two)) == 2, "선언 없는 둘을 안 센다"
    _said = ('# asks: 지문이 정답과 같은가\n'
             'step "가" uv run python tools/golden.py check\n'
             '# asks: 그 게이트가 또 풀리는가\n'
             'step "나" uv run python tools/golden.py selftest\n')
    assert not scopedecl.step_ask_gaps(_said), "적었는데도 센다"
    _same = _said.replace("그 게이트가 또 풀리는가", "지문이 정답과 같은가")
    assert scopedecl.step_ask_gaps(_same), "글자까지 같은 선언 둘을 통과시킨다"
    # ★ 한 단계만 부르는 검사기는 **안 센다** — 그쪽은 `toolindex` 가 든다.
    _solo = 'step "가" uv run python tools/golden.py check\n'
    assert not scopedecl.step_ask_gaps(_solo), "혼자 부르는 자리를 센다"
    # ★ 선언은 **그 단계에만** 걸린다. 사이에 명령이 끼면 끊긴다.
    _leak = ('# asks: 가\nscope "x"\nstep "가" uv run python tools/golden.py check\n'
             '# asks: 나\nstep "나" uv run python tools/golden.py selftest\n')
    assert scopedecl.step_ask_gaps(_leak), "scope 줄을 넘어 선언이 새고 있다"
