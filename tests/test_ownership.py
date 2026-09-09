#!/usr/bin/env python3
"""
test_ownership.py — 저장소 전 경로에 소유자가 있는가.

── 왜 생겼나 ───────────────────────────────────────────────────
2026-08-26. 5인 체제 전환 직전에 `tools/owned_paths.py --unowned` 를
처음 돌렸다. **미소유 경로가 62건이었다.**

    tools/       27   ship · tidy · 조사 스크립트 전부
    tests/       16   강제자 본체가 미소유
    docs/         6   PLAN · DECISIONS 포함
    루트 설정     11   pyproject · uv.lock · Dockerfile · workflows

`test_web_ownership.py` 가 `web/` 에 대해 하던 검사를 저장소 전체로
넓히지 않았던 결과다. 2인일 때는 사실상 전부 한 사람 것이라 드러나지
않았다.

── 이 검사가 푸는 진짜 문제 ────────────────────────────────────
"공용 파일이 앞으로 더 늘면 그때 규칙 거는 걸 깜빡하면?"

목록으로 관리하면 반드시 빠뜨린다. 그래서 목록을 관리하지 않는다.
**미소유 상태를 불법으로 만든다.**

새 공용 파일을 만드는 그 PR 에서 빨간불이 뜨고, 머지하려면 소유자를
정해야 한다. 규칙을 미리 거는 것이 아니라 **규칙 없는 상태로는 머지가
안 되게** 하는 것이다. 미래를 예측할 필요가 사라진다.

IN    .github/CODEOWNERS · git ls-files
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ★ sys.path 를 조작하지 않는다(test_layering). `tools/` 는 pyproject 의
#   `[tool.pytest.ini_options] pythonpath = ["tools"]` 가 이미 잡는다.
from owned_paths import CODEOWNERS, owners_of, rules, tracked, unowned

ROOT = Path(__file__).resolve().parent.parent


def test_every_tracked_path_has_an_owner():
    """★ 이 저장소의 핵심 방어. 미소유 경로는 존재할 수 없다."""
    bad = unowned()
    assert not bad, (
        f"소유자 없는 경로 {len(bad)}건\n"
        + "\n".join(f"  {b}" for b in bad[:25])
        + (f"\n  ... 외 {len(bad) - 25}건" if len(bad) > 25 else "")
        + "\n\n  고치는 법 — .github/CODEOWNERS 에 한 줄 추가한다.\n"
        "      /경로/                @핸들\n"
        "  누구 것인지 모르겠으면 그것이 바로 지금 정해야 하는 것이다.\n"
        "  소유자 없는 파일은 아무나 고치고 아무도 리뷰하지 않는다.")


def test_codeowners_has_a_catch_all():
    """기본값 규칙이 있는가.

    ★ 이것이 없으면 위 검사가 새 파일마다 빨간불을 낸다. 있으면
      새 파일은 일단 대관리자에게 떨어지고, 파트 것이면 좁은 규칙으로
      내려보낸다. **막는 것이 아니라 흐르게 하는 장치다.**
    """
    pats = [p for p, _, _ in rules()]
    assert "*" in pats, (
        "CODEOWNERS 에 기본값 규칙 `*` 이 없다.\n"
        "  없으면 새 파일이 생길 때마다 미소유 빨간불이 뜬다.\n"
        "      *                        @AIMasterFox\n"
        "  를 파일 맨 위(좁은 규칙들보다 먼저)에 둔다.")


def test_catch_all_comes_first():
    """기본값이 맨 앞에 있는가.

    ★ CODEOWNERS 는 **마지막 매치가 이긴다.** `*` 이 뒤에 있으면
      앞의 모든 좁은 규칙을 덮어써서 전 저장소가 한 사람 소유가 된다.
      파일이 문법상 멀쩡하고 검사도 통과하므로 아무도 모른다.
    """
    pats = [p for p, _, _ in rules()]
    if "*" not in pats:
        return
    assert pats.index("*") == 0, (
        f"기본값 `*` 이 {pats.index('*') + 1}번째 규칙이다.\n"
        "  CODEOWNERS 는 마지막 매치가 이기므로 `*` 은 반드시 맨 앞이어야\n"
        "  한다. 뒤에 있으면 좁은 규칙이 전부 무효가 되고, 그래도\n"
        "  파일은 멀쩡해 보인다.")


def test_no_double_star_glob():
    """`**` 를 쓰지 않는가.

    GitHub 과 owned_paths.py 의 해석이 갈릴 수 있는 유일한 문법이다.
    갈리면 CI 가 보는 범위와 리뷰가 걸리는 범위가 달라진다.
    """
    bad = [p for p, _, _ in rules() if "**" in p]
    assert not bad, (
        f"CODEOWNERS 에 `**` 패턴이 있다: {bad}\n"
        "  `/dir/` · `/path/file` · `*.ext` 만 쓴다.")


def test_owner_handles_look_real():
    """소유자 핸들이 자리표시자로 남아 있지 않은가.

    ★ 존재하지 않는 핸들을 GitHub 은 **조용히 무시한다.** 그 경로는
      리뷰 없이 통과하는데 CODEOWNERS 에는 적혀 있어서 보호되는
      것처럼 보인다. 검사가 죽은 채 뜨는 초록불이다.
    """
    if not CODEOWNERS.exists():
        return
    txt = CODEOWNERS.read_text(encoding="utf-8")
    body = "\n".join(l for l in txt.splitlines()
                     if not l.lstrip().startswith("#"))
    placeholder = re.findall(r"@(?:GIS-2|CV-LEAD|CV-2|INFRA|TODO)\b", body)
    assert not placeholder, (
        f"CODEOWNERS 에 자리표시자 핸들이 남아 있다: {sorted(set(placeholder))}\n"
        "  실제 GitHub 핸들로 교체할 것.\n"
        "  존재하지 않는 핸들은 GitHub 이 조용히 무시하고, 그 경로는\n"
        "  리뷰 없이 머지된다. 보호되는 것처럼 보이지만 아니다.")


def test_contracts_surface_is_signed():
    """경계 계약의 **표면**이 서명된 지문과 같은가.

    ★ 2026-09-09. 종전에는 `src/contracts/` 를 **2인 공동 소유**로 강제했다.
      뜻은 "경계는 혼자 조용히 못 바꾼다" 였고, 수단은 사람이었다 —
      리뷰 요청이 가야 다른 파트가 알아챈다(MASTER §5-2, GIS ↔ UI).

      저장소가 1인 체제가 되면서 **그 수단이 성립하지 않는다.** 파트가
      하나면 2인 소유가 불가능하고, 검사를 그대로 두면 영구 실패다.
      없는 사람을 소유자로 적어 통과시키는 것은 더 나쁘다 —
      CODEOWNERS 머리말이 경고한 *"보호되는 것처럼 보이면서"* 가 된다.

    ★ **목적은 남기고 수단을 바꾼다.** 사람이 알아채던 것을 검사가 한다.
      계약의 공개 표면(모델 이름과 필드 이름·순서)을 지문으로 굳히고,
      바뀌면 지문을 **의식적으로 다시 서명**하게 한다. `golden` 이 판정에
      대해 하는 일과 같다 — 게이트는 울고, 또 풀린다.

    ★ 내용 검사는 이미 따로 있다. 여기는 **변경 사실의 가시성**만 본다.
        tests/test_contract.py          GIS ↔ UI 구조 599줄
        tests/test_contract_vision.py   코드 ↔ MASTER §19-1 · 임계값 누출
      셋이 각각 다른 것을 본다. 이 검사가 없으면 "고쳤다는 사실" 만 샌다.

    ★ 다시 협업으로 돌아가도 이 검사는 유효하다. 소유권 검사를 되살리려면
      CODEOWNERS 에 2인 이상을 적고 이 함수 옆에 다시 만들면 된다.
    """
    import hashlib
    import json

    d = ROOT / "src/contracts"
    if not d.exists():
        pytest.skip("src/contracts 가 없다")

    import contracts as C

    surface = {
        name: list(getattr(C, name).model_fields)
        for name in sorted(C.__all__)
    }
    got = hashlib.sha256(
        json.dumps(surface, ensure_ascii=False, sort_keys=False)
        .encode("utf-8")).hexdigest()[:16]

    sig = ROOT / "src/contracts/SURFACE.sha256"
    if not sig.exists():
        pytest.fail(
            f"경계 계약 지문이 없다. 표면을 확인하고 서명하라 —\n"
            f"  {json.dumps(surface, ensure_ascii=False, indent=2)}\n"
            f"  echo {got} > src/contracts/SURFACE.sha256")

    want = sig.read_text(encoding="utf-8").split("#")[0].strip()
    assert got == want, (
        f"경계 계약의 표면이 바뀌었다. {want} → {got}\n"
        f"  현재 표면 —\n{json.dumps(surface, ensure_ascii=False, indent=4)}\n"
        "  이것은 파트 간 유일한 접점이다. 바꿔도 되지만 **조용히는 안 된다.**\n"
        "  1) MASTER §19 를 같이 고쳤는가\n"
        "  2) 소비자(cv · api · web)가 이 필드를 읽고 있지 않은가\n"
        "  확인했으면 다시 서명하라 —\n"
        f"      echo {got} > src/contracts/SURFACE.sha256")


def test_strict_scope_is_not_empty():
    """엄격 검사 대상이 비어 있지 않은가.

    CODEOWNERS 를 잘못 고쳐 단독 소유가 0건이 되면 `contract-strict`
    job 이 **아무것도 검사하지 않고 초록불**이 된다.
    """
    from owned_paths import strict_paths
    n = len(strict_paths())
    assert n > 0, (
        "`# !strict` 로 표시된 경로가 0건이다.\n"
        "  contract-strict job 이 아무것도 검사하지 않고 통과한다.\n"
        "  CODEOWNERS 줄 끝의 `# !strict` 태그가 지워지지 않았는지 보라.")

