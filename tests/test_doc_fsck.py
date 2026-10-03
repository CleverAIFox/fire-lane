#!/usr/bin/env python3
"""
test_doc_fsck.py — `tools/doc_fsck.py` 의 넷을 CI 에서 강제한다.

★ 도구를 만들어 두고 사람이 가끔 돌리는 것으로는 안 된다. `§79` 가 적은 대로
  **예외는 문서 밖에서 자라서 읽어도 안 보인다.** 검사가 CI 에서 울어야 보인다.

★ 이 파일은 판정을 하지 않는다. 어긋난 자리를 그대로 옮겨 실패 메시지로 낸다.
  어느 쪽이 정본인지는 사람이 정한다 — 보통 최신이지만 늘 그렇지는 않다.

IN    tools/doc_fsck.py
OUT   없음 (검사)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `sys.path` 를 건드리지 않는다. `tools/` 는 패키지가 아니라 스크립트
#   모음이라 import 경로에 넣으면 이름이 전역에 샌다.
#   `tests/test_layering.py::test_sys_path_해킹이_없다` 가 그것을 막는다.
_spec = importlib.util.spec_from_file_location(
    "doc_fsck", ROOT / "tools" / "doc_fsck.py")
doc_fsck = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = doc_fsck   # @dataclass 가 되짚는다 (§258-10)
_spec.loader.exec_module(doc_fsck)


@pytest.fixture(scope="module")
def led():
    return doc_fsck._ledger()


def _fail(title: str, bad: list[str], why: str) -> None:
    assert not bad, (
        f"{title}\n" + "\n".join(f"  · {b}" for b in bad) + f"\n\n  {why}")


def test_ledger_schema_doc_matches_reality(led):
    """★ 2026-09-01. README 예시가 `url` `license` `retrieved` 를 드는데 실물
    41개 중 0건이었다. 지혜님이 그 예시를 보고 대장 초안을 쓰다 어긋났다."""
    _fail("대장 스키마 문서가 실물과 다르다", doc_fsck.check_schema(led),
          "src/firelane/README.md 의 예시를 실물에 맞춘다. "
          "메타 항목의 정본은 sources.yaml 머리말이다.")


def test_paths_that_docs_point_at_exist():
    """★ 2026-09-01. `web/config.js` 가 `profiles.json` 을 fetch 하는데 저장소에
    그 파일이 없었다. clone 한 사람은 제원 칸이 빈 화면을 본다."""
    _fail("문서·설정이 없는 파일을 가리킨다", doc_fsck.check_paths(),
          "DECISIONS(경위) 와 PLAN(계획) 은 대상이 아니다. "
          "여기 잡힌 것은 '지금 그렇게 동작한다' 고 말하는 자리다.")


def test_absent_declarations_are_true(led):
    """★ 2026-09-01. 대장이 `turn_radius_m` 을 "7종 전수 확인 0건" 으로
    선언하는데 `profiles.json` 은 7300~11889 를 갖고 있었다."""
    _fail("대장이 없다고 한 값이 실물에 있다", doc_fsck.check_absent(led),
          "값을 지우는 것이 아니라 선언을 사실에 맞춘다. "
          "출처가 있으면 적고 미검증이면 그렇게 적는다(§81).")


def test_human_made_layer_is_in_the_ledger(led):
    """★ 2026-09-01. `layers.field` 는 재취득 불가한 실측이라고 선언하는데
    재취득 가능한 공공데이터 CSV 가 들어와 있었고 대장에도 없었다."""
    _fail("사람이 만드는 계층에 대장 밖 파일이 있다",
          doc_fsck.check_field_ledger(led),
          "재취득 가능하면 landing→raw 로 보낸다. 실측이면 대장에 등재한다. "
          "유예가 필요하면 doc_fsck.FIELD_EXEMPT 에 사유와 날짜를 적는다.")


def test_temporary_things_actually_expire():
    """★ 2026-09-02. `DECISIONS 80` 이 bypass 를 한시로 부여하고 회수를 사람
    기억에 맡겼다. **한시가 한시로 끝나려면 시계가 있어야 한다.**"""
    _fail("한시로 정한 것의 기한이 지났다", doc_fsck.check_expiry(),
          "회수하고 그 카드·서술을 지우거나, 날짜를 다시 정해라. "
          "지난 날짜가 적힌 안내는 안 지킨 규칙처럼 읽힌다.")


def test_a_generated_path_is_a_claim_not_a_silence():
    """★ 2026-09-25 (§258). `DOC_ABSENT` 는 **면제가 아니라 주장**이다 —
    「이 도구가 이 경로를 굽는다」. 그 주장이 죽으면 ② 가 그 사실을 낸다.

    셋을 잰다. ㉠ 살아 있는 주장은 조용하다. ㉡ 없는 도구를 적으면 운다.
    ㉢ 그 도구가 그 경로를 더 이상 안 굽으면(머리말 `OUT` 에서 빠지면) 운다.
    ㉢ 이 빠지면 굽기를 멈춘 뒤에도 문서가 조용히 거짓말한다.
    """
    from firelane import generated

    assert generated.DOC_ABSENT, "생성물 주장이 비었다 — 그러면 이 시험이 빈 그물이다"
    for path, tool in generated.DOC_ABSENT.items():
        assert (ROOT / tool).is_file(), f"{tool} 이 없다"
        assert path in generated._out_header(ROOT / tool), (
            f"{tool} 의 OUT 머리말이 {path} 를 안 든다")
    assert not generated.dead_claims(ROOT)

    real = dict(generated.DOC_ABSENT)
    try:
        generated.DOC_ABSENT.clear()
        generated.DOC_ABSENT["web/없는것.pdf"] = "tools/__없는도구__.py"
        assert generated.dead_claims(ROOT), "없는 도구를 적었는데 조용하다"
        generated.DOC_ABSENT.clear()
        # 실재하는 도구인데 그 경로를 안 굽는다 — 굽기를 멈춘 꼴
        generated.DOC_ABSENT["web/굽지않는것.pdf"] = "tools/doc_fsck.py"
        assert generated.dead_claims(ROOT), "OUT 에 없는 경로를 적었는데 조용하다"
    finally:
        generated.DOC_ABSENT.clear()
        generated.DOC_ABSENT.update(real)
    assert not generated.dead_claims(ROOT), "복원이 안 됐다"


def test_a_generated_claim_does_not_silence_a_real_absence():
    """★ 넓힌 쪽의 반대편. 주장에 적히지 **않은** 없는 경로는 여전히 운다."""
    probe = ROOT / "docs/MASTER.md"
    original = probe.read_text(encoding="utf-8")
    try:
        probe.write_text(original + "\n\n<!-- web/__가짜생성물__.pdf -->\n",
                         encoding="utf-8")
        assert any("__가짜생성물__" in b for b in doc_fsck.check_paths()), (
            "생성물 주장을 넣은 뒤 ② 가 다른 없는 경로를 놓친다")
    finally:
        probe.write_text(original, encoding="utf-8")


def test_the_gate_actually_cries():
    """★ 해제만 검사하면 항상 통과하는 검사를 만들게 된다(§69).
    없는 경로를 하나 심어 ② 가 우는지 본다."""
    probe = ROOT / "docs/MASTER.md"
    original = probe.read_text(encoding="utf-8")
    try:
        probe.write_text(original + "\n\n<!-- tools/__doc_fsck_probe__.py -->\n",
                         encoding="utf-8")
        assert doc_fsck.check_paths(), "없는 경로를 심었는데 ② 가 조용하다"
    finally:
        probe.write_text(original, encoding="utf-8")


def test_elsewhere_points_at_committed_files():
    """`absent.elsewhere` 가 **커밋되는 파일**을 가리키는가.

    ★ 2026-09-04. `data/processed/nfa_dispatch_119.csv` 를 가리켰는데
      `.gitignore:27` 이 `data/processed/*.csv` 를 뺀다. 로컬에는 있고
      **CI 에는 없어서** 로컬만 통과하는 검사가 됐다.

    ★ `elsewhere` 는 "그 출처에는 없지만 여기 있다" 를 증명하는 자리다.
      증명이 기계에 안 보이면 선언이 아니라 주석이다.
      커밋되는 것 — `_manifest.json` · `web/**` · `data/field/*`.
    """
    import subprocess

    import yaml

    led = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))
    targets = set()

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "absent" and isinstance(v, dict):
                    for spec in v.values():
                        if isinstance(spec, dict) and spec.get("elsewhere"):
                            targets.add(spec["elsewhere"])
                else:
                    walk(v)
    walk(led)

    bad = []
    for rel in sorted(targets):
        r = subprocess.run(["git", "check-ignore", "-q", rel],
                           cwd=ROOT, capture_output=True)
        if r.returncode == 0:
            bad.append(f"  {rel} 은 .gitignore 대상이다 — CI 에 없다")
    assert not bad, (
        "absent.elsewhere 가 커밋 안 되는 파일을 가리킨다.\n" + "\n".join(bad)
        + "\n\n  로컬에서만 통과하는 검사가 된다."
          "\n  data/processed/_manifest.json 이 컬럼 목록을 들고 커밋된다.")

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _plan() -> str:
    return (ROOT / "docs/PLAN.md").read_text(encoding="utf-8")


def _legend(text: str) -> set[str]:
    """`§0-2 상태 표기` 표에 선언된 표식.

    ★ 표식 목록을 여기 적지 않는다. 문서가 정본이다. 종전 검사는 `⬛` 를
      코드에 박아뒀는데 2026-09-13 에 슬롯 규약이 폐지되며 그 표식이
      문서에서 사라졌다. **찾을 것이 없어진 검사는 영원히 0건이고 영원히
      초록이다** — 그래서 `✅` 셋이 아흐레를 버텼다.
    """
    lines = text.splitlines(keepends=True)
    i = next(k for k, v in enumerate(lines) if v.startswith("### 0-2."))
    j = next(k for k in range(i + 1, len(lines))
             if lines[k].startswith(("### ", "## ")))
    out = set()
    for m in re.finditer(r"^\| *([^|\-][^|]*?) *\| *[^|]+ *\|$",
                         "".join(lines[i:j]), re.M):
        cell = m.group(1).strip()
        if cell != "표기":
            out.add(cell)
    return out


def _rows(text: str) -> list[tuple[str, str, str]]:
    """`## 1. 남은 일` 부터 다음 `### ` 앞까지의 (번호, 제목, 상태).

    ★ 범위를 `plan_renumber._span` 과 **같게 잡는다.** 문서 전체를 긁으면
      §7 기획서 대조표가 섞인다 — 그 표는 3번째 칸이 상태가 아니라
      '바꿀 것' 이라 어휘가 다르다. 범위가 다르면 도구와 검사가 다른 것을
      세고, 그러면 고쳐도 계속 운다.
    """
    lines = text.splitlines(keepends=True)
    i = next(k for k, v in enumerate(lines) if v.startswith("## 1. 남은 일"))
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith("### "))
    return [(m.group(1), m.group(2).strip(), m.group(3).strip())
            for m in re.finditer(
                r"^\| *(\d+\w*) *\| *([^|]*?) *\| *([^|]*?) *\|",
                "".join(lines[i:j]), re.M)]


def _offenders(text: str) -> list[tuple[str, str, str]]:
    ok = _legend(text)
    return [r for r in _rows(text) if r[2] not in ok]


def test_plan_status_vocabulary_is_closed():
    """§1 표의 상태 칸은 **§0-2 에 선언된 표식만** 쓴다.

    ★ 2026-09-15. 종전 `test_plan_has_no_closed_items` 는 `⬛` 만 찾았다.
      09-13 에 슬롯 규약이 폐지되며 닫힘 표식이 `✅` 로 바뀌었는데 검사는
      옛 표식을 계속 찾았고, `PLAN` 범례는 둘 다 모르는 채였다.
      **검사 · 문서 · 범례 셋이 갈려 있었고 아무도 울지 않았다.**

    ★ 닫힘 표식을 어휘에 넣지 않는 것이 요점이다(§0-2). 표식이 있으면
      사람은 행을 지우는 대신 표식을 단다. PLAN 은 빚 목록이고 갚은 빚은
      목록에 없다. `✅` 든 `⬛` 든 어휘 밖이므로 여기서 걸린다.

    닫는 법 — 결과는 MASTER 로, 이유는 DECISIONS 로 옮기고 **행을 지운다.**
    번호는 안 당긴다 — 결번이 정상이다(§0-2 · DECISIONS §205).
    """
    text = _plan()
    bad = _offenders(text)
    assert not bad, (
        f"§1 표에 어휘 밖 상태 표식이 {len(bad)}개 있다.\n  "
        + "\n  ".join(f"#{i} [{st}] {t[:44]}" for i, t, st in bad)
        + "\n\n  선언된 표식: " + " · ".join(sorted(_legend(text)))
        + "\n\n  ★ 닫힘 표식은 없다. 완료면 **행을 지운다**(§0-2).\n"
          "    결과는 MASTER 로, 이유는 DECISIONS 로 옮긴다.\n"
          "    번호는 안 당긴다 — 결번이 정상이다(DECISIONS §205)\n"
          "  ★ 손으로 옮긴다. 옮기는 배치는 저장소에 안 남긴다.")


def test_plan_status_probe_is_alive():
    """카나리아 — 위 검사가 **실제로 잡는가.**

    ★ 0 이 목표인 검사는 0 을 죽음으로 읽으면 안 되고, 0 을 성공으로만
      읽어서도 안 된다. 어느 쪽인지 가리는 것은 양성 대조뿐이다.
      `env_check --selftest` 가 같은 이유로 생겼다(DECISIONS §150).

    ★ 실물 문서를 안 건드린다. 합성 문자열로 프로브만 흔든다.
    """
    text = _plan()
    ok = _legend(text)
    assert ok, "§0-2 범례를 못 읽었다 — 표식 파서가 죽었다"
    assert len(_rows(text)) > 20, "§1 표 행을 못 찾았다 — 행 파서가 죽었다"

    synth = text.replace("| 1 | ", "| 1 | ", 1)
    lines = synth.splitlines(keepends=True)
    i = next(k for k, v in enumerate(lines) if v.startswith("## 1. 남은 일"))
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith("|---"))
    lines.insert(j + 1, "| 999 | 합성 카나리아 행 | \u2705 | 프로브 양성 대조 |\n")
    caught = _offenders("".join(lines))
    assert any(r[0] == "999" for r in caught), (
        "카나리아가 안 잡혔다. 어휘 밖 표식을 심었는데 검사가 조용하다 —\n"
        "  `_legend` 나 `_rows` 의 정규식이 문서 형식 변경으로 죽었다.\n"
        "  이 검사가 초록인 것은 PLAN 이 깨끗해서가 아니다.")


def _proposal_rows(text: str) -> list[tuple[str, str, str]]:
    """`§12 기획서 갱신 대상` 표의 (번호, 서술, 상태).

    ★ §1 과 어휘가 다르다. 여기 상태 칸은 `완료` · `🟡` 를 쓴다.
      그래서 §1 용 검사를 그대로 쓰면 안 되고, 범위도 따로 잡아야 한다.
    """
    k = text.find("| # | 기획서의 서술 |")
    if k < 0:
        return []
    end = text.find("\n## ", k)
    blk = text[k:] if end < 0 else text[k:end]
    return [(m.group(1), m.group(2).strip(), m.group(3).strip())
            for m in re.finditer(
                r"^\| *(\d+\w*) *\| *([^|]*?) *\| *[^|]*? *\| *([^|]*?) *\|",
                blk, re.M)]


def test_proposal_table_has_no_closed_rows():
    """`§12` 에 **닫힌 행이 남아 있으면 안 된다.**

    ★ 2026-09-15 신설. §1 은 `✅` 를 잡는 검사가 생겼는데 §12 는 아무도
      안 봤다. `완료` 행 여섯이 그대로 남아 있었고 그중 하나(`4a`)는
      폐지된 `⬛` 를 **상태가 아닌 칸**에 달고 있었다. 표가 둘이면
      검사도 둘이어야 한다 — 하나만 만들면 나머지가 그늘이 된다.

    ★ 닫는 법은 §1 과 같다. 기획서를 실제로 고쳤으면 그 사실은
      `MASTER` 에 있다. 여기는 **앞으로 고칠 것**만 담는다.
    """
    text = _plan()
    bad = [r for r in _proposal_rows(text) if "완료" in r[2]]
    assert not bad, (
        f"§12 에 닫힌 행이 {len(bad)}개 남았다. **행을 지워라.**\n  "
        + "\n  ".join(f"#{i} {t[:44]}" for i, t, _ in bad)
        + "\n\n  갱신했으면 결과는 MASTER 에 있다. 이 절은 남은 것만 담는다.\n"
          "  ★ 손으로 지운다. 지우는 배치는 저장소에 안 남긴다.")


def test_proposal_probe_is_alive():
    """카나리아 — 위 검사가 실제로 잡는가.

    ★ §12 가 비면 `_proposal_rows` 가 0건을 내고 0건은 초록이다.
      그것이 깨끗해서인지 파서가 죽어서인지 합성 행으로 가린다(§159).
    """
    text = _plan()
    k = text.find("| # | 기획서의 서술 |")
    assert k >= 0, "§12 표 머리를 못 찾았다 — 파서가 죽었다"
    j = text.index("\n", text.index("\n", k) + 1)
    synth = text[:j + 1] + "| 998 | 합성 카나리아 | 프로브 양성 대조 | 완료 |\n" + text[j + 1:]
    caught = [r for r in _proposal_rows(synth) if "완료" in r[2]]
    assert any(r[0] == "998" for r in caught), (
        "카나리아가 안 잡혔다. 닫힌 행을 심었는데 검사가 조용하다 —\n"
        "  `_proposal_rows` 의 정규식이 표 형식 변경으로 죽었다.")


# ── ⑥b 의 전제 — 공통 조상이 없으면 재지 않는다 (DECISIONS §355) ──────
#: ⑥b 가 사는 모듈. **`sys.path` 를 안 건드린다** — 위 `doc_fsck` 와 같은 방식이다.
_spec6 = importlib.util.spec_from_file_location(
    "docx_revised", ROOT / "tools" / "docfsck" / "docx_revised.py")
docx_revised = importlib.util.module_from_spec(_spec6)
sys.modules[_spec6.name] = docx_revised
_spec6.loader.exec_module(docx_revised)


def _orphan_ref() -> str:
    """HEAD 와 **공통 조상이 없는** 커밋을 ref 로 만든다. 얕은 클론의 재현이다.

    ★ 얕은 클론에서는 `origin/part/ไ…` 같은 ref 가 **있는데 커밋이 없다.**
      여기서는 반대로 커밋은 있고 조상이 없게 만든다 — `base...HEAD` 가
      공통 조상을 못 찾는다는 점에서 git 에게는 같은 상황이다.
    """
    import subprocess
    root = Path(__file__).resolve().parents[1]

    # ★ 2026-10-02 (DECISIONS §362). `commit-tree` 는 **쓰기** 명령이라 커미터
    #   신원이 있어야 돈다. 개발 기계에는 있고 **CI 러너에는 없다** — verify 는
    #   초록인데 CI 가 `Author identity unknown` 으로 죽었다(PR #269).
    #   시험이 환경에 있는 것을 전제로 쓰면 그 전제가 없는 곳에서 처음 드러난다.
    #   그래서 **시험이 제 신원을 들고 간다** — 어느 기계에서도 같게 돈다.
    ID = ("-c", "user.name=fl-test", "-c", "user.email=fl-test@invalid.example")

    def g(*a: str) -> str:
        r = subprocess.run(["git", *ID, *a], cwd=root, capture_output=True,
                           text=True, timeout=20, check=True)
        return r.stdout.strip()

    tree = g("hash-object", "-w", "-t", "tree", "/dev/null")
    sha = g("commit-tree", tree, "-m", "orphan probe")
    name = "refs/fl-test/orphan-probe"
    g("update-ref", name, sha)
    return name


@pytest.mark.skipif(not (ROOT / ".git").exists(),
                    reason="환경skip(도구) — git 저장소가 아니라 ref 를 못 심는다")
def test_the_squash_arm_declines_to_measure_without_a_common_ancestor():
    """**얕은 클론에서 사유 없이 빨개지지 않는다.**

    ── 왜 (2026-10-02 · DECISIONS §355) ──────────────────────────
    PR #266 의 CI 가 이렇게 울었다 —

        docs/proposal.docx 이 origin/part/infra 와 다른지 판별하지 못했다: .

    사유 칸이 비어 있다. `git diff base...HEAD` 가 공통 조상을 못 찾아 죽었고
    stderr 가 비었기 때문이다. 종전 기준 선택은 **이름이 있는가**(`rev-parse
    --verify`)만 봤는데, `checkout@v4` 의 얕은 클론에는 **이름은 있고 커밋이
    없다.** 바로 위 `check_docx_revised` 가 2026-09-18 에 이미 선언한 전제를
    이 팔만 안 물려받고 있었다.
    """
    m = docx_revised
    ref = _orphan_ref()
    try:
        assert m.check_docx_ready_for_squash(bases=(ref,)) == [], (
            "공통 조상이 없는 기준으로 쟀다 — 얕은 클론에서 CI 가 사유 없이 빨개진다")
        # ★ 빈 그물이 아니다(MASTER §17-0 ③). 위 통과가 「조상이 없어서」인지
        #   「프로브가 아예 안 돌아서」인지 가른다 — HEAD 는 제 조상이다.
        assert m._git("merge-base", "HEAD", "HEAD")[0] == 0, (
            "merge-base 프로브 자체가 안 돈다 — 위 통과는 아무것도 증명 안 한다")
        assert m._git("merge-base", "HEAD", ref)[0] != 0, (
            f"{ref} 가 HEAD 와 조상을 공유한다 — 주입이 성립 안 했다")
    finally:
        import subprocess
        subprocess.run(["git", "update-ref", "-d", ref],
                       cwd=Path(__file__).resolve().parents[1],
                       capture_output=True, timeout=20, check=False)


# ── ⑧ 기한 — **0건이 청결인가 죽음인가** (DECISIONS §359) ──────────────────
def test_the_deadline_arm_is_still_alive_while_the_table_is_empty():
    """★ 양성 대조. `DEFERRED` 가 빈 동안 이 검사는 `[]` 만 돌려줬다.

    2026-09-24 에 마지막 줄이 해소되면서 표가 비었고, 그 뒤로 ⑧ 은 **열흘 가까이
    항상 통과**했다. 머리말이 바로 그 병을 경고하고 있었는데(「해제만 검사하면
    항상 통과하는 검사가 된다(§69)」) 정작 자기가 걸렸다.

    빈 것 자체는 옳다 — 네 줄이 전부 해소·이관됐다. 고칠 것은 **0건을 선언으로
    만드는 일**이고, 선언은 「지금 빚이 없다」를 **증명할 수 있을 때만** 선언이다.
    그래서 합성 행으로 울려 본다.
    """
    anchor = "# Fire-Lane"            # README 첫 줄 — 실재하는 앵커
    assert anchor in (ROOT / "README.md").read_text(encoding="utf-8")[:200], \
        "앵커가 더는 README 에 없다 — 이 시험의 전제를 고쳐라"

    past = doc_fsck.check_deferred(
        (("2000-01-01", "README.md", anchor, "합성 — 지난 기한"),), _use=True)
    assert past, "기한이 지난 줄을 안 운다 — ⑧ 의 앞 방향이 죽었다"
    assert "2000-01-01" in past[0]

    gone = doc_fsck.check_deferred(
        (("2999-01-01", "README.md", "이런 글자는 문서에 없다",
          "합성 — 해소된 줄"),), _use=True)
    assert gone, "해소된 줄이 표에 남았는데 안 운다 — ⑧ 의 뒤 방향이 죽었다"
    assert "해소" in gone[0]

    future = doc_fsck.check_deferred(
        (("2999-01-01", "README.md", anchor, "합성 — 아직 기한 안"),), _use=True)
    assert not future, f"기한 안인데 운다 — 늘 우는 검사다 {future}"


def test_the_deadline_table_is_empty_on_purpose():
    """표가 **왜** 비었는지가 소스에 적혀 있는가. 적혀 있지 않으면 사고다.

    ★ 지운 줄마다 「해소」 또는 「이관」과 그 날짜가 주석으로 남아 있어야 한다.
      남기지 않으면 다음 사람은 **표가 비었다**와 **표를 지웠다**를 구별 못 한다.
    """
    src = (ROOT / "tools" / "doc_fsck.py").read_text(encoding="utf-8")
    body = src.split("DEFERRED = (", 1)[1].split("\n)", 1)[0]
    if doc_fsck.DEFERRED:
        return                                   # 줄이 있으면 이 물음이 아니다
    assert body.strip(), "표가 비었는데 사유도 없다 — 왜 비었는지 아무도 모른다"
    assert ("해소" in body or "이관" in body), \
        "표가 비었는데 어느 줄이 왜 사라졌는지 안 적혀 있다"
