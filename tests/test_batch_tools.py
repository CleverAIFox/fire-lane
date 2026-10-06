#!/usr/bin/env python3
"""
test_batch_tools.py — **배치 도구가 저장소 안에서 재현되는가.**  (DECISIONS §214-1)

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22. 배치를 돌리는 `fl.sh` · `tidy.sh` 가 INBOX(다운로드 폴더)에만 살았다.
버전 관리 · 시험 밖이었고, INBOX 를 비우자 **도구가 통째로 사라졌다.** 같은 날
레이크 검사(L3)가 INBOX 의 우리 패치 zip 을 「레이크 밖 원본」으로 잡아 verify 가
빨개졌다 — 우리가 만든 포장물을 우리 검사가 모르는 상태였다.

── 무엇을 보는가 ───────────────────────────────────────────────
    1. 세 스크립트가 bash 문법으로 읽힌다
    2. 부트스트랩이 **패치 안의** tools/fl.sh 를 고른다 — 새로 만드는 패치도,
       저장소 판을 고치는 패치도. 없으면 저장소 판
    3. fl.sh 가 방송을 `exec` 하지 않는다 — 뒤에 정리가 있다. 정리는 `--auto`
    4. fl.sh 가 소비한 포장물을 INBOX 에서 치운다
    5. 레이크 처분 목록이 우리 패치 zip 을 안다
"""
from __future__ import annotations

import fnmatch
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "tools"
SCRIPTS = [T / "fl.sh", T / "branch_tidy.sh", T / "inbox_fl.sh"]


def _zip(out: Path, *files: Path) -> None:
    """포장물 zip 을 만든다. ★ `zip` 명령을 쓰지 않는다 — 사용자 기계(WSL)에 없어서
    skip 이 났고, skip 정책(tests/skip_policy.py)이 사유 없는 skip 을 실패로 셌다."""
    import zipfile
    with zipfile.ZipFile(out, "w") as z:
        for f in files:
            z.write(f, f.name)


def test_scripts_parse():
    for s in SCRIPTS:
        assert s.exists(), f"{s.relative_to(ROOT)} 가 없다"
        r = subprocess.run(["bash", "-n", str(s)], capture_output=True, text=True)
        assert r.returncode == 0, f"{s.name} 문법 오류\n{r.stderr}"


def _git(cwd: Path, *a: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True,
                          text=True, env=env).stdout


def _fake(repo: Path, body: str) -> None:
    (repo / "tools").mkdir(exist_ok=True)
    (repo / "tools" / "fl.sh").write_text(f"#!/usr/bin/env bash\necho {body} \"$@\"\n", encoding="utf-8")


def _world(tmp: Path, seed: str | None):
    """bare 원격 · 작업 저장소(origin/part/infra) · INBOX 를 만든다."""
    bare, work, inbox = tmp / "r.git", tmp / "work", tmp / "inbox"
    _git(tmp, "init", "-q", "--bare", str(bare))
    _git(tmp, "clone", "-q", str(bare), str(work))
    (work / "README").write_text("x\n", encoding="utf-8")
    if seed:
        _fake(work, seed)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "init")
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/part/infra")
    _git(work, "fetch", "-q", "origin")
    inbox.mkdir()
    shutil.copy(T / "inbox_fl.sh", inbox / "fl.sh")
    return work, inbox


def _patch(work: Path, body: str, out: Path) -> None:
    _git(work, "switch", "-q", "-c", "tmp-patch", "origin/part/infra")
    _fake(work, body)
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "patch")
    out.write_text(_git(work, "format-patch", "-1", "--stdout"), encoding="utf-8")
    _git(work, "switch", "-q", "-")


def _run(inbox: Path, work: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "FIRE_LANE_REPO": str(work)}
    return subprocess.run(["bash", str(inbox / "fl.sh"), "feat/x", "--all"],
                          capture_output=True, text=True, env=env)


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_prefers_patch_that_creates_the_tool(tmp_path):
    work, inbox = _world(tmp_path, seed=None)
    _patch(work, "NEW", inbox / "0001-fix.patch")
    r = _run(inbox, work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NEW feat/x --all" in r.stdout, r.stdout


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_applies_patch_on_top_of_repo_version(tmp_path):
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "NEWER", inbox / "0001-fix.patch")
    r = _run(inbox, work)
    assert "NEWER feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_survives_its_own_batch_being_merged(tmp_path):
    """★ 2026-10-06 실제 사고 (DECISIONS §402). 배치 Ze 가 `tools/fl.sh` 를 고쳤고,
    머지된 **뒤에** 열차를 다시 불렀다. 씨앗(origin/part/infra)이 이미 그 변경을
    품었는데 zip 은 INBOX 에 남아 있어 `exit 1` 이 났다 — **배치 도구를 고치는
    배치가 머지 직후 자기 열차를 막았다.** 되감아 보면 「이미 들어 있다」가 갈린다.
    """
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "MERGED", inbox / "0001-fix.patch")
    # 스쿼시 머지를 흉내 낸다 — 원격 씨앗이 패치의 결과가 된다
    _git(work, "push", "-q", "-f", "origin", "tmp-patch:refs/heads/part/infra")
    _git(work, "fetch", "-q", "origin")
    r = _run(inbox, work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MERGED feat/x --all" in r.stdout, r.stdout + r.stderr
    assert "씨앗에 이미 있다" in r.stdout, r.stdout


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_falls_back_to_repo_version(tmp_path):
    work, inbox = _world(tmp_path, seed="OLD")
    r = _run(inbox, work)
    assert "OLD feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(부트스트랩 · fl.sh 가 쓴다)")
def test_bootstrap_reads_patch_inside_zip(tmp_path):
    work, inbox = _world(tmp_path, seed="OLD")
    p = tmp_path / "0001-fix.patch"
    _patch(work, "ZIPPED", p)
    _zip(inbox / "fire-lane-x.zip", p)
    r = _run(inbox, work)
    assert "ZIPPED feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(부트스트랩 · fl.sh 가 쓴다)")
def test_bootstrap_same_patch_in_zip_and_loose(tmp_path):
    """평소 절차는 zip 을 INBOX 에 풀어 **같은 패치가 두 벌** 남는다 — 한 번만 얹는다."""
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "ONCE", inbox / "0001-fix.patch")
    _zip(inbox / "fire-lane-x.zip", inbox / "0001-fix.patch")
    r = _run(inbox, work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ONCE feat/x --all" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_bootstrap_ignores_foreign_patches(tmp_path):
    """INBOX 는 공용 다운로드 폴더다. 남의 패치가 tools/fl.sh 를 건드려도 집지 않는다."""
    work, inbox = _world(tmp_path, seed="OLD")
    _patch(work, "FOREIGN", inbox / "D0216.patch")
    r = _run(inbox, work)
    assert "OLD feat/x --all" in r.stdout, r.stdout + r.stderr


FOREIGN = "From x\nSubject: other repo\n---\n+++ b/README\n"


def _pick(inbox: Path) -> list[str]:
    env = {**os.environ, "FIRE_LANE_INBOX": str(inbox), "FIRE_LANE_REPO": str(ROOT)}
    r = subprocess.run(["bash", str(T / "fl.sh"), "feat/x", "--pick"],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    return [l for l in r.stdout.splitlines() if l.endswith(".patch") and "무시" not in l]


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(fl.sh 가 쓴다)")
def test_fl_picks_only_this_batch(tmp_path):
    """2026-09-22 실제 사고 — hathor · thoth 의 패치가 적용 후보에 올라 3단계에서 멈췄다."""
    inbox = tmp_path / "in"
    inbox.mkdir()
    (inbox / "0001-fix.patch").write_text("From a\nSubject: ours\n", encoding="utf-8")
    _zip(inbox / "fire-lane-x.zip", inbox / "0001-fix.patch")
    (inbox / "D0216.patch").write_text(FOREIGN, encoding="utf-8")
    (inbox / "thoth-105-fixture-honest.patch").write_text(FOREIGN + "x", encoding="utf-8")
    assert _pick(inbox) == ["0001-fix.patch"]


def test_fl_without_zip_takes_only_prefixed_patches(tmp_path):
    """zip 없이 낱개로 풀린 패치는 **`fire-lane-` 접두사가 붙은 것만** 집는다.

    ★ 2026-09-28 (DECISIONS §278-5). 종전 규칙은 `0001-….patch` 였는데 그것은
      `git format-patch` 기본 이름이라 **어느 저장소에서 떠도 같은 꼴**이다.
      INBOX 가 다운로드 폴더라 공용인 이상 이름으로 안 갈린다 — 접두사를
      주는 쪽(`deliver.py`)이 박고 여기서 그것을 본다.
    """
    inbox = tmp_path / "in"
    inbox.mkdir()
    (inbox / "fire-lane-0001-a.patch").write_text("From a\n", encoding="utf-8")
    (inbox / "fire-lane-0002-b.patch").write_text("From b\n", encoding="utf-8")
    (inbox / "0003-c.patch").write_text("From c\n", encoding="utf-8")   # ← 접두사 없다. 남의 것일 수 있다
    (inbox / "D0216.patch").write_text(FOREIGN, encoding="utf-8")
    assert _pick(inbox) == ["fire-lane-0001-a.patch", "fire-lane-0002-b.patch"]


def test_deliver_stamps_the_prefix_that_fl_looks_for():
    """★ 주는 쪽과 고르는 쪽이 **같은 접두사**를 봐야 한다. 갈리면 아무것도 안 집는다."""
    d = (T / "deliver.py").read_text(encoding="utf-8")
    f = (T / "fl.sh").read_text(encoding="utf-8")
    assert 'PATCH_PREFIX = "fire-lane-"' in d
    assert "^fire-lane-[0-9]{4}-.+\\.patch$" in f


def test_fl_runs_tidy_after_release_and_clears_inbox():
    s = (T / "fl.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    assert "exec bash tools/merge_batch.sh" not in code, "방송을 exec 하면 정리가 안 돈다"
    assert "bash tools/merge_batch.sh --release" in code
    assert "bash tools/branch_tidy.sh --auto --close-bots" in code, "배치 끝에 가지 정리 · 봇 PR 닫기가 없다(§217-4)"
    assert "tools/tidy.py --yes" in code and "tools/janitor.sh" in code, "배치 끝에 위생이 없다(§217-4)"
    assert "_applied" in code, "소비한 포장물을 INBOX 에서 안 치운다 — 다음 실행이 옛 패치를 또 집는다"
    assert "FL_RELOCATED" in code, "자기 복사 없이 가지를 바꾸면 도는 중에 다른 판을 읽는다"


def test_tidy_auto_never_closes_or_deletes_remote():
    """--auto 는 사람 PR 을 안 닫는다. 봇 PR 은 --close-bots 가 있을 때만(§217-4)."""
    s = (T / "branch_tidy.sh").read_text(encoding="utf-8")
    assert '[ "$BOTS" = 1 ]' in s and "*dependabot*" in s, "봇 PR 을 작성자로 가르지 않는다"
    # ask() 가 --auto 에서 거짓을 내므로 PR 닫기 · 원격 삭제는 대화형에서만 닿는다
    assert '[ "$AUTO" = 1 ] && return 1' in s, "--auto 의 ask 가 거짓을 내지 않는다"
    assert "merged_by_content" in s


def test_lake_disposition_knows_our_patch_zip():
    # ★ 경로를 건드리지 않고 도구 파일을 모듈로 읽는다(test_layering — 경로 조작 금지)
    import importlib.util

    from firelane import ledger

    spec = importlib.util.spec_from_file_location("lakecheck_t", T / "lakecheck.py")
    assert spec and spec.loader
    lakecheck = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = lakecheck   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(lakecheck)
    globs = lakecheck.disposed(ledger.load_sources())
    for name in ("fire-lane-navi-closed-loop.zip", "fire-lane-turn-radius.zip"):
        assert any(fnmatch.fnmatch(name, g) for g in globs), (
            f"{name} 을 레이크 L3 가 「밖에 있는 원본」으로 잡는다 — landing_disposition 에 적는다")


def test_fl_work_dir_is_per_run():
    """2026-09-22 실제 사고 — verify 안의 `--pick` 시험이 고정 경로 /tmp/fl-patches 를
    비워 7분 뒤 PR 단계가 PR_BODY.md 를 못 찾았다. 실행마다 새 자리여야 한다."""
    s = (T / "fl.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    assert "WORK=/tmp/fl-patches" not in code
    assert "mktemp -d /tmp/fl-patches." in code
    assert "applied()" in code, "다시 돌 때 이미 얹힌 패치를 건너뛰지 않는다"


def test_fl_rebuilds_branch_holding_older_version():
    """2026-09-22 실제 사고 — 6단계에서 멈춘 가지에 **고친 판** 패치를 얹으려다 4단계가
    파일마다 「already exists」 로 멈췄다. 3단계는 base 에 대 봤고 4단계는 옛 가지에
    얹었다. 옛 판이 있으면 base 에서 새로 짓고, 원격에 올라간 가지는 건드리지 않는다."""
    s = (T / "fl.sh").read_text(encoding="utf-8")
    code = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith("#"))
    assert 'git switch -q -C "$BR" "origin/$BASE"' in code
    assert 'git rev-parse -q --verify "origin/$BR"' in code, "원격 가지를 몰래 갈아 끼운다"
    assert "MISSING" in code


_FAKE_GH = """#!/usr/bin/env bash
# 시험용 gh — 상태는 환경변수로 준다
case "$1 $2" in
  "auth status") echo "  - Token scopes: 'repo', 'workflow'" ;;
  "pr list")
    case "$*" in
      *"--state open"*"--base part/infra"*|*"--base part/infra"*"--state open"*) echo "${GH_OPEN:-}" ;;
      *"--state merged"*) echo "${GH_MERGED:-}" ;;
      *) echo "" ;;
    esac ;;
  "pr view") echo "제목" ;;
  *) echo "gh $*" ;;
esac
"""


def _resume_world(tmp: Path, main_has_infra: bool):
    """origin 에 main · dev · part/infra, 저장소에 가짜 방송 · 정리, PATH 에 가짜 gh."""
    work, inbox = _world(tmp, seed=None)
    (work / "tools").mkdir(exist_ok=True)
    (work / "tools" / "merge_batch.sh").write_text("echo MERGE_BATCH \"$@\"\n", encoding="utf-8")
    (work / "tools" / "branch_tidy.sh").write_text("echo TIDY \"$@\"\n", encoding="utf-8")
    (work / "tools" / "verify.sh").write_text("exit 0\n", encoding="utf-8")
    # ★ 2026-09-27 (DECISIONS §273-5). 7b 가 부르는 도구를 합성 트리도 들고 간다.
    #   없으면 fl.sh 가 「스쿼시 뒤 빨간불」로 죽는데, 그것은 **옳은 동작**이다 —
    #   여기서 조용히 건너뛰게 만들면 이 시험이 7b 를 안 보는 시험이 된다(§272).
    (work / "tools" / "after_squash.py").write_text(
        "import sys; print('열차 뒤 검사 — 합성 트리'); sys.exit(0)\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "tools")
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/part/infra", "HEAD:refs/heads/dev")
    _git(work, "push", "-q", "origin", ("HEAD" if main_has_infra else "HEAD~1") + ":refs/heads/main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "switch", "-q", "-c", "part/infra", "origin/part/infra")
    bin_ = tmp / "bin"
    bin_.mkdir()
    (bin_ / "gh").write_text(_FAKE_GH, encoding="utf-8")
    (bin_ / "gh").chmod(0o755)
    return work, inbox, bin_


def _resume(work: Path, inbox: Path, bin_: Path, **gh) -> subprocess.CompletedProcess:
    env = {**os.environ, "FIRE_LANE_REPO": str(work), "FIRE_LANE_INBOX": str(inbox),
           "PATH": f"{bin_}:{os.environ['PATH']}", **gh}
    return subprocess.run(["bash", str(T / "fl.sh"), "feat/x", "--resume"],
                          capture_output=True, text=True, env=env, stdin=subprocess.DEVNULL)


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_fl_resume_after_squash_goes_to_release(tmp_path):
    """2026-09-22 실제 사고 — 8단계에서 끊겨 남은 명령을 손으로 쳤다. feat PR 이 머지됐으면
    패치를 찾지 않고 방송 · 정리로 간다."""
    work, inbox, bin_ = _resume_world(tmp_path, main_has_infra=False)
    r = _resume(work, inbox, bin_, GH_MERGED="7")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "dev PR 부터" in out and "MERGE_BATCH --release" in out and "TIDY --auto" in out, out
    assert "2. 패치" not in out, "머지된 배치인데 패치를 다시 찾는다"


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_fl_resume_when_released_only_tidies(tmp_path):
    work, inbox, bin_ = _resume_world(tmp_path, main_has_infra=True)
    r = _resume(work, inbox, bin_, GH_MERGED="7")
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert "MERGE_BATCH" not in out, "이미 main 에 들어간 배치를 또 방송한다"
    assert "TIDY --auto" in out, out


@pytest.mark.skipif(not shutil.which("git"), reason="환경skip(도구) — git 이 없다")
def test_fl_resume_without_pr_refuses(tmp_path):
    work, inbox, bin_ = _resume_world(tmp_path, main_has_infra=False)
    r = _resume(work, inbox, bin_)
    assert r.returncode != 0 and "이을 것이 없다" in r.stdout + r.stderr, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(fl.sh 가 쓴다)")
def test_fl_resume_archives_leftover_package(tmp_path):
    """스쿼시 직후 · 포장물을 치우기 전에 끊겼으면 --resume 이 치운다. 남기면 다음 --all 이
    또 집는다. 제목이 머지된 PR 과 같을 때만 이 배치 것으로 본다(독립 검토 2026-09-22)."""
    work, inbox, bin_ = _resume_world(tmp_path, main_has_infra=False)
    (tmp_path / "0001-fix.patch").write_text("From a\nSubject: ours\n", encoding="utf-8")
    (tmp_path / "PR_TITLE").write_text("제목\n", encoding="utf-8")                 # 가짜 gh 의 pr view 가 「제목」
    _zip(inbox / "fire-lane-x.zip", tmp_path / "0001-fix.patch", tmp_path / "PR_TITLE")
    shutil.copy(tmp_path / "0001-fix.patch", inbox / "0001-fix.patch")
    r = _resume(work, inbox, bin_, GH_MERGED="7")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (inbox / "0001-fix.patch").exists() and not (inbox / "fire-lane-x.zip").exists(), (
        "머지된 배치의 포장물이 INBOX 에 남았다\n" + r.stdout)
    assert list((inbox / "_applied").glob("*-feat_x/0001-fix.patch")), r.stdout


@pytest.mark.skipif(not shutil.which("unzip"), reason="환경skip(도구) — unzip 이 없다(fl.sh 가 쓴다)")
def test_fl_resume_keeps_other_batch_package(tmp_path):
    work, inbox, bin_ = _resume_world(tmp_path, main_has_infra=False)
    (tmp_path / "0001-fix.patch").write_text("From a\nSubject: next\n", encoding="utf-8")
    (tmp_path / "PR_TITLE").write_text("다음 배치\n", encoding="utf-8")
    _zip(inbox / "fire-lane-y.zip", tmp_path / "0001-fix.patch", tmp_path / "PR_TITLE")
    r = _resume(work, inbox, bin_, GH_MERGED="7")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (inbox / "fire-lane-y.zip").exists(), "다음 배치 포장물을 치웠다"


def test_tidy_keeps_long_lived_branches_like_branch_tidy():
    """`fl.sh` 11단계의 `tidy.py --yes` 가 `branch_tidy.sh` 가 지키는 가지를 지우지 않는다 (§217-4)."""
    import importlib.util
    import re as _re
    spec = importlib.util.spec_from_file_location("_tidy", ROOT / "tools" / "tidy.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m   # @dataclass 가 되짚는다 (§258-10)
    spec.loader.exec_module(m)
    sh = (ROOT / "tools" / "branch_tidy.sh").read_text(encoding="utf-8")
    keep = _re.search(r"KEEP_RE='\^\(([^)]*)\)\$'", sh).group(1).split("|")
    for b in keep:
        assert m.KEEP_BRANCH.match(b), f"branch_tidy 가 지키는 {b} 를 tidy 가 지울 수 있다"
    assert not m.KEEP_BRANCH.match("feat/x"), "feat 가지까지 지키면 정리가 안 된다"


def test_bot_prs_are_vacuumed_not_wiped():
    """봇 PR 은 알림이다 — 전부 닫지 않고 밀린 것 · 흐름 밖 것만 청소한다 (DECISIONS §218-4)."""
    dep = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    n_eco = dep.count("- package-ecosystem:")
    assert dep.count("target-branch: part/infra") == n_eco, "봇 PR 이 흐름 밖(main)으로 온다"
    s = (ROOT / "tools" / "branch_tidy.sh").read_text(encoding="utf-8")
    assert "밀렸다" in s and "흐름 밖" in s, "청소 기준(밀림 · 흐름 밖)이 없다"
    assert "gh pr diff" in s, "닫기 전에 diff 를 보관하지 않는다"
    assert "봇 대기" in s, "남긴 봇 PR 을 알리지 않는다"


def test_pr_body_check_runs_before_verify():
    """본문 검사가 전수 verify **앞**에 있다 (DECISIONS §220).

    2026-09-22 실물 — 본문의 「리뷰어가 볼 곳」이 비어 10분짜리 verify 를 태운 **뒤에** 멈췄다.
    """
    fl = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    first = fl.index("pr_body_check.py")
    verify = fl.index('step "5. 전수 verify"')
    assert first < verify, "본문 검사가 verify 뒤에 있다 — 빨강을 10분 늦게 본다"


def test_relock_step_stops_when_judgment_moved():
    """`--relock` 은 지문만 다시 찍고, 판정 **값**이 움직이면 멈춘다 (DECISIONS §220)."""
    fl = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    assert "--relock) RELOCK=1" in fl, "--relock 을 안 받는다"
    i = fl.index('if [ "$RELOCK" = 1 ]; then')
    blk = fl[i:fl.index('step "5. 전수 verify"')]
    assert "fire-lane --from segments" in blk and "golden.py lock" in blk, "재잠금 두 명령이 없다"
    # ★ 2026-09-23. 지문 파일은 `golden.py lock` 만 써서 재잠금 전에는 늘 안 움직인다 —
    #   판정이 움직였는지는 **추적되는 산출물**이 말한다. 2026-09-30 (§319) 그 대조가
    #   `tools/remeasure.py` 로 갔다(멈춘 뒤 할 일이 같은 자리에 있어야 막다른 길이 아니다).
    rm = (ROOT / "tools" / "remeasure.py").read_text(encoding="utf-8")
    assert "data/processed/segments.geojson" in rm and '"--name-only"' in rm, "빈 그물이다"
    assert blk.index("tools/remeasure.py") < blk.index("tools/golden.py lock"), \
        "값 대조를 재잠금 **뒤에** 한다 — 그러면 움직인 판정을 덮어쓴다"
    # ingest 닫힘이 바뀐 배치는 샤드 봉인이 찢어진다 — `--from segments` 로는 _manifest 가 낡는다
    assert "code_closure(\"firelane.ingest\")" in blk and "fire-lane --split" in blk, \
        "ingest 닫힘이 바뀐 배치에서 전량 재빌드를 안 한다"


def test_release_checkbox_asks_only_about_judgment():
    """릴리즈 체크박스는 판정 지문만 본다 — 발행 파일 수는 `계보` 줄이 말한다 (§220)."""
    mb = (ROOT / "tools" / "merge_batch.sh").read_text(encoding="utf-8")
    i = mb.index('out = changed(')
    line = mb[i:mb.index("\n", i)]
    assert "segments.fingerprint.json" in line and "web/data" not in line, line


def test_tag_prompt_accepts_the_suggested_tag():
    """제안 태그를 그대로 치면 「예」다 — y/N 자리에 태그를 치는 사람이 있다 (§220)."""
    mb = (ROOT / "tools" / "merge_batch.sh").read_text(encoding="utf-8")
    assert '[y/N/태그]' in mb and 'y|Y|"$next") tag="$next"' in mb, "태그 입력을 y 로 안 받는다"


def test_bot_prs_do_not_block_a_batch():
    """봇 PR 은 배치를 막지 않는다 — 막는 것은 **사람** PR 뿐이다 (DECISIONS §221-2).

    `branch_tidy --close-bots` 는 봇 PR 을 알림으로 **일부러 남긴다**(§218-4).
    1단계가 작성자를 안 보면 그 남긴 PR 이 다음 배치를 영영 세운다 — 규칙 둘이
    서로를 막는다. 2026-09-23 에 실제로 섰다.
    """
    fl = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    i = fl.index('step "1. 전제"')
    blk = fl[i:fl.index('step "2.', i)]
    assert "author" in blk and "dependabot" in blk.lower(), "1단계가 PR 작성자를 안 본다"
    assert "**사람** PR" in blk, "사람 PR 만 막는다는 것이 메시지에 없다"
    # 봇 목록은 `die` 가 아니라 `warn` 으로 나간다
    j = blk.index("BOT")
    tail = blk[j:]
    assert "warn " in tail and 'die "$BASE 로 가는 **봇' not in tail, "봇 PR 에서 죽는다"


# ── 봇 PR 이 배치를 막지 않는가 — **족으로** 본다 ──────────────────
#: 훑기인데 작성자를 안 봐도 되는 자리. 사유를 적는다 — 적는 순간 세어진다.
SWEEP_EXEMPT = {
    ("tools/branch_tidy.sh", "--json number --jq length"):
        "수만 센다 — 끝 표에 「열린 PR N」을 찍을 뿐 아무것도 막지 않는다",
}


def _gh_pr_list_sweeps() -> list[tuple[str, int, str]]:
    """배치 도구에서 `gh pr list` 호출을 **줄 이음까지 붙여** 뽑는다.

    `--head` 가 있으면 우리 가지 하나를 지목한 것이라 훑기가 아니다.
    """
    out = []
    for rel in ("tools/fl.sh", "tools/merge_batch.sh", "tools/branch_tidy.sh"):
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        i = 0
        while i < len(lines):
            if "gh pr list" in lines[i] and not lines[i].lstrip().startswith("#"):
                call, n = lines[i], i
                while call.rstrip().endswith("\\") and n + 1 < len(lines):
                    n += 1
                    call = call.rstrip()[:-1] + " " + lines[n].strip()
                if "--head" not in call:
                    out.append((rel, i + 1, call))
                i = n
            i += 1
    return out


def test_pr_sweeps_read_the_author():
    """열린 PR 을 **훑는** 자리는 전부 작성자를 읽는다 (DECISIONS §221-2 · §222-1).

    ★ 이것이 족 가드다. 2026-09-23 에 `fl.sh` 1단계의 같은 결함을 고치면서
      `merge_batch.sh` A단계의 **두 번째 인스턴스를 놓쳤고**, 같은 날 방송이
      dependabot PR 넷으로 멈췄다. 인스턴스를 하나씩 잡으면 반드시 다음 것이 남는다.
      작성자를 안 읽는 훑기는 봇 PR 과 사람 PR 을 가를 수 없고, 가를 수 없으면
      `branch_tidy --close-bots` 가 **일부러 남기는** 봇 PR(§218-4)이 배치를 영영 막는다.
    """
    bad = []
    for rel, line, call in _gh_pr_list_sweeps():
        if "author" in call:
            continue
        if any(rel == r and frag in call for (r, frag) in SWEEP_EXEMPT):
            continue
        bad.append(f"  {rel}:{line}  {call.strip()[:110]}")
    assert not bad, (
        "열린 PR 을 훑으면서 작성자를 안 읽는다 — 봇과 사람을 못 가른다:\n" + "\n".join(bad)
        + "\n\n  `--json …,author` 를 더하고 봇은 목록만 내라(§218-4).\n"
        "  막지 않는 훑기면 SWEEP_EXEMPT 에 사유와 함께 적어라.")


def test_sweep_exempt_entries_are_alive():
    """면제가 유령이 되지 않게 — 적어둔 자리가 실재하는가."""
    calls = [(r, c) for r, _, c in _gh_pr_list_sweeps()]
    dead = [f"{r}  {frag}" for (r, frag) in SWEEP_EXEMPT
            if not any(rr == r and frag in cc for rr, cc in calls)]
    assert not dead, f"SWEEP_EXEMPT 가 없는 자리를 든다: {dead}"


def test_release_brief_names_the_byte_axis_honestly():
    """「계약」 축의 sha 는 **바이트**다 — 값을 묻는 척하지 않는다 (DECISIONS §222-3).

    2026-09-23 릴리즈에서 의존성 일곱이 부동소수 표기만 바꿨는데 이 축이
    「1개가 움직였다」로 떴고, 같은 표 아래 체크박스는 「안 바뀐다」였다.
    """
    rb = (ROOT / "tools" / "release_brief.py").read_text(encoding="utf-8")
    assert '"발행바이트sha"' in rb, "축 이름이 무엇을 보는지 안 말한다"
    assert '"sha256": (j.get' not in rb, "옛 이름이 남아 있다"
    assert "_bytes_only" in rb, "바이트만 움직인 경우를 따로 안 말한다"


def test_verify_failure_keeps_a_legitimate_generated_change():
    """생성물이 움직였고 **판정이 불변**이면 되돌리지 않는다 (DECISIONS §223-5).

    ★ 종전에는 verify 가 빨개지면 생성물을 무조건 커밋본으로 되돌렸다. 배치가
      생성물을 정당하게 바꾸면(봉인지 신설 · 발행 형식 변경) 그 결과가 버려지고,
      다음 실행이 파이프라인 7분을 다시 돌려 같은 것을 만들고 또 되돌린다.
      **커밋 대상을 찌꺼기로 취급한 것**이다.
    ★ 경계는 둘 다 만족해야 한다 — 더러운 것이 생성물뿐이고, `golden.py check` 가 초록.
    """
    fl = (ROOT / "tools" / "fl.sh").read_text(encoding="utf-8")
    i = fl.index('step "5. 전수 verify"')
    blk = fl[i:fl.index('step "6.', i)]
    assert "tools/golden.py check" in blk, "판정을 안 보고 되돌린다"
    assert blk.index("tools/golden.py check") < blk.index('git checkout -q -- "${GEN[@]}"'), \
        "되돌린 **뒤에** 판정을 본다 — 그러면 이미 버린 것이다"
    assert "커밋한 뒤 다시 돌려라" in blk, "무엇을 하라는지 안 적는다"


# ════════════════════════════════════════════════════════════════
# 족 — 도구가 **모르는 것을 안다고 우긴다** (DECISIONS §225)
#
# 2026-09-23 하루에 셋이 연달아 터졌고 전부 같은 병이다.
#   A0  `gh pr checks` 의 503 을 「CI 빨강」으로 읽고 **PR 을 닫고 가지를 지웠다**
#   A4  A-0 이 part/infra 를 앞세워 놓고 「PR 을 빠뜨렸다」고 **사람을 탓했다**
#   A5  push **이전** 머리로 머지를 걸어 `Head branch is out of date` 로 거부당했다
#
# 인스턴스를 하나씩 잡으면 다음 것이 남는다 — 위 `test_pr_sweeps_read_the_author`
# 가 그 교훈으로 생겼다. 여기 둘은 그 족을 정적으로 막는다.
# ════════════════════════════════════════════════════════════════

#: 되돌릴 수 없는 동작. 여기 한 줄이 늘면 아래 시험이 사유를 요구한다.
DESTRUCTIVE = (
    "gh pr close",
    "--delete-branch",
    "git branch -q -D",
    "git branch -D",
    "git push --delete",
    "git push -d ",
)

#: 파괴적 동작이 **「모름」과 무관한** 자리. (파일, 줄에 든 조각) → 사유.
#: ★ 사유는 「왜 모름이 여기 못 오는가」여야 한다. 「안전하다」는 사유가 아니다.
DESTROY_EXEMPT = {
    ("tools/merge_batch.sh", 'git branch -q -D "$sb"'):
        "조회가 아니라 **우리가 방금 만든** 로컬 가지를 치운다 — 원격은 gh 가 이미 지웠거나 남겼다",
    ("tools/branch_tidy.sh", "--delete-branch"):
        "branch_tidy 는 자기 조회 실패를 스스로 본다(--close-bots 는 목록을 먼저 낸다)",
    ("tools/fl.sh", 'git branch -D "$BR" && ok'):
        "`--undo` 다. **사람이 지우라고 친 것**이지 조회 결과가 시킨 것이 아니다",
    ("tools/fl.sh", "--squash --delete-branch"):
        "머지가 **성공한 뒤**다. 가지는 base 에 흡수됐으므로 지우는 것이 맞다 — "
        "실패하면 바로 옆 `|| die` 가 먼저 문다",
    ("tools/fl.sh", 'git branch -D "$BR" >/dev/null'):
        "스쿼시 성공 뒤 로컬 정리. 원격은 이미 gh 가 지웠고 내용은 base 에 있다",
    ("tools/branch_tidy.sh", 'git branch -q -D "$b"'):
        "지우는 대상 `GONE` 은 `git fetch --prune` 이 **원격에서 사라졌다고 표시한** 것뿐이다. "
        "fetch 가 실패하면 아무것도 gone 으로 안 서고 목록이 비어 **아무것도 안 지운다** — "
        "조회 실패가 파괴로 가는 길이 구조적으로 없다",
}


def _destructive_sites() -> list[tuple[str, int, str]]:
    out = []
    for rel in ("tools/fl.sh", "tools/merge_batch.sh", "tools/branch_tidy.sh"):
        p = ROOT / rel
        if not p.is_file():
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = ln.split("#", 1)[0]
            if not any(d in s for d in DESTRUCTIVE):
                continue
            # ★ 2026-09-24. **사람에게 보여주는 문구를 동작으로 세지 않는다.**
            #   `die "… gh pr close --delete-branch $BR …"` 는 지우는 코드가 아니라
            #   지우는 법을 알려주는 글이다. 처음 판이 그것을 잡았고, 그러면
            #   「고칠 수 없는 빨강」이 생겨 사람이 검사를 우회한다(MASTER §17).
            b = s.strip()
            if b.startswith(('"', "'")) or re.match(r'^(die|warn|ok|say|echo|printf)\b', b):
                continue
            out.append((rel, i, ln.strip()))
    return out


def test_nothing_is_destroyed_on_an_unread_answer():
    """**모르면 안 지운다.** 파괴적 동작 앞 25줄이 「미상」을 가르는가.

    ★ 2026-09-23 실물. GitHub 이 503 을 뱉었고 `merge_batch.sh` 가 그것을 CI
      빨강으로 읽어 봉인 PR 을 닫고 가지를 지웠다. 못 읽은 것을 근거로 되돌릴
      수 없는 일을 했다 — `ruleset_check.py` 가 자기 머리말에 「못 읽은 것을
      '없다' 로 적지 않는다」고 써 둔 바로 그 원칙을 옆 도구가 어겼다.

    ★ 무엇을 보는가 — 파괴 자리 위쪽에 **세 갈래를 가르는 표시**가 있는가.
      `wrc`/`rc` 를 `2` 와 비교하거나, 「미상 · 못 읽」 이라는 말이 있어야 한다.
      말만 있고 코드가 없으면 그것은 다음 시험(`…_actually_returns_three`)이 잡는다.
    """
    bad = []
    for rel, line, src in _destructive_sites():
        if any(rel == r and frag in src for (r, frag) in DESTROY_EXEMPT):
            continue
        lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
        ctx = "\n".join(lines[max(0, line - 26):line])
        if re.search(r'=\s*"?2"?\s*\]|=\s*2\s*\]|미상|못 읽', ctx):
            continue
        bad.append(f"  {rel}:{line}  {src[:100]}")
    assert not bad, (
        "되돌릴 수 없는 동작인데 **「못 읽었다」를 「빨갛다」와 안 가른다**:\n"
        + "\n".join(bad)
        + "\n\n  조회가 실패하면 0/1 이 아니라 **세 번째 값**을 내고, 그 값에서는\n"
          "  아무것도 지우지 마라(merge_batch 의 `wait_checks` → 0·1·2 가 본보기).\n"
          "  「모름」이 여기 못 온다면 DESTROY_EXEMPT 에 **그 이유**를 적어라.")


def test_destroy_exempt_entries_are_alive():
    """면제가 유령이 되지 않게."""
    sites = [(r, s) for r, _, s in _destructive_sites()]
    dead = [f"{r}  {frag}" for (r, frag) in DESTROY_EXEMPT
            if not any(rr == r and frag in ss for rr, ss in sites)]
    assert not dead, f"DESTROY_EXEMPT 가 없는 자리를 든다: {dead}"


def test_status_probe_actually_returns_three():
    """조회 함수가 **정말로** 세 갈래를 내는가 — 말이 아니라 코드로.

    ★ 앞 시험은 「가른다고 적혀 있는가」를 본다. 적어만 두고 안 가르면 그것이
      1족(무음 통과)이다. 여기서는 `wait_checks` 본문에 `return 2` 가 실재하고
      호출부가 그 2 를 실제로 읽는지 센다.
    """
    src = (ROOT / "tools/merge_batch.sh").read_text(encoding="utf-8")
    body = src[src.index("wait_checks() {"):src.index("require_green() {")]
    assert "return 2" in body, (
        "`wait_checks` 가 「못 읽음」을 낼 길이 없다 — 0/1 뿐이면 호출부가 못 가른다")
    assert body.count("return 2") >= 2, (
        "조회 실패 자리가 하나뿐이다 — 머리 조회 · 검사 등록 대기 · 상태 조회 셋이 "
        "전부 「못 읽음」이다")
    users = [ln for ln in src.splitlines() if re.search(r'(wrc|rc)"?\s*=\s*"?2"?', ln)]
    assert users, "아무도 2 를 안 읽는다 — 내기만 하고 안 가르면 없는 것과 같다"


def test_no_exit_code_read_after_assignment_under_set_e():
    """`set -e` 아래서 `x=$(cmd); rc=$?` 는 **rc 를 읽기 전에 죽는다.**

    ★ 2026-09-24. 이 배치를 만들다 내가 네 자리에서 저질렀다. 대입의 종료코드가
      곧 명령의 종료코드라 `set -e` 가 먼저 문다 — 그래서 「실패를 분류하려고 쓴
      코드」가 **분류하기 전에 스크립트를 죽인다.** 조용하지도 않다: 죽긴 죽는데
      개발자가 의도한 분기는 영원히 안 돈다.
    ★ 고치는 법은 `if x=$(cmd); then rc=0; else rc=$?; fi` 다.
    """
    bad = []
    for rel in ("tools/fl.sh", "tools/merge_batch.sh", "tools/branch_tidy.sh"):
        p = ROOT / rel
        if not p.is_file():
            continue
        src = p.read_text(encoding="utf-8")
        if not re.search(r"^set -\w*e", src, re.M):
            continue
        for i, ln in enumerate(src.splitlines(), 1):
            s = ln.split("#", 1)[0]
            if re.search(r"^\s*\w+=\$\(.*\)\s*;\s*\w+=\$\?", s):
                bad.append(f"  {rel}:{i}  {ln.strip()[:100]}")
    assert not bad, (
        "`set -e` 아래서 대입 뒤 `$?` 를 읽는다 — 그 줄은 **안 돈다**:\n"
        + "\n".join(bad)
        + "\n\n  if x=$(cmd); then rc=0; else rc=$?; fi")



# ── CI 대기 — 조용한가 (2026-09-28 · DECISIONS §278-6) ──────────
def test_nobody_calls_gh_pr_checks_watch_any_more():
    """★ `--watch` 는 10초마다 **표 전체**를 다시 찍는다.

    2026-09-28 배치 로그 853줄 중 564줄(66%)이 같은 표의 반복이었다.
    실패는 0건인데 사람이 열고 「문제가 쏟아진다」고 읽었다 —
    **안 읽히는 로그에서는 진짜 실패도 안 보인다.**
    """
    for name in ("fl.sh", "merge_batch.sh", "ci_wait.sh"):
        code = "\n".join(l for l in (T / name).read_text(encoding="utf-8").splitlines()
                         if not l.lstrip().startswith("#"))
        assert "--watch" not in code, f"{name} 이 아직 `gh pr checks --watch` 를 부른다"


def test_both_callers_use_the_one_ci_wait_door():
    """★ 같은 물음을 두 곳이 다르게 답하던 자리다.

    `merge_batch` 는 §225-1 에서 「빨강」과 「못 읽음」을 갈랐는데 `fl.sh` 는
    **비영이면 전부 빨강**으로 읽었다 — 503 을 빨강으로 읽고 PR 을 지운 그
    결함이 옆 도구에 그대로 있었다. 문은 하나여야 한다.
    """
    for name in ("fl.sh", "merge_batch.sh"):
        assert "ci_wait.sh" in (T / name).read_text(encoding="utf-8"), \
            f"{name} 이 CI 대기를 제 손으로 한다 — 두 곳이면 또 갈린다"


def test_ci_wait_has_a_timeout_and_it_is_not_red():
    """시간 초과를 1(빨강)로 내면 호출부가 **PR 을 지운다.** 2(모름)여야 한다."""
    src = (T / "ci_wait.sh").read_text(encoding="utf-8")
    assert "CI_WAIT_MAX" in src, "시간 제한이 없다 — 안 끝나는 CI 에 영원히 매달린다"
    body = src[src.index("wait_ci() {"):src.index("selftest() {")]
    assert "return 2" in body.split("while", 1)[1].split("done", 1)[1], \
        "시간 초과가 2 로 안 나간다 — 「안 끝났다」와 「빨갛다」는 다르다"


def test_ci_wait_selftest_is_not_an_empty_net():
    r = subprocess.run(["bash", str(T / "ci_wait.sh"), "--selftest"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr


def test_ci_wait_separates_red_from_not_mergeable():
    """★ 「빨강이 없다」와 「밑동이 받아준다」는 다르다 (DECISIONS §282-1).

    배치 D 에서 이 도구가 「초록 3 · 빨강 0」을 찍고 스쿼시가 거부됐다 —
    같은 SHA 에 `contract-shared` 가 둘이었고 하나가 결론이 없었다.

    ★ 2026-10-06 (DECISIONS §403). 실행이 아예 없으면 교집합이 빈다 — **차집합**으로 뒤집었다.
    """
    src = (T / "ci_wait.sh").read_text(encoding="utf-8")
    for fn in ("unsettled()", "required_of()", "settled_runs()", "blocking()"):
        assert fn in src, f"{fn} 이 없다 — 필수 검사 미해결을 못 본다"
    # ★ `mergeStateStatus` 하나만 보면 승인 대기(main)에서 영원히 멈춘다.
    #   **주석은 걷는다** — 「왜 그것을 안 쓰는가」를 적은 줄까지 위반으로 세면
    #   사유를 못 적는다.
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "mergeStateStatus" not in code, (
        "`mergeStateStatus` 를 직접 보면 승인 부족과 검사 미해결이 안 갈린다 — "
        "릴리즈가 멈춘다. 필수 검사 목록과의 교집합으로 본다")
    body = src[src.index("wait_ci() {"):src.index("selftest() {")]
    assert "blocking " in body, "`wait_ci` 가 초록 직전에 미해결 필수 검사를 안 묻는다"


# ── 부트스트랩 자기 설치  (DECISIONS §396 · PLAN #153) ────────────────

def _install_block() -> str:
    """`fl.sh` 의 자기 설치 구간을 **그대로** 꺼낸다 — 베낀 사본을 재면 갈린다."""
    s = (T / "fl.sh").read_text(encoding="utf-8")
    assert "# >>> bootstrap-install" in s and "# <<< bootstrap-install" in s, (
        "fl.sh 에 자기 설치 구간 표지가 없다")
    return s.split("# >>> bootstrap-install", 1)[1].split("# <<< bootstrap-install", 1)[0]


def _run_install(tmp_path: Path, inbox_exists: bool, seed: str | None) -> Path:
    """가짜 저장소 · 가짜 INBOX 에서 그 구간만 돌린다."""
    repo = tmp_path / "repo"
    (repo / "tools").mkdir(parents=True)
    (repo / "tools/inbox_fl.sh").write_text("#!/usr/bin/env bash\n저장소판\n", encoding="utf-8")
    inbox = tmp_path / "inbox"
    if inbox_exists:
        inbox.mkdir()
        if seed is not None:
            (inbox / "fl.sh").write_text(seed, encoding="utf-8")
    sh = tmp_path / "run.sh"
    sh.write_text(f'set -uo pipefail\nIN="{inbox}"\ncd "{repo}"\n' + _install_block(),
                  encoding="utf-8")
    # ★ 시한 없이 자식을 기다리면 빨강이 무한 대기가 된다(§284-5).
    r = subprocess.run(["bash", str(sh)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    return inbox / "fl.sh"


def test_fl_installs_the_bootstrap_into_the_inbox(tmp_path):
    """★ INBOX 를 비우면 `fl.sh` 가 같이 사라졌고 사람이 `cp` 를 하루에 세 번 쳤다.

    손으로 치는 사본은 **낡기도 한다** — 저장소 판이 바뀌어도 INBOX 판은 그대로다.
    그래서 「없으면 깐다」가 아니라 **「다르면 덮는다」**를 잰다.
    """
    gone = _run_install(tmp_path, inbox_exists=True, seed=None)
    assert gone.read_text(encoding="utf-8") == "#!/usr/bin/env bash\n저장소판\n", "없을 때 안 깐다"

    stale = _run_install(tmp_path / "b", inbox_exists=True, seed="옛판\n")
    assert stale.read_text(encoding="utf-8") == "#!/usr/bin/env bash\n저장소판\n", "낡은 사본을 안 덮는다"


def test_fl_does_not_die_when_the_inbox_is_unwritable(tmp_path):
    """★ 이 줄은 **편의**다. 쓰기가 막혔다고 배치를 막으면 고치려고 만든 것이 막는다."""
    assert not _run_install(tmp_path, inbox_exists=False, seed=None).exists(), (
        "INBOX 가 없는데 만들었다 — 남의 경로에 파일을 쓴다")


def test_the_measured_hint_says_when_not_to_use_it():
    """★ §332 의 규율 — 도구가 보여주는 값은 그 도구의 관문을 통과해야 한다.

    `--measured` 안내가 **붙이는 조건**을 안 적으면, 읽는 사람은 그것을
    「막혔을 때 뚫는 깃발」로 읽는다. DECISIONS §388 이 그렇게 났다.
    """
    s = (T / "fl.sh").read_text(encoding="utf-8")
    hint = [ln for ln in s.splitlines() if "--measured=20260930-covrate" in ln]
    assert hint, "안내가 사라졌다"
    assert "실제로 움직였을 때만" in s, "붙이는 조건을 안 적는다"
    assert "§388" in s, "그 믿음이 무엇을 냈는지 안 가리킨다"
