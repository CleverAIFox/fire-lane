#!/usr/bin/env python3
"""
deliver.py — **배달물이 제 밑동을 증명하는가.** 패치 묶음의 강제자다.

    uv run python tools/deliver.py base   <가지>            원격 팁을 찍는다
    uv run python tools/deliver.py dryrun <가지> <범위>      얹어보고 전수를 돈다
    uv run python tools/deliver.py pack   <가지> <범위> --out DIR
    uv run python tools/deliver.py --selftest               ★ 판정기가 살아 있나

── 왜 생겼나 ──────────────────────────────────────────────────
★ 2026-09-27. 배달 하나에 왕복 셋을 태웠다. 셋 다 보내기 **전에** 기계가 잴
  수 있던 것이다.

    ① 같은 커밋의 패치가 두 이름으로 들어갔다 — `0001-fix-rc-0-272.patch` 와
       `0003-fix-rc-0-272.patch`. 묶는 디렉터리를 비우지 않아서다.
    ② 밑동을 산문으로 **단정했다.** `BASE` 에 `§268` 이라고 적었고 실물은
       `§266` 이었다. `git fetch origin` 한 번이면 알 수 있었다 — 가지는
       `origin/feat/batch-0926` 으로 올라가 있다.
    ③ 「산출물 안 바뀜」·「재잠금 불필요」·「web/data 불변」이 전부 PR 본문의
       **산문**이었다. 맞았지만, 맞은 것은 운이다.

  ★ 형태가 하나다 — **배달물이 제 성질을 주장하고, 그 주장을 사람이 썼다.**
    받는 쪽은 그 주장을 믿고 1분 44초짜리 파이프라인과 8GB 기계를 건다.
    검사가 아니라 **주장의 저자**를 바꿔야 죽는 족이다.

── 무엇을 보는가 ───────────────────────────────────────────────
① **밑동** — `BASE` 를 쓰지 않는다. `origin/<가지>` 에서 **읽어서** 적는다.
   원격에 못 닿으면 배달 자체를 거부한다. 추측이 들어갈 자리를 없앤다.

② **얹힘** — 그 원격 팁 위에 **워크트리를 떠서 실제로 얹는다.** 3way 가
   미끄러지면 내용 기반으로 떨어지는 것까지 받는 쪽 `go.sh` 와 같은 순서다.
   붙지 않으면 zip 이 안 나온다.

②′ **스윕은 `verify.sh` 를 그대로 돈다.** 흉내내지 않는다. 처음에 도구 여섯을
   손으로 들었다가 `deadcheck ②` 에 걸렸고, `step` 줄을 정규식으로 유도했더니
   **60 중 22** 만 잡혔다 — `bash -c` 여러 줄 · `uv run ruff` · `python -m` 형태를
   못 봤고, 그래서 **엄격 린트와 문서 정합 도장이 예습 밖**이었다. 둘 다 실기에서
   빨갛게 났다. 손목록 → 유도 → **원본 실행**. 관문과 예습이 같은 파일이면 갈릴 수가 없다.

③ **실측 → `EXPECT`** — 그 워크트리에서 폐포 지문·`golden.py stale`·`web/data`
   변동·전수 pytest 를 **재고, 잰 수를 `EXPECT` 파일에 적는다.** 받는 쪽
   `go.sh` 는 그 파일을 읽어서 제가 잰 값과 대조한다. 어긋나면 거기서 죽는다.
   PR 본문의 산문이 기계가 낸 수로 바뀐다.

④ **빨간불의 근거 — 이름이 아니라 기준선** . 워크트리·심(shim)·레이크 부재가
   만드는 빨간불이 있다. 그것을 이름 대장으로 면제하면 도장 찍기다(§272 가 바로
   그 족이다). 그래서 **밑동에서 먼저 재고**, `after - base` 만 센다 — 묻는 것은
   「빨간가」가 아니라 **「이 배치가 새로 빨갛게 만들었는가」**다. 대장이 필요한
   자리는 배치가 **새로 넣은** 시험이 레이크 없이는 못 도는 경우 하나뿐이고,
   거기만 `LAKE_ONLY` 에 **판별식과 함께** 적는다. 판별식이 거짓이면 안 봐준다.

⑤ **이름 충돌 · 금지 문자열** — 같은 basename 이 둘이면 거부한다. 커밋
   메시지와 스크립트에 공동저자 줄이 남아 있으면 거부한다(둘 다 실제로 났다).

IN    저장소 · origin/<가지> · 배달 디렉터리
OUT   배달 디렉터리 (fire-lane-0*.patch · BASE · EXPECT) · 표준출력
PARAM LAKE_ONLY · FORBIDDEN · FAIL_LINE
밖    **go.sh 의 내용은 안 짠다.** 그것은 사람이 짜고 이 도구는 `EXPECT` 를
      준다 — 받는 쪽이 무엇을 대조하는가는 `tests/test_expect_contract.py`
      가 본다. 그리고 **`EXPECT` 의 수가 옳은가는 못 본다** — 이 도구가 잰
      것과 받는 쪽이 잰 것이 같은가만 본다. 레이크가 있는 기계에서만 나는
      차이는 ④ 의 판별식이 덮는 만큼만 보장된다.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

# ★ 판별식은 `delivercheck` 가 든다(§276-1). 여기서 다시 정의하면 두 벌이 된다.
from delivercheck import (
    BODY_CHECK,
    FORBIDDEN,
    bodies_bad,
    bodies_missing,
    collide,
    forbidden,
    tails,
)

ROOT = Path(__file__).resolve().parents[1]

# ── ④ 레이크 없는 기계에서만 빨갛다고 인정하는 것 ────────────────
#    (노드 id 조각, 사유, 판별식). 판별식이 거짓인데 빨갛다면 **거부한다.**
LAKE_ONLY: dict[str, tuple[str, str]] = {
    "test_published_polygons_are_well_formed":
        ("커밋된 web/data 가 낡았다 — 발행은 레이크 기계에서만 된다", "no_lake"),
}


# ── ③ 워크트리에서 도는 스윕 ────────────────────────────────────
# ★ 2026-09-27. 종전에는 여섯을 **손으로** 들었다. `deadcheck ②` 가 그것을 잡았다 —
#   「tools 82개 중 6개를 코드에 박았다. 원본에서 유도하지 않으면 늘어도 안 따라간다」.
#   맞는 지적이다. 새 래칫이 `verify.sh` 에 붙어도 배달 예습은 그것을 안 돌았다.
#
#   그래서 **관문의 정본에서 유도한다.** `verify.sh` 의 `step` 줄 중 파이썬 도구를
#   부르는 것을, **인자까지 그대로** 가져온다. 파일 이름만 긁으면 `serve.py`(서버가
#   뜬다)까지 섞인다 — 부르는 형태가 아니라 **부르는 줄**이 정본이다.
#
# ★ 레이크가 필요한 축(`freshcheck` · `lakecheck` · `golden check`)은 여기서 빼지
#   않는다. **기준선 대조가 흡수한다** — 밑동에서도 빨가면 이 배치의 죄가 아니다.
#   빼는 목록을 두면 그것이 또 손목록이고, 같은 결함을 한 칸 옆으로 옮길 뿐이다.
# ★ 2026-09-27 (2차). 유도로 바꿨더니 **22축이었다 — `verify.sh` 의 step 은 60이다.**
#   정규식이 `step "이름" uv run python tools/x.py` 한 형태만 봤고, 실제 관문은
#   `bash -c '…'`(여러 줄) · `uv run pytest` · `uv run ruff` · `python -m firelane.x`
#   로도 부른다. 그래서 **엄격 린트와 문서 정합 도장이 예습 밖**이었고, 둘 다
#   실기에서 빨갛게 났다. 손목록을 유도로 바꾼 것이 부족했다 — **유도의 범위가
#   또 이름보다 좁았다.**
#
#   흉내내기를 그만둔다. **`verify.sh` 를 그대로 돌린다.** 관문과 예습이
#   같은 파일이면 갈릴 수가 없다. 느린 값은 내 시간이지 그의 시간이 아니다.
#
# ★ 실패 이름은 `verify.sh` 가 끝에 찍는 요약에서 읽는다. 종료코드만 보면
#   「무엇이」 빨간지 모르고, 그러면 기준선 대조를 축별로 못 한다.
FAIL_LINE = re.compile(r"^\s+✗\s+(.+?)(?:\s{2,}|$)", re.M)


def _run(args: list[str], cwd: Path | None = None, env: dict | None = None,
         timeout: int = 900) -> tuple[int, str]:
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run(args, cwd=cwd or ROOT, env=e, capture_output=True,
                       text=True, timeout=timeout, check=False)
    return p.returncode, (p.stdout + p.stderr)


def no_lake(root: Path) -> bool:
    """레이크가 없는 기계인가. `LAKE_ONLY` 의 판별식이다."""
    return not (root / "data" / "raw").is_dir()


PREDICATES = {"no_lake": no_lake}


# ── ① 밑동 ──────────────────────────────────────────────────────
#: 새 가지의 밑동. `origin/<가지>` 가 없으면 여기서 읽는다.
FALLBACK_BASE = "part/infra"

#: 패치 이름 접두사. INBOX(다운로드 폴더)는 공용이라 `0001-….patch` 만으로는
#: 남의 저장소 패치와 안 갈린다(§278-5). `fl.sh` 의 낱개 규칙이 이것을 본다.
PATCH_PREFIX = "fire-lane-"


def remote_tip(branch: str, fetch: bool = True) -> tuple[str, str]:
    """`origin/<가지>` 의 실제 팁. **못 읽으면 예외다** — 추측하지 않는다.

    ★ 2026-09-27 (DECISIONS §274-9). **새 가지는 원격에 없다.** 종전에는 그것을
      「origin 에 못 닿았다」로 읽고 배달을 거부했다 — 배치를 새로 뜰 때마다
      걸리는데, 그 상황이 바로 이 도구를 제일 쓰고 싶은 순간이다.
      없으면 **밑동 가지**(`part/infra`)를 읽고 그렇게 말한다. 추측이 아니라
      **다른 참조를 읽는 것**이므로 이 도구의 규율은 그대로다.
    """
    ref = branch
    if fetch:
        rc, out = _run(["git", "fetch", "origin", branch], timeout=180)
        if rc:
            rc2, out2 = _run(["git", "fetch", "origin", FALLBACK_BASE], timeout=180)
            if rc2:
                raise SystemExit(
                    "★ origin 에 못 닿았다 — 밑동을 읽을 수 없으면 배달하지 않는다\n"
                    f"  {branch}: {out}\n  {FALLBACK_BASE}: {out2}")
            ref = FALLBACK_BASE
            print(f"  ★ origin/{branch} 가 아직 없다 — 새 가지다. "
                  f"밑동을 origin/{FALLBACK_BASE} 에서 읽는다")
    rc, sha = _run(["git", "rev-parse", f"origin/{ref}"])
    if rc and ref != FALLBACK_BASE:
        ref = FALLBACK_BASE
        print(f"  ★ origin/{branch} 가 아직 없다 — 밑동을 origin/{ref} 에서 읽는다")
        rc, sha = _run(["git", "rev-parse", f"origin/{ref}"])
    if rc:
        raise SystemExit(f"★ origin/{ref} 가 없다\n{sha}")
    sha = sha.strip()
    _, subj = _run(["git", "log", "-1", "--format=%s", sha])
    return sha, subj.strip()


# ── ⑤ 묶기 전 검사 ──────────────────────────────────────────────


# ── ② 얹힘 ──────────────────────────────────────────────────────
def _apply(wt: Path, patch: Path) -> tuple[bool, str]:
    """받는 쪽 `go.sh` 와 **같은 순서** — 3way → 내용 기반. 다르면 이 예습이 거짓이다."""
    body, diff = wt / ".fl-body", wt / ".fl-diff"
    with patch.open("rb") as fh:
        p = subprocess.run(["git", "mailinfo", str(body), str(diff)], cwd=wt,
                           stdin=fh, capture_output=True, text=True)
    m = re.search(r"^Subject: (.+)$", p.stdout, re.M)
    if not m:
        return False, f"메일 파싱 실패\n{p.stdout}{p.stderr}"
    subject = m.group(1).strip()

    _, hist = _run(["git", "log", "--format=%s", "-80"], cwd=wt)
    if subject in hist.splitlines():
        return True, "이미 들어가 있다"

    rc, out = _run(["git", "am", "--3way", str(patch)], cwd=wt)
    if rc == 0:
        return True, "3way"
    _run(["git", "am", "--abort"], cwd=wt)

    rc, why = _run(["git", "apply", "--check", "-v", str(diff)], cwd=wt)
    if rc:
        return False, f"안 붙는다\n{why}"
    _run(["git", "apply", str(diff)], cwd=wt)
    _run(["git", "add", "-A"], cwd=wt)
    _run(["git", "-c", "user.email=d@d", "-c", "user.name=d",
          "commit", "-q", "-m", subject], cwd=wt)
    return True, "내용 기반"


def _closure(wt: Path, env: dict) -> dict[str, str]:
    code = ("import json;from firelane import shardseal as s;"
            "print(json.dumps({t:s.code_print(t)[:12] for t in "
            "('firelane.ingest','firelane.segments')}))")
    rc, out = _run([str(_py()), "-c", code], cwd=wt, env=env)
    if rc:
        raise SystemExit(f"★ 폐포 지문을 못 떴다\n{out}")
    return json.loads(out.strip().splitlines()[-1])


def _py() -> Path:
    v = ROOT / ".venv" / "bin" / "python"
    return v if v.exists() else Path(sys.executable)


def _wt_env(wt: Path) -> dict:
    """★ 워크트리의 `src` 가 **먼저** 와야 한다. `.venv` 는 본 저장소를 가리키므로
    그냥 돌리면 옛 코드를 재고 「붙였는데 그대로다」라는 거짓말이 나온다."""
    pp = [str(wt / "src")]
    if shim := os.environ.get("FL_PYSHIM"):
        pp.append(shim)
    if old := os.environ.get("PYTHONPATH"):
        pp.append(old)
    return {"PYTHONPATH": os.pathsep.join(pp)}


def dryrun(branch: str, rng: str, patches: list[Path],
           fetch: bool = True, tests: bool = True) -> dict:
    """원격 팁 위에 실제로 얹고 **재서** 사실을 낸다. 여기서 나온 수가 `EXPECT` 다."""
    sha, subj = remote_tip(branch, fetch=fetch)
    wt = Path(tempfile.gettempdir()) / "fl-dryrun"
    if wt.exists():
        _run(["git", "worktree", "remove", "--force", str(wt)])
        shutil.rmtree(wt, ignore_errors=True)
    rc, out = _run(["git", "worktree", "add", "-q", str(wt), sha, "--detach"])
    if rc:
        raise SystemExit(f"★ 워크트리를 못 떴다\n{out}")
    env = _wt_env(wt)
    fact: dict = {"base.sha": sha[:12], "base.subject": subj, "patches": len(patches)}
    try:
        before = _closure(wt, env)
        # ★ **기준선을 먼저 잰다.** 워크트리·심(shim)·레이크 부재가 만드는 빨간불은
        #   배치의 죄가 아니고, 이름으로 면제하면 도장 찍기다. 밑동에서 이미 빨간
        #   것을 빼고 **이 배치가 새로 빨갛게 만든 것**만 센다.
        base_red = _redlist(wt, env) if tests else (set(), "skipped")
        base_sweep = _sweep_red(wt, env)
        for p in patches:
            ok, how = _apply(wt, p)
            print(f"  {p.name:<38} {how.splitlines()[0]}")
            if not ok:
                raise SystemExit(f"★ {p.name} 이 원격 팁에 안 붙는다 — zip 을 내지 않는다\n{how}")
        for junk in (".fl-body", ".fl-diff"):
            (wt / junk).unlink(missing_ok=True)
        after = _closure(wt, env)
        for t in ("firelane.ingest", "firelane.segments"):
            k = t.split(".")[-1]
            fact[f"closure.{k}"] = ("same:" + after[t]) if before[t] == after[t] \
                else f"moved:{before[t]}->{after[t]}"

        rc, _ = _run([str(_py()), "tools/golden.py", "stale"], cwd=wt, env=env)
        fact["golden.relock"] = "no" if rc == 0 else "yes"
        relock = rc != 0

        rc, out = _run(["git", "status", "--porcelain", "--", "web/data"], cwd=wt)
        fact["webdata"] = "unchanged" if not out.strip() else "changed"

        fact["sweep"] = _diff_sweep(base_sweep, _sweep_red(wt, env), wt, relock)
        fact["pytest"] = _diff_tests(base_red, _redlist(wt, env), wt) if tests \
            else "skipped"
    finally:
        _run(["git", "worktree", "remove", "--force", str(wt)])
        shutil.rmtree(wt, ignore_errors=True)
    return fact


def _excused(name: str, wt: Path) -> str | None:
    """④ **판별식이 참일 때만** 면제다. 거짓이면 사유가 있어도 안 봐준다."""
    for frag, (why, pred) in LAKE_ONLY.items():
        if frag in name:
            return why if PREDICATES[pred](wt) else None
    return None


def _sweep_red(wt: Path, env: dict) -> set[str]:
    """`verify.sh` 를 **그대로 돌리고** 빨간 축의 이름만 걷는다. 채집이지 판정이 아니다."""
    rc, out = _run(["bash", "tools/verify.sh"], cwd=wt, env=env, timeout=3600)
    names = set(FAIL_LINE.findall(out))
    if rc and not names:
        # ★ 죽었는데 이름을 못 읽었다. **0건으로 세면 빈 그물이다.**
        names.add(f"verify.sh 가 rc={rc} 로 죽었는데 요약을 못 읽었다 — {out.strip()[-300:]}")
    return names


def _redlist(wt: Path, env: dict) -> tuple[set[str], str]:
    """빨간 노드 id 와 요약 한 줄. 판정이 아니라 **채집**이다."""
    rc, out = _run([str(_py()), "-m", "pytest", "-q", "-p", "no:randomly"],
                   cwd=wt, env=env, timeout=1800)
    red = {l.split()[1] for l in out.splitlines()
           if l.startswith("FAILED") and len(l.split()) > 1}
    tail = [l for l in out.splitlines() if re.search(r"\d+ (passed|failed)", l)]
    return red, (tail[-1] if tail else f"rc={rc}")


def _new(base: set[str], after: set[str], wt: Path, label: str) -> list[str]:
    """**이 배치가 새로 빨갛게 만든 것**만. 면제는 판별식이 참일 때만 붙는다."""
    fresh = sorted(after - base)
    un = [f for f in fresh if not _excused(f, wt)]
    if un:
        raise SystemExit(f"★ 이 배치가 {label} 를 새로 빨갛게 만들었다 — 배달하지 않는다\n  "
                         + "\n  ".join(un))
    return fresh


#: 재잠금이 선언된 배치에서 **빨간 것이 결과인** 축. 사유를 함께 든다.
RELOCK_AXES = {
    "golden 판정 불변":
        "판정 폐포의 코드 지문이 움직였다는 뜻이고, 그것이 곧 재잠금이 필요한 이유다. "
        "`golden.py stale` 이 rc 로 말할 때만 받는다 — 사람이 적는 값이 아니다",
    "커밋된 web/data 가 최신인가":
        "재잠금은 상류를 다시 돌리므로 커밋본이 그 뒤에 온다. 같은 실행에서 커밋된다",
}


def _diff_sweep(base: set[str], after: set[str], wt: Path,
                relock: bool = False) -> str:
    # ★ 재잠금을 **도구가 필요하다고 말한** 배치에서는 위 축이 빨간 것이 결과다.
    #   사람이 「재잠금 배치니까요」라고 적어서 넘기는 것이 아니라, `golden.py stale`
    #   의 rc 가 참일 때만 받는다. 거짓이면 그대로 운다.
    if relock:
        after = after - set(RELOCK_AXES)
    fresh = _new(base, after, wt, "스윕")
    bits = [f"새 빨간불 {len(fresh)}"]
    if base:
        bits.append(f"밑동에서 이미 빨감 {len(base)}({' · '.join(sorted(base))})")
    if fixed := sorted(base - after):
        bits.append(f"이 배치가 고침 {len(fixed)}({' · '.join(fixed)})")
    if relock:
        bits.append(f"재잠금 선언으로 받은 축 {len(RELOCK_AXES)}")
    return " · ".join(bits)


def _diff_tests(base: tuple[set[str], str], after: tuple[set[str], str],
                wt: Path) -> str:
    fresh = _new(base[0], after[0], wt, "시험")
    bits = [after[1], f"새 빨간불 {len(fresh)}"]
    if base[0]:
        bits.append(f"밑동에서 이미 빨감 {len(base[0])}")
    if fixed := sorted(base[0] - after[0]):
        bits.append(f"이 배치가 고침 {len(fixed)}")
    return " · ".join(bits)


# ── ③ EXPECT ────────────────────────────────────────────────────
def render(fact: dict) -> str:
    """받는 쪽이 읽는 계약. **사람이 쓰지 않는다.**"""
    head = ("# EXPECT — tools/deliver.py 가 원격 팁 위에서 **재서** 적었다 (§273).\n"
            "# go.sh 가 제가 잰 값과 대조한다. 어긋나면 거기서 죽는다.\n"
            "# 사람이 고치면 안 된다 — 고치는 것은 주장을 되살리는 것이다.\n")
    return head + "".join(f"{k}={v}\n" for k, v in fact.items())


def parse(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


# ── 하위명령 ────────────────────────────────────────────────────
def cmd_base(a) -> int:
    sha, subj = remote_tip(a.branch)
    print(f"{sha[:12]}  {subj}")
    return 0


def cmd_dryrun(a) -> int:
    pat = f"{PATCH_PREFIX}0*.patch"
    ps = sorted(Path(a.out).glob(pat)) if a.out else sorted(Path().glob(pat))
    if not ps:
        print("★ 패치가 없다"); return 1
    for k, v in dryrun(a.branch, a.range, ps, tests=not a.no_tests).items():
        print(f"  {k:<20} {v}")
    return 0


def cmd_pack(a) -> int:
    out = Path(a.out)
    if out.exists():
        shutil.rmtree(out)          # ★ ① 이름 충돌의 원인 — 묶는 자리를 비운다
    out.mkdir(parents=True)

    sha, subj = remote_tip(a.branch)
    rc, o = _run(["git", "format-patch", a.range, "-o", str(out),
                  "--no-signature", "-q"])
    if rc:
        print(f"★ 패치를 못 떴다\n{o}"); return 1
    # ★ 2026-09-28 (DECISIONS §278-5). INBOX 는 **다운로드 폴더라 공용이다.**
    #   `git format-patch` 이름(`0001-….patch`)은 어느 저장소에서 떠도 같은 꼴이라
    #   남의 프로젝트 패치와 이름만으로는 안 갈린다. zip 은 이미 `fire-lane-*` 인데
    #   낱개로 풀린 패치가 그렇지 않았다. 여기서 접두사를 박아 **파일 이름 자체가
    #   출처를 지게** 한다 — `fl.sh` 의 낱개 규칙도 이 접두사를 본다.
    for p in sorted(out.glob("0*.patch")):
        p.rename(p.with_name(PATCH_PREFIX + p.name))
    ps = sorted(out.glob(f"{PATCH_PREFIX}0*.patch"))
    names = [p.name for p in ps]
    for label, bad in (("이름 충돌", collide(names)), ("같은 꼬리", tails(names)),
                       ("금지 문자열", forbidden(ps))):
        if bad:
            print(f"★ {label} — 배달하지 않는다\n  " + "\n  ".join(bad)); return 1

    print(f"  밑동  {sha[:12]}  {subj}")
    fact = dryrun(a.branch, a.range, ps, fetch=False, tests=not a.no_tests)
    (out / "BASE").write_text(subj + "\n", encoding="utf-8")   # ★ ① 읽어서 적는다
    (out / "EXPECT").write_text(render(fact), encoding="utf-8")
    for k, v in fact.items():
        print(f"  {k:<20} {v}")

    for extra in (a.extra or []):
        src = Path(extra)
        if src.is_file():
            shutil.copy2(src, out / src.name)
    if bad := forbidden(sorted(out.iterdir())):
        print("★ 배달 디렉터리에 금지 문자열이 남았다\n  " + "\n  ".join(bad)); return 1

    # ★ 본문을 **검사기에 태운다.** 산문으로 「넘는다」고 적지 않는다(§276-1).
    names = [f.name for f in out.iterdir() if f.is_file()]
    for label, bad in (("본문 없음", bodies_missing(names)),
                       ("본문이 템플릿을 못 넘는다", bodies_bad(out, _run, str(_py())))):
        if bad:
            print(f"★ {label} — 배달하지 않는다\n  " + "\n  ".join(bad)); return 1
    # ★ **잰 것만 적는다.** 처음엔 `PR_*` 전부를 적었고, 그래서 `PR_TITLE` 까지
    #   「검사 통과」로 찍혔다 — 검사기는 `PR_BODY*.md` 만 태운다. 이 배치가 든
    #   물음이 바로 그것이다(§276-1): **도구가 안 잰 것을 잰 것처럼 말하지 않는다.**
    print(f"  본문   {' · '.join(sorted(f.name for f in out.glob('PR_BODY*.md')))} 검사 통과")

    if a.zip:
        z = Path(a.zip)
        z.unlink(missing_ok=True)
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(out.iterdir()):
                if f.is_file():
                    zf.write(f, f.name)
        print(f"  zip   {z}  sha256 {hashlib.sha256(z.read_bytes()).hexdigest()[:16]}")
    return 0


def selftest() -> int:
    """판별식이 살아 있나. 셋을 일부러 깨고 셋 다 울어야 한다."""
    bad = []
    if collide(["0001-a.patch", "0001-a.patch"]) != ["0001-a.patch"]:
        bad.append("이름 충돌을 못 잡는다")
    if collide(["0001-a.patch", "0002-b.patch"]):
        bad.append("멀쩡한 이름에 운다")
    # ★ §278-5. 접두사가 붙어도 같은 꼬리를 잡는가. 안 떼면 무음으로 통과한다.
    if not tails([f"{PATCH_PREFIX}0001-x.patch", f"{PATCH_PREFIX}0003-x.patch"]):
        bad.append("접두사 붙은 같은 꼬리를 안 잡는다")
    if tails([f"{PATCH_PREFIX}0001-x.patch", f"{PATCH_PREFIX}0002-y.patch"]):
        bad.append("접두사 붙은 다른 꼬리를 잡는다")
    if not tails(["0001-x.patch", "0003-x.patch"]):
        bad.append("번호만 다른 같은 꼬리를 못 잡는다")
    if tails(["0001-x.patch", "0002-y.patch"]):
        bad.append("멀쩡한 꼬리에 운다")
    if not parse(render({"a": "1"})) == {"a": "1"}:
        bad.append("EXPECT 를 적고 되읽지 못한다")
    if parse(render({"a": "1"})).get("#"):
        bad.append("주석을 값으로 읽는다")
    # ★ `deadcheck ③` — 대장이 비면 통과가 아니라 실패다. 비운 채로 초록이면
    #   「금지 문자열 없음」이 「볼 것이 없음」의 다른 말이 된다.
    if not FORBIDDEN:
        bad.append("`FORBIDDEN` 이 비었다 — 볼 것이 없으면 통과가 아니다")
    if not LAKE_ONLY:
        bad.append("`LAKE_ONLY` 가 비었다 — 면제 대장이 비면 ④ 가 죽은 칸이다")
    if not bodies_missing(["0001-x.patch", "EXPECT"]):
        bad.append("`PR_BODY.md` 가 없는데 안 운다")
    if bodies_missing(["PR_BODY.md", "PR_BODY_DEV.md"]):
        bad.append("본문이 있는데 운다")
    if not (ROOT / BODY_CHECK).exists():
        bad.append(f"`{BODY_CHECK}` 가 없다 — 본문 검사가 죽은 칸이다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad)); return 1

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        dirty = Path(td) / "0001-x.patch"
        dirty.write_text(f"제목\n\n{FORBIDDEN[0]} <x@y>\n", encoding="utf-8")
        clean = Path(td) / "0002-y.patch"
        clean.write_text("제목\n\n본문뿐이다\n", encoding="utf-8")
        if not forbidden([dirty]):
            bad.append("금지 문자열을 심었는데 못 잡는다")
        if forbidden([clean]):
            bad.append("멀쩡한 파일에 운다")
        # ★ diff 안의 같은 글자는 **결함이 아니다.** 규약은 커밋 메시지에 걸린다.
        indiff = Path(td) / "0003-z.patch"
        indiff.write_text(f"제목\n\n본문\n---\n a | 1 +\n+{FORBIDDEN[0]}\n",
                          encoding="utf-8")
        if forbidden([indiff]):
            bad.append("diff 안의 글자를 결함으로 센다 — 그 규약을 무는 검사를 못 쓰게 된다")
        inmsg = Path(td) / "0004-z.patch"
        inmsg.write_text(f"제목\n\n{FORBIDDEN[0]} <x@y>\n---\n a | 1 +\n",
                         encoding="utf-8")
        if not forbidden([inmsg]):
            bad.append("메시지의 서명을 못 잡는다")
        # ★ 면제는 **판별식이 참일 때만**이다. 레이크가 있는 자리에서는 안 봐준다.
        frag = next(iter(LAKE_ONLY))
        (Path(td) / "data" / "raw").mkdir(parents=True)
        if _excused(frag, Path(td)) is not None:
            bad.append("레이크가 있는데도 면제해준다 — 도장 찍기다")
        shutil.rmtree(Path(td) / "data")
        if _excused(frag, Path(td)) is None:
            bad.append("레이크가 없는데 면제를 안 해준다")
        if _excused("test_아무거나", Path(td)) is not None:
            bad.append("대장에 없는 빨간불을 면제해준다")
        # ★ 재잠금 축은 **재잠금이 선언됐을 때만** 받는다. 아니면 그대로 운다.
        axis = next(iter(RELOCK_AXES))
        try:
            _diff_sweep(set(), {axis}, Path(td), relock=True)
        except SystemExit:
            bad.append("재잠금 배치에서 재잠금 축에 운다")
        try:
            _diff_sweep(set(), {axis}, Path(td), relock=False)
            bad.append("재잠금이 아닌데 재잠금 축을 받아준다 — 도장 찍기다")
        except SystemExit:
            pass
        # ★ ④ 기준선 대조. 밑동에서 이미 빨간 것은 흡수하고, 새것은 울어야 한다.
        try:
            _new({"a::b"}, {"a::b"}, Path(td), "시험")
        except SystemExit:
            bad.append("밑동에서 이미 빨간 것에 운다 — 기준선을 안 뺀다")
        try:
            _new({"a::b"}, {"a::b", "c::d"}, Path(td), "시험")
            bad.append("이 배치가 새로 빨갛게 만든 것에 안 운다")
        except SystemExit:
            pass
        try:
            _new(set(), {frag}, Path(td), "시험")   # 레이크 없음 → 면제가 맞다
        except SystemExit:
            bad.append("레이크 없는 자리에서 레이크 전용 빨간불에 운다")
    if bad:
        print("★ 자기검사 실패\n  " + "\n  ".join(bad)); return 1
    # ★ 2026-09-27 (§276-1). 종전에는 `18개` 가 **손으로 박혀** 있었다. 팔을
    #   더해도 그 수가 안 따라오므로 곧 거짓이 된다 — 이 저장소가 수를 손으로
    #   적었다가 열두 번 고친 자리와 같은 형태다(PLAN §1 제목 · DECISIONS §246).
    #   판별식 하나가 `bad.append` 하나이므로 **소스에서 센다.**
    arms = inspect.getsource(selftest).count("bad.append(")
    print(f"✓ 자기검사 — 판별식 {arms}개가 다 운다")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="배달물이 제 밑동을 증명하는가")
    ap.add_argument("--selftest", action="store_true")
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("base"); b.add_argument("branch"); b.set_defaults(fn=cmd_base)
    d = sub.add_parser("dryrun")
    d.add_argument("branch"); d.add_argument("range")
    d.add_argument("--out"); d.add_argument("--no-tests", action="store_true")
    d.set_defaults(fn=cmd_dryrun)
    p = sub.add_parser("pack")
    p.add_argument("branch"); p.add_argument("range")
    p.add_argument("--out", required=True); p.add_argument("--zip")
    p.add_argument("--extra", nargs="*"); p.add_argument("--no-tests", action="store_true")
    p.set_defaults(fn=cmd_pack)

    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not getattr(a, "fn", None):
        ap.print_help(); return 1
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
