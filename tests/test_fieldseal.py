"""
test_fieldseal.py — 재생성 불가 층의 지문이 **살아 있고 실물과 맞는가**.
(PLAN §13 W13-7 의 증표 · DECISIONS §288 · §291 · §306)

── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
W13-7 은 2026-09-28 에 **닫혔다**고 선언됐다. 그런데 `fieldseal` 을 무는
시험이 **트리에 하나도 없었다.** `tests/test_defect_evidence.py` 의 등록부가
정확히 그것을 잡으려고 있는데, 그 관문 ③은 DECISIONS 의 `닫힘` **줄**만
읽고 §288 은 그 형식을 안 썼다 — 그래서 조용히 지나갔다(1족, 무음 통과).

★ 닫힘의 증표는 「도구가 존재한다」가 아니다. 도구는 존재하면서 안 불릴 수
  있고(§286 에서 `--selftest` 26개 중 16개가 그랬다), 불리면서 아무것도 안
  볼 수도 있다. 그래서 여기가 무는 것은 셋이다 —

    ① `verify.sh` 가 **정말 그 단계를 돈다**
    ② 지문 파일이 실재하고 **실물과 맞는다**
    ③ 실물이 바뀌면 **빨개진다** (반대 방향 — 이것이 없으면 항상 통과한다)

IN    tools/fieldseal.py · data/field/** · data/golden/field.fingerprint.json
OUT   없음
밖    **표의 값이 옳은가는 안 본다** — 폭 값의 진위는 `tools/widthcross.py`
      가 다른 원천과 대서 본다. 여기는 「선언한 그 파일 그대로인가」만 든다.
      **`--write` 를 안 부른다.** 그것은 사람이 새로 뽑았을 때만 치는 것이고,
      시험이 부르면 지문이 무엇이든 늘 맞아떨어진다.
      **CI 가 이 층을 갖는가**는 `tests/test_ci_env.py` 소관이다.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / "data" / "golden" / "field.fingerprint.json"
FIELD = ROOT / "data" / "field"


def _fs():
    spec = importlib.util.spec_from_file_location("fieldseal_t", ROOT / "tools" / "fieldseal.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


FS = _fs()


# ── ① 관문이 정말 불린다 ───────────────────────────────────────

def test_verify_runs_the_field_seal():
    """`verify.sh` 가 이 도구를 **단계로** 돈다.

    ★ 「도구가 있다」와 「도구가 불린다」는 다르다. §286 이 그것을 실측했다 —
      선언된 `--selftest` 26개 중 **16개를 아무도 안 불렀다.**
    """
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    assert "tools/fieldseal.py" in sh, "verify.sh 가 fieldseal 을 안 부른다"
    step = [ln for ln in sh.splitlines()
            if "tools/fieldseal.py" in ln and ln.strip().startswith("step ")]
    assert step, "fieldseal 이 `step` 이 아니다 — note 로 적으면 실패가 판정에 안 든다"
    assert "--write" not in step[0], (
        "관문이 `--write` 를 돈다 — 그러면 지문이 매번 다시 떠져 **항상 통과한다**")


def test_the_seal_is_not_ci_exempt():
    """★ 이 층은 커밋되므로 CI 가 돌 수 있다. `ci-exempt` 가 붙으면 안 된다."""
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(sh) if "tools/fieldseal.py" in ln and "step " in ln)
    head = "\n".join(sh[max(0, i - 6):i])
    assert "ci-exempt: tools/fieldseal.py" not in head, (
        "재생성 불가 층의 관문을 CI 에서 뺐다 — 이 층은 추적되므로 CI 에 있다")


# ── ② 지문이 실물과 맞는다 ─────────────────────────────────────

def _declared() -> dict[str, dict]:
    """지문이 든 파일 → 기록. **키는 `data/field` 기준 상대경로**다."""
    d = json.loads(SEAL.read_text(encoding="utf-8"))
    return d["files"]


def test_the_seal_file_exists_and_is_shaped():
    assert SEAL.is_file(), f"{SEAL.relative_to(ROOT)} 가 없다 — W13-7 이 닫히지 않았다"
    files = _declared()
    assert files, "지문이 비었다 — 빈 지문은 아무것도 안 든다"
    for rel, rec in files.items():
        assert len(rec["sha256"]) == 64, f"{rel} 의 해시가 sha256 이 아니다"
        # ★ 바이트·줄 수를 같이 든다. 해시만 있으면 「무엇이 달라졌나」를
        #   사람이 못 읽는다 — 크기가 절반이면 잘린 것이고, 같으면 내용이 바뀐 것이다.
        assert rec["bytes"] > 0 and rec["lines"] > 0, f"{rel} 의 크기가 0 이다"


def test_the_seal_matches_the_tracked_table():
    """지금 트리의 `data/field` 가 선언된 지문과 같다.

    ★ skip 이 없다. 이 층은 **추적되므로** 어느 기계에서도 실재한다 —
      없으면 그것 자체가 결함이다(재취득 불가 층이 사라졌다는 뜻이다).
    """
    import hashlib
    for rel, rec in _declared().items():
        q = FIELD / rel
        assert q.is_file(), (
            f"지문이 든 파일이 없다: data/field/{rel}\n"
            "  재취득 불가 층이다 — 지웠으면 `--write` 로 지문을 같이 옮겨야 한다")
        b = q.read_bytes()
        assert hashlib.sha256(b).hexdigest() == rec["sha256"], (
            f"data/field/{rel} 의 내용이 선언과 다르다\n"
            f"  선언 {rec['bytes']}바이트 · 실물 {len(b)}바이트\n"
            "  그날의 그 표가 아니다. 새로 뽑았으면 —\n"
            "    uv run python tools/fieldseal.py --write")
        assert len(b) == rec["bytes"], "바이트 수가 선언과 다르다"


# ── ③ 반대 방향 — 바뀌면 빨개지는가 ────────────────────────────

def test_a_changed_file_is_caught(tmp_path: Path):
    """★ 이것이 없으면 위 시험은 **항상 통과하는 검사**가 된다(§69).

    실물을 안 건드린다 — 임시 트리에 한 글자 다른 사본을 두고, 대조가
    그것을 잡는지만 본다.
    """
    import hashlib
    rel, rec = next(iter(_declared().items()))
    src = FIELD / rel
    q = tmp_path / Path(rel).name
    q.write_bytes(src.read_bytes() + b"x")
    assert hashlib.sha256(q.read_bytes()).hexdigest() != rec["sha256"], (
        "한 바이트를 붙였는데 지문이 같다 — 해시가 내용을 안 본다")
    assert len(q.read_bytes()) != rec["bytes"], "바이트 수도 안 움직였다"


def test_the_selftest_is_alive():
    """도구가 제 판별식을 들고 있다. `tools/selftests.py` 가 이것을 돈다."""
    src = (ROOT / "tools" / "fieldseal.py").read_text(encoding="utf-8")
    assert "--selftest" in src, "판별식이 없다"
