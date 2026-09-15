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
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# ★ `sys.path` 를 건드리지 않는다. `tools/` 는 패키지가 아니라 스크립트
#   모음이라 import 경로에 넣으면 이름이 전역에 샌다.
#   `tests/test_layering.py::test_sys_path_해킹이_없다` 가 그것을 막는다.
_spec = importlib.util.spec_from_file_location(
    "doc_fsck", ROOT / "tools" / "doc_fsck.py")
doc_fsck = importlib.util.module_from_spec(_spec)
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
    그 뒤 `uv run python tools/plan_renumber.py --apply` 로 번호를 당긴다.
    """
    text = _plan()
    bad = _offenders(text)
    assert not bad, (
        f"§1 표에 어휘 밖 상태 표식이 {len(bad)}개 있다.\n  "
        + "\n  ".join(f"#{i} [{st}] {t[:44]}" for i, t, st in bad)
        + "\n\n  선언된 표식: " + " · ".join(sorted(_legend(text)))
        + "\n\n  ★ 닫힘 표식은 없다. 완료면 **행을 지운다**(§0-2).\n"
          "    결과는 MASTER 로, 이유는 DECISIONS 로 옮긴다.\n"
          "    그 뒤 uv run python tools/plan_renumber.py --apply\n"
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
