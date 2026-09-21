#!/usr/bin/env python3
"""
test_seal_survives_squash.py — **봉인이 스쿼시를 타지 않는 자리에서 찍히는가.**

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-20 (PLAN §13 W11-1 · DECISIONS §204 · §207). `data/dms/SEAL.json` 의
`commit` 이 `2130b14` 였는데 **이 저장소에 없는 커밋**이었다.

    $ git cat-file -t 2130b14
    fatal: Not a valid object name 2130b14
    $ git for-each-ref --contains 2130b14
    refs/remotes/allrefs/pull/108/head          ← 여기에만 있다

PR #108 을 **스쿼시**로 머지하고 브랜치를 지웠기 때문이다. 봉인은 「이 지점까지
정합한다」고 말하는데 그 지점이 저장소 역사에 없었다.

★ **근본 원인은 「깜빡했다」가 아니다.** 봉인은 커밋 해시를 적고, `cmd_seal` 이
  `SEAL.json` 을 쓴 뒤 사람이 그것을 커밋하므로 불변은 `봉인 == HEAD^` 다.
  그런데 배치는 스쿼시로 `part/infra` 에 들어가므로 **그 `HEAD^` 가 반드시
  사라진다.** 다시 찍어도 다음 배치에 또 난다 — 구조가 그렇게 만든다.

★ 그래서 찍는 **자리**를 옮겼다. 스쿼시 **뒤** `part/infra` 에서 찍으면 그 커밋은
  `part/infra` → (merge commit) → `dev` → `main` 을 타고 가므로 **영원히 main 의
  조상**이다. 스쿼시를 한 번도 안 탄다.

★ **아직 못 세우는 가드가 하나 있다** — 「봉인 커밋이 `main` 의 조상인가」.
  지금 봉인은 옛 절차로 찍힌 것이라 그 물음에 **빨강**이고, 빨간 가드를 배치에
  넣으면 §13-5 규약 6(로컬·CI 둘 다 초록)을 어긴다. 게다가 `dms seal` 은 verify
  초록을 요구하므로 가드가 빨가면 **영영 못 찍는다**(자기참조).
  **한 번 릴리즈가 돌아 좋은 봉인이 생긴 뒤에 그 가드가 선다** — W11-1 이
  그때까지 열려 있는 이유다. 여기서는 **기구가 제자리에 있는지**만 든다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MB = ROOT / "tools" / "merge_batch.sh"


def _src() -> str:
    return MB.read_text(encoding="utf-8")


def test_the_probe_is_not_an_empty_net():
    """`merge_batch.sh` 를 읽고 A·B 단계를 찾아내는가."""
    s = _src()
    assert len(s) > 2000, "merge_batch.sh 가 너무 짧다 — 이 검사가 빈 그물이 됐다"
    assert "part/infra" in s and "--release" in s, "방송 도구가 아닌 것 같다"


def test_seal_runs_on_part_infra_not_on_the_feat_branch():
    """봉인이 **`part/infra` 로 옮긴 뒤에** 찍히는가.

    ★ feat 가지에서 찍으면 그 커밋이 스쿼시로 사라진다. 이 순서가 이 배치의 전부다.
    """
    s = _src()
    m = re.search(r"uv run python tools/dms\.py seal", s)
    assert m, (
        "`merge_batch.sh` 가 더는 봉인을 찍지 않는다.\n"
        "  그러면 봉인은 다시 사람이 feat 가지에서 찍게 되고, 그 커밋은\n"
        "  스쿼시로 사라진다(W11-1 · DECISIONS §207).")
    before = s[:m.start()]
    sw = list(re.finditer(r'git switch -q (?:-c )?["\']?part/infra', before))
    assert sw, (
        "봉인 직전에 `part/infra` 로 옮기는 줄이 없다.\n"
        "  그 자리가 아니면 스쿼시로 사라지는 커밋을 또 가리킨다.")
    # 그 사이에 다른 가지로 옮기지 않는다
    tail = before[sw[-1].end():]
    assert "git switch" not in tail, (
        "`part/infra` 로 옮긴 뒤 봉인 전에 또 가지를 옮긴다 — 어디서 찍히는지 모른다")


def test_seal_is_committed_and_pushed():
    """찍기만 하고 커밋을 안 하면 아무 일도 안 일어난 것과 같다."""
    s = _src()
    i = s.index("uv run python tools/dms.py seal")
    win = s[i:i + 900]
    for need, why in (
        ("git add data/dms/SEAL.json", "봉인 파일을 스테이징하지 않는다"),
        ("git commit", "봉인을 커밋하지 않는다 — 다음 fetch 에 사라진다"),
        ("git push", "봉인을 원격에 안 민다 — dev PR 이 그것을 못 싣는다"),
    ):
        assert need in win, (
            f"봉인 뒤에 `{need}` 가 없다 — {why}.\n"
            "  봉인은 **커밋본의 기준선**이다. 작업 트리에만 있으면 기준선이 아니다.")


def test_seal_happens_before_the_dev_merge():
    """봉인이 dev 머지보다 **먼저**인가.

    ★ 나중이면 그 봉인은 이번 릴리즈에 안 실린다. GitHub PR 은 브랜치 머리를
      따라가므로 PR 을 연 뒤에 밀어도 되지만, **머지보다는 앞서야** 한다.
    """
    s = _src()
    seal = s.index("uv run python tools/dms.py seal")
    merge = s.index('gh pr merge "$pr" -R "$REPO" --merge')
    assert seal < merge, (
        "봉인이 dev 머지보다 뒤에 있다 — 이번 릴리즈에 안 실린다.\n"
        "  A 단계의 `gh pr merge` 앞으로 옮겨라.")


def test_seal_failure_does_not_block_the_release():
    """봉인을 못 찍었을 때 **멈추지 않는가.**

    ★ 봉인은 **기준선이지 관문이 아니다.** 여기서 죽으면 빨간 강제자 하나 때문에
      릴리즈 전체가 막히고, 그러면 사람이 이 단계를 지운다 — 그것이 이 저장소가
      반복해 당한 모양이다(못 지키는 문턱은 끄게 되고, 끈 문턱은 없는 것과 같다).
      못 찍었다는 사실을 **말하고** 넘어간다.
    """
    s = _src()
    i = s.index("uv run python tools/dms.py seal")
    # ★ **주석을 뺀 뒤에 본다.** 2026-09-21 에 이 검사가 제 머리말의
    #   「여기서 die 하면」이라는 **설명 문장**을 코드로 읽고 빨개졌다.
    #   `tests/test_tools_are_wired.py` 가 2026-09-20 에 배운 것과 같은 구멍이다 —
    #   주석은 배선이 아니다. 같은 병을 하루 만에 다시 앓았다.
    # ★ 창을 **글자 수로 끊지 않는다.** 1600자로 잘랐더니 창이 다음 절까지 넘어가
    #   거기 있는 무관한 `die` 를 이 블록의 것으로 읽었다. 블록의 끝은
    #   「dev PR 을 찾는 줄」이고, 그것이 경계다. 이것도 같은 병의 다른 얼굴이다 —
    #   **범위를 어림으로 잡으면 어림만큼 틀린다.**
    end = s.index('pr=$(gh pr list -R "$REPO" --base dev', i)
    code = "\n".join(ln for ln in s[i:end].splitlines()
                     if not ln.lstrip().startswith("#"))
    assert "warn" in code, "봉인 실패를 말하지 않는다 — 조용히 넘어가면 없는 것과 같다"
    fail_branch = code.split("else", 1)[-1]
    assert "die" not in fail_branch, (
        "봉인 실패가 `die` 로 릴리즈를 막는다.\n"
        "  봉인은 기준선이지 관문이 아니다 — 막으면 사람이 이 단계를 지운다.")


def test_failed_seal_leaves_no_dirty_tracked_file():
    """봉인이 실패했을 때 **작업 트리를 더럽힌 채 두지 않는가.**

    ★ 2026-09-21 (DECISIONS §208-6). v0.28 뒤에 실제로 났다. `cmd_seal` 은
      사유 없는 빨강을 만나면 `data/dms/RED.txt` 에 빈 사유 줄을 **써놓고**
      거부한다. 사람이 손으로 찍을 때는 「여기 사유를 적어라」는 자리표라
      값이 있는데, **릴리즈 스크립트 안에서는 아무도 안 채운다.**
      추적 파일이 더러운 채 남아 다음 `fl.sh` 가 1단계에서 거부당했다 ——

          ✗ 추적 파일에 변경이 있다.
              M data/dms/RED.txt

    ★ **자동 절차가 남긴 자리표는 선언이 아니라 찌꺼기다.** 실패 가지에서
      되돌린다. 성공 가지에서 되돌리면 안 된다 — 거기서는 사람이 적어둔
      사유가 살아 있어야 한다.
    """
    s = _src()
    i = s.index("uv run python tools/dms.py seal")
    end = s.index('pr=$(gh pr list -R "$REPO" --base dev', i)
    code = "\n".join(ln for ln in s[i:end].splitlines()
                     if not ln.lstrip().startswith("#"))
    fail_branch = code.split("else", 1)[-1]
    assert "RED.txt" in fail_branch, (
        "봉인 실패 가지가 `data/dms/RED.txt` 를 되돌리지 않는다.\n"
        "  `cmd_seal` 이 거기 빈 사유 줄을 써놓고 거부하므로, 그대로 두면\n"
        "  다음 릴리즈가 「추적 파일에 변경이 있다」로 1단계에서 막힌다.")
    ok = ("git checkout" in fail_branch or "git restore" in fail_branch)
    assert ok, "RED.txt 를 **되돌리는** 명령이 아니다 — 언급만으로는 안 지워진다"
    # 성공 가지는 건드리면 안 된다 — 사람이 적어둔 사유가 거기 산다
    ok_branch = code.split("else", 1)[0]
    assert "RED.txt" not in ok_branch, (
        "봉인이 **성공한** 가지에서 RED.txt 를 건드린다.\n"
        "  거기서는 사람이 적어둔 사유가 살아 있어야 한다 — 지우면 그것이 거짓 기록이다.")
