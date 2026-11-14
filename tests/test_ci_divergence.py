"""로컬이 CI 를 흉내 내지 못하는 분기 **넷**을 정적으로 센다 — 세는 일이 시험이다.  (PLAN #215 도착 열거 ① ②)

★ 왜 센다. 로컬 전수가 초록인데 CI 가 빨간 일이 반복됐다(`환경skip(계보)` · `core.bare`). 원인은 늘 같다 — **로컬에서 한 번도 안 타는 갈래**가 CI 에서 처음 탄다.
  이 시험은 그 갈래를 넷으로 나눠 **수를 말하고**(`-s` 로 돌리면 출력), 각 세는 눈이 **살아 있는지**(합성 입력에서 센다 · 실물에서 0 이 아니다)만 문다. 수 자체는 못 박지 않는다 — 박으면 낡는다.
    ① `skipif` / `skip` / `importorskip` 호출 — 조건이 로컬과 CI 에서 갈린다. 사유 어휘는 `test_skip_policy` 가 따로 문다.
    ② 환경변수가 다른 훅 · 도구 경로 — `GIT_DIR` · `GIT_WORK_TREE` · `GIT_INDEX_FILE` · `GIT_COMMON_DIR`(훅이 물려받는 것) · `CI` / `GITHUB_ACTIONS`(CI 만 켜는 것).
    ③ `tools/verify.sh` 의 `# ci-exempt:` — CI 가 일부러 안 도는 관문(`gate_parity` 가 사유와 거짓 면제를 문다).
    ④ 로컬에만 있는 `.gitignore` 파일(`data/**` · 루트)의 **이름을 문자열로 든** 시험 — CI 에는 그 파일이 없다.
밖    ④ 는 **상한**이다 — 같은 파일이 「없으면 skip」으로 이미 가려져 있는지는 안 따진다(위 ① 이 문다). 문자열 상수가 아닌 조립(`ROOT / "data" / x`)은 못 본다.
      「레이크 · 산출물을 가린 채 도는 CI 흉내 모드」는 정적으로 안 보인다 — 실제로 돌려 답했다(PLAN #215 보고).
"""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
SKIP_NAMES = {"skipif", "skip", "importorskip"}
GIT_ENV = re.compile(r"\b(GIT_DIR|GIT_WORK_TREE|GIT_INDEX_FILE|GIT_COMMON_DIR)\b")
CI_ENV = re.compile(r"""environ[^\n]*["'](CI|GITHUB_ACTIONS)["']|getenv\(["'](CI|GITHUB_ACTIONS)["']""")


def count_skips(source: str) -> dict[str, int]:
    out = dict.fromkeys(SKIP_NAMES, 0)
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.Call):
            name = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
            if name in out:
                out[name] += 1
    return out


def count_env_branches(text: str) -> int:
    return len(GIT_ENV.findall(text)) + len(CI_ENV.findall(text))


def count_ci_exempt(verify_sh: str) -> int:
    return sum(1 for ln in verify_sh.splitlines() if re.match(r"\s*# ci-exempt: \S+ \S", ln))


def ignored_names_in(source: str, local_only: set[str]) -> list[str]:
    return sorted({n.value for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in local_only})


def _git(*a: str) -> list[str]:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60).stdout.split("\n")


def _local_only_names() -> set[str]:
    """추적 안 되고 `.gitignore` 에 걸린 **실존** 파일 중 `data/` · 루트의 것 — 경로와 이름 둘 다."""
    out: set[str] = set()
    for p in _git("ls-files", "--others", "--ignored", "--exclude-standard"):
        if p and ((p.startswith("data/") and not p.startswith("data/interim/")) or "/" not in p) and not p.endswith(".py"):
            out |= {p, Path(p).name}
    return out


def test_the_four_ci_divergence_counters_see_synthetic_cases():
    assert count_skips("import pytest\n@pytest.mark.skipif(x, reason='r')\ndef t():\n    pytest.skip('r')\n    pytest.importorskip('m')\n") == {"skipif": 1, "skip": 1, "importorskip": 1}
    assert count_env_branches("env = {k: v for k in e if k != 'GIT_DIR'}\nos.environ.get(\"CI\")\nx = 1\n") == 2
    assert count_ci_exempt("# ci-exempt: tools/x.py 레이크가 있어야 돈다\n# ci-exempt:\n#   ci-exempt: 설명 줄\n") == 1
    assert ignored_names_in("a = 'data/processed/_lineage.json'\nb = 'other'\n", {"data/processed/_lineage.json"}) == ["data/processed/_lineage.json"]
    assert not ignored_names_in("b = 'other'\n", {"data/processed/_lineage.json"}), "로컬 전용 이름이 없는데 셌다"
    assert not count_ci_exempt("# 설명만\n"), "ci-exempt 가 없는데 셌다"


def test_the_four_unreproducible_branches_are_counted_and_each_counter_is_alive():
    skips = dict.fromkeys(SKIP_NAMES, 0)
    ignored_files: dict[str, list[str]] = {}
    local_only = _local_only_names()
    for f in sorted(p for d in (TESTS, ROOT / "src", ROOT / "tools") for p in d.rglob("*.py")):   # skip · 로컬 전용 이름은 시험에 산다 — 셋을 다 훑어도 0 이 느는 것은 없다
        src = f.read_text(encoding="utf-8")
        for k, v in count_skips(src).items():
            skips[k] += v
        if (m := ignored_names_in(src, local_only)):
            ignored_files[f.name] = m  # 파일 이름만 센다(같은 이름이 둘이면 하나로 — 상한이다)
    env_files = sorted(p for p in _git("ls-files", ".githooks", "tools", "src", "tests")
                       if p and Path(p).suffix in ("", ".py", ".sh") and count_env_branches((ROOT / p).read_text(encoding="utf-8", errors="replace")))
    exempt = count_ci_exempt((ROOT / "tools" / "verify.sh").read_text(encoding="utf-8"))
    print(f"\n[#215] ① skip 호출 {sum(skips.values())} {skips} · ② 환경변수 갈래 파일 {len(env_files)} · ③ ci-exempt {exempt} · ④ 로컬 전용 파일을 이름으로 든 시험 {len(ignored_files)}")
    assert sum(skips.values()) > 0 and env_files and exempt > 0, "세는 눈이 죽었다 — 실물에서 0 이다"
    assert ".githooks/pre-push" in env_files, "훅 경로(GIT_DIR)를 못 센다"
    assert local_only and ignored_files, "로컬 전용 파일(.gitignore)을 못 센다"
