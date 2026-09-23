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
import shutil
import subprocess
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
    (repo / "tools" / "fl.sh").write_text(f"#!/usr/bin/env bash\necho {body} \"$@\"\n")


def _world(tmp: Path, seed: str | None):
    """bare 원격 · 작업 저장소(origin/part/infra) · INBOX 를 만든다."""
    bare, work, inbox = tmp / "r.git", tmp / "work", tmp / "inbox"
    _git(tmp, "init", "-q", "--bare", str(bare))
    _git(tmp, "clone", "-q", str(bare), str(work))
    (work / "README").write_text("x\n")
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
    out.write_text(_git(work, "format-patch", "-1", "--stdout"))
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
    (inbox / "0001-fix.patch").write_text("From a\nSubject: ours\n")
    _zip(inbox / "fire-lane-x.zip", inbox / "0001-fix.patch")
    (inbox / "D0216.patch").write_text(FOREIGN)
    (inbox / "thoth-105-fixture-honest.patch").write_text(FOREIGN + "x")
    assert _pick(inbox) == ["0001-fix.patch"]


def test_fl_without_zip_takes_format_patch_names_only(tmp_path):
    inbox = tmp_path / "in"
    inbox.mkdir()
    (inbox / "0001-a.patch").write_text("From a\n")
    (inbox / "0002-b.patch").write_text("From b\n")
    (inbox / "D0216.patch").write_text(FOREIGN)
    assert _pick(inbox) == ["0001-a.patch", "0002-b.patch"]


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
    (work / "tools" / "merge_batch.sh").write_text("echo MERGE_BATCH \"$@\"\n")
    (work / "tools" / "branch_tidy.sh").write_text("echo TIDY \"$@\"\n")
    (work / "tools" / "verify.sh").write_text("exit 0\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "tools")
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/part/infra", "HEAD:refs/heads/dev")
    _git(work, "push", "-q", "origin", ("HEAD" if main_has_infra else "HEAD~1") + ":refs/heads/main")
    _git(work, "fetch", "-q", "origin")
    _git(work, "switch", "-q", "-c", "part/infra", "origin/part/infra")
    bin_ = tmp / "bin"
    bin_.mkdir()
    (bin_ / "gh").write_text(_FAKE_GH)
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
    (tmp_path / "0001-fix.patch").write_text("From a\nSubject: ours\n")
    (tmp_path / "PR_TITLE").write_text("제목\n")                 # 가짜 gh 의 pr view 가 「제목」
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
    (tmp_path / "0001-fix.patch").write_text("From a\nSubject: next\n")
    (tmp_path / "PR_TITLE").write_text("다음 배치\n")
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
    # ★ 2026-09-23. 종전에는 `data/golden/segments.fingerprint.json` 을 대조했는데 그 파일은
    #   `golden.py lock` 만 쓴다 — 재잠금 전에는 언제나 안 움직여 그물이 비어 있었다.
    #   판정이 움직였는지는 **추적되는 파이프라인 산출물**이 말한다.
    cmp_ = "git diff --quiet -- data/processed/segments.geojson data/processed/seg_uid_map.csv"
    assert cmp_ in blk, "판정 산출물 대조가 없다 — 지문 파일만 보면 빈 그물이다"
    assert blk.index(cmp_) < blk.index("tools/golden.py lock"), \
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
