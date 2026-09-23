#!/usr/bin/env python3
"""
test_sources_of_truth.py — 사실마다 정본과 따르는 자리가 같은가 (계급 가드 2).

── 왜 생겼나 ───────────────────────────────────────────────────
2026-09-22 (DECISIONS §218-6 · 계급 가드 2). uv 판이 CI 둘 · Dockerfile 에 0.12.13 으로
박혀 있는데 `.devcontainer/setup.sh` 의 대체 설치만 판이 없었다 — 그날의 최신을 받았다.
`render_figures` 는 TRUCK 은 정본에서 읽으면서 여유선 7.0 은 글자로 박았다. 같은 값이
여러 파일에 사는 것을 막을 수 없는 자리(YAML · Dockerfile · 셸)는 **목록으로 적고 맞춘다.**

── 목록이 어디 사나 (2026-09-23) ───────────────────────────────
★ 종전에는 `docs/SOURCES_OF_TRUTH.yaml` 이 목록이었다. **저장소의 문서는 넷이다**
  (MASTER · PLAN · DECISIONS · 기획서). 문서를 하나 더 만드는 것으로 규율을 세우면
  규율이 늘 때마다 문서가 는다. 그래서 목록을 **둘로 갈라** 각자의 집에 뒀다 —

    기계가 읽는 판   `SPEC` — 이 파일 안. 강제자와 같은 파일에 사는 것이 맞다
    사람이 읽는 판   MASTER §17-1 표 — 사실 · 정본 파일 · 따르는 곳 · 강제자

  둘이 갈리면 `test_master_table_and_spec_agree` 가 **양방향**으로 운다.

── SPEC 모양 ───────────────────────────────────────────────────
  owner      {file, regex}   정본. regex 의 첫 그룹이 값이다. **정확히 한 번** 걸려야 한다
  consumers  [{file, has} | {file, ref} | {file, regex, cmp}]
               has    이 문자열이 있어야 한다. `{v}` 가 값으로 바뀐다(`{v:g}` 는 수로 서식)
               ref    정본을 읽는다는 증거 문자열(값 대신 정본 경로·이름을 적는 자리)
               regex  첫 그룹을 값과 cmp(`==` · `>=` 판 비교)로 견준다
             ★ 공백은 무시하고 견준다(`Pretendard, system-ui` ≡ `Pretendard,system-ui`)
  scan       [글롭]  아래 둘을 볼 범위. 없으면 안 본다
  pins       [{find, regex}]  scan 안에서 `find` 가 나오는 자리마다 regex 가 그 자리에서
             걸리고 첫 그룹이 값이어야 한다 · 그 파일은 owner/consumers 에 있어야 한다
  exclusive  true 면 scan 안에서 값 literal 이 owner/consumers 밖에 나오면 실패

  ① owner regex 가 정확히 한 번 걸린다(집이 하나다)
  ② consumer 마다 값(has) · 정본 참조(ref) · 비교(regex+cmp) 가 맞다
  ③ scan 범위 안에서 pins 자리는 전부 값과 같고, 그 파일은 목록에 있다
  ④ exclusive 면 값 literal 이 목록 밖 파일에 없다
  ⑤ SPEC ↔ MASTER §17-1 표가 양방향으로 같다

★ 값을 바꿀 때는 owner 를 고치고 시험이 가리키는 consumers 를 따라 고친다. 새 자리를
  만들면 SPEC consumers 와 MASTER 표에 같이 더한다 — 안 더하면 exclusive/pins 가 운다.
★ 문서(docs/*.md)는 SPEC 에 안 든다. 커버리지 래칫의 문서 대조는 test_verify_citations 가,
  판정 숫자의 문서 대조는 docnum_check 가 이미 한다.

IN    SPEC(이 파일) · docs/MASTER.md §17-1 · 그것이 가리키는 파일
OUT   없음 (검사)
PARAM 없음
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "docs" / "MASTER.md"

# ── 기계가 읽는 판 ─────────────────────────────────────────────
# ★ 사람이 읽는 판은 MASTER §17-1 이다. 여기 사실을 더하면 그 표에도 더한다.
SPEC: dict[str, dict] = {
    "uv": {
        "what": "uv 판 — CI · 배포 · 이미지 · devcontainer 가 같은 uv 로 uv.lock 을 푼다",
        "owner": {"file": "Dockerfile", "regex": r"ghcr\.io/astral-sh/uv:([\w.]+)"},
        "consumers": [
            {"file": ".github/workflows/contract.yml", "has": 'version: "{v}"'},
            {"file": ".github/workflows/deploy.yml", "has": 'version: "{v}"'},
            {"file": ".devcontainer/setup.sh", "has": "astral.sh/uv/{v}/install.sh"},
        ],
        "scan": [".github/**/*", "Dockerfile*", ".devcontainer/*"],
        "pins": [
            {"find": "astral-sh/setup-uv@",
             "regex": r'astral-sh/setup-uv@\S+\s*\n\s*with:\s*\n\s*version:\s*"([^"]*)"'},
            {"find": "astral-sh/uv:", "regex": r"astral-sh/uv:([\w.]+)"},
            {"find": "astral.sh/uv/", "regex": r"astral\.sh/uv/([\d.]+)/install\.sh"},
        ],
        "exclusive": True,
    },
    "node": {
        "what": "내비 빌드 · 타입 검사 노드 판 (DECISIONS §186-2 · test_ci_env)",
        "owner": {"file": "web/navi/.nvmrc", "regex": r"^(\d+)\s*$"},
        "consumers": [
            {"file": ".github/actions/build-navi/action.yml",
             "ref": "node-version-file: web/navi/.nvmrc"},
            {"file": ".github/workflows/contract.yml",
             "ref": "node-version-file: web/navi/.nvmrc"},
            {"file": ".devcontainer/devcontainer.json", "has": '"version": "{v}"'},
        ],
        "scan": [".github/**/*", ".devcontainer/*", "web/navi/package.json"],
        "pins": [{"find": "node-version:", "regex": r'node-version:\s*"?(\d+)'}],
        "code_only": True,
    },
    "python": {
        "what": "파이썬 판 (W3-17)",
        "owner": {"file": ".python-version", "regex": r"^([\d.]+)\s*$"},
        "consumers": [
            {"file": "Dockerfile", "has": "FROM python:{v}-slim"},
            {"file": "pyproject.toml", "has": 'requires-python = ">={v}"'},
            {"file": ".github/workflows/contract.yml",
             "ref": "python-version-file: .python-version"},
            {"file": ".github/workflows/deploy.yml",
             "ref": "python-version-file: .python-version"},
        ],
        "scan": [".github/**/*", "Dockerfile*"],
        "pins": [
            {"find": "python-version:", "regex": r'python-version:\s*"?([\d.]+)'},
            {"find": "FROM python:", "regex": r"FROM python:([\d.]+)"},
        ],
    },
    "pytest": {
        "what": "pytest 하한 — dev 그룹 한 곳(W3-1). 잠금이 하한 아래로 내려가면 안 된다",
        "owner": {"file": "pyproject.toml", "regex": r'"pytest>=([\d.]+)"'},
        "consumers": [
            {"file": "uv.lock", "regex": r'name = "pytest"\nversion = "([\d.]+)"',
             "cmp": ">="},
        ],
        "scan": [".github/**/*", "pyproject.toml", ".pre-commit-config.yaml"],
        "pins": [{"find": "pytest>=", "regex": r"pytest>=([\d.]+)"}],
        "code_only": True,
    },
    "coverage_floor": {
        "what": "커버리지 래칫 문턱 — 명령줄은 숫자를 안 적고 변수를 읽는다(W3-11)",
        "owner": {"file": "tools/verify.sh", "regex": r"^COV_MIN=(\d+)\s*$"},
        "consumers": [
            {"file": "tools/verify.sh", "ref": '"$COV_MIN"'},
            {"file": "tests/test_verify_citations.py", "ref": "COV_MIN="},
        ],
        "scan": [".github/**/*", "tools/*.sh", "pyproject.toml"],
        "pins": [{"find": "--cov-fail-under=", "regex": r"--cov-fail-under=(\d+)"}],
        "code_only": True,
    },
    "truck_m": {
        "what": "통과 하한(m) — 판정 임계",
        "owner": {"file": "src/firelane/seg/params.py", "regex": r"^TRUCK\s*=\s*([\d.]+)"},
        "consumers": [
            {"file": "web/config.js", "has": "폭 {v}m 미만"},
            {"file": "tools/render_figures.py", "ref": '"TRUCK"'},
            {"file": "tests/test_declaration_sync.py", "ref": 'p["TRUCK"]'},
            # ★ 2026-09-23 (DECISIONS §222-5). `scan` 이 찾아낸 자리들. 전부 **문구**지만
            #   TRUCK 이 움직이면 그 문구가 거짓말이 된다 — 그래서 사본이 맞다. 등재한다.
            {"file": "src/firelane/seg/geom.py", "has": "wmax < {v} -> blocked"},
            {"file": "src/firelane/seg/report.py", "has": "통과 하한 {v}m"},
            {"file": "src/firelane/seg/vehicle.py", "has": "TRUCK = {v}"},
            {"file": "src/firelane/segments.py", "has": "TRUCK={v}"},
        ],
        "scan": ["src/firelane/**/*.py", "web/navi/src/**/*.ts", "web/*.js"],
        "exclusive": True,
        "code_only": True,
        "near": r"TRUCK|truck|통과\s*하한|필요\s*폭|requiredWidth|전폭",
    },
    "park_m": {
        "what": "주차 1대 노면점유(m) — 여유선 = TRUCK + 2×PARK",
        "owner": {"file": "src/firelane/seg/params.py", "regex": r"^PARK\s*=\s*([\d.]+)"},
        "consumers": [
            {"file": "tools/render_figures.py", "ref": '"PARK"'},
            {"file": "tests/test_declaration_sync.py", "ref": 'p["PARK"]'},
        ],
        "scan": ["web/navi/src/domain/*.ts", "web/*.js"],
        "exclusive": True,
        "code_only": True,
        "near": r"PARK|park|주차|여유선",
    },
    "cctv_range_m": {
        "what": "CCTV 유효 측정 반경(m)",
        "owner": {"file": "src/firelane/seg/params.py",
                  "regex": r"^CCTV_RANGE\s*=\s*([\d.]+)"},
        "consumers": [
            {"file": "web/config.js", "has": "유효범위 {v:g}m 밖"},
            {"file": "tools/render_figures.py", "ref": '"CCTV_RANGE"'},
            {"file": "src/firelane/seg/vehicle.py", "has": "CCTV_RANGE = {v}"},
            {"file": "src/firelane/segments.py", "has": "CCTV_RANGE={v}"},
        ],
        "scan": ["src/firelane/**/*.py", "web/navi/src/**/*.ts", "web/*.js"],
        "exclusive": True,
        "code_only": True,
        "near": r"CCTV_RANGE|cctv|유효\s*범위|유효\s*측정",
    },
    "code_owner": {
        "what": "저장소 단독 소유자(CODEOWNERS 기본 규칙 · 2026-09-09 개인 계정 이관)",
        "owner": {"file": ".github/CODEOWNERS", "regex": r"^\*\s+@(\S+)"},
        "consumers": [
            {"file": "tools/navi_setup.py", "has": 'default="@{v}"'},
            {"file": "tools/ruleset_check.py", "has": 'ADMINS = ["{v}"]'},
            {"file": "tools/ruleset_check.py", "has": 'FALLBACK_REPO = "{v}/fire-lane"'},
            # ★ 2026-09-23. `scan` 을 붙이자마자 나온 **진짜 사본 셋**이다(DECISIONS §222-5).
            #   배치 도구가 `REPO=CleverAIFox/fire-lane` 을 각자 박고 있었고 아무도 안 봤다.
            #   소유자가 바뀌면 셋이 조용히 남의 저장소를 가리킨다 — 2족 그대로다.
            {"file": "tools/fl.sh", "has": "{v}/fire-lane"},
            {"file": "tools/merge_batch.sh", "has": "{v}/fire-lane"},
            {"file": "tools/branch_tidy.sh", "has": "{v}/fire-lane"},
        ],
        "scan": [".github/**/*", "tools/*.py", "tools/*.sh"],
        "exclusive": True,
        "code_only": True,
    },
    "font_stack": {
        "what": "그림 · 화면 글꼴 스택",
        "owner": {"file": "tools/render_figures.py", "regex": r'^FONT = "([^"]+)"'},
        "consumers": [
            {"file": "web/navi/src/ui/tokens.ts", "has": 'family: "{v}"'},
            {"file": "web/proposal.html", "has": "{v}"},
        ],
        "scan": ["web/navi/src/**/*.ts", "web/navi/src/**/*.tsx", "web/*.html",
                 "web/*.js", "tools/*.py"],
        "exclusive": True,
        "code_only": True,
    },
}


class _V(str):
    """`{v}` 는 적힌 그대로, `{v:g}` 처럼 서식이 붙으면 수로 서식한다."""
    def __format__(self, spec: str) -> str:
        return str(self) if not spec else format(float(self), spec)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _ver(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", s))


def owner_value(fact: dict) -> str:
    o = fact["owner"]
    hits = re.findall(o["regex"], _read(o["file"]), re.M)
    assert len(hits) == 1, (f"정본 {o['file']} 에서 {o['regex']!r} 가 {len(hits)}번 걸린다 — "
                            "집이 하나가 아니거나 서식이 바뀌었다")
    return hits[0]


#: 확장자 → (줄 주석 토큰, 블록 주석 쌍). 스캔에서 주석을 걷는 데 쓴다.
_COMMENT = {
    ".py": ("#", None), ".sh": ("#", None), ".yml": ("#", None), ".yaml": ("#", None),
    ".toml": ("#", None), ".cfg": ("#", None), ".nvmrc": ("#", None),
    ".ts": ("//", ("/*", "*/")), ".tsx": ("//", ("/*", "*/")),
    ".js": ("//", ("/*", "*/")), ".mjs": ("//", ("/*", "*/")),
    ".json": (None, None), ".md": (None, None),
}


def strip_comments(txt: str, suffix: str) -> str:
    """주석을 지운 코드만 남긴다.

    ★ 2026-09-23 (DECISIONS §222-5). 이것이 없어서 값 사실 여섯에 `scan` 을 못 붙였다.
      `web/navi/src/domain/vehicle.ts` 는 「3.0 / 0.5 / 1.8 / 2.5 를 여기서 재선언하지
      않는다」고 **주석으로** 적는다 — 옳은 코드인데 `exclusive` 가 그것을 사본으로 읽는다.
      잘못된 경보는 진짜 경보를 죽인다(MASTER §18-13). 그래서 스캔은 **코드만** 본다.
    ★ 완벽한 파서가 아니다 — 문자열 안의 `#` · `//` 도 지운다. 그 방향의 오차는
      **안전하다**(덜 보고 덜 운다). 반대 방향(주석을 코드로 보는 것)만 위험하다.
    """
    line_tok, block = _COMMENT.get(suffix, ("#", None))
    if block:
        out, i = [], 0
        while True:
            a = txt.find(block[0], i)
            if a < 0:
                out.append(txt[i:]); break
            b = txt.find(block[1], a + 2)
            out.append(txt[i:a])
            if b < 0:
                break
            i = b + 2
        txt = "".join(out)
    if not line_tok:
        return txt
    return "\n".join(ln.split(line_tok)[0] for ln in txt.splitlines())


def _scan_files(fact: dict) -> list[Path]:
    out: set[Path] = set()
    for g in fact.get("scan", []):
        out |= {p for p in ROOT.glob(g) if p.is_file()}
    return sorted(out)


def _listed(fact: dict) -> set[str]:
    return {fact["owner"]["file"], *(c["file"] for c in fact["consumers"])}


def consumer_errors(fact: dict, v: str) -> list[str]:
    bad = []
    for c in fact["consumers"]:
        txt = _read(c["file"])
        if "has" in c:
            want = c["has"].format(v=_V(v))
            if _squash(want) not in _squash(txt):
                bad.append(f"{c['file']} 에 {want!r} 가 없다")
        elif "ref" in c:
            if _squash(c["ref"]) not in _squash(txt):
                bad.append(f"{c['file']} 가 정본을 읽지 않는다 — {c['ref']!r} 가 없다")
        else:
            hits = re.findall(c["regex"], txt, re.M)
            cmp = c.get("cmp", "==")
            ok = hits and all((_ver(h) >= _ver(v)) if cmp == ">=" else h == v for h in hits)
            if not ok:
                bad.append(f"{c['file']} 의 {hits or '(못 찾음)'} 가 정본 {v} 와 {cmp} 가 아니다")
    return bad


def scan_errors(fact: dict, v: str) -> list[str]:
    bad, listed = [], _listed(fact)
    for p in _scan_files(fact):
        rel = p.relative_to(ROOT).as_posix()
        try:
            txt = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if fact.get("code_only"):
            txt = strip_comments(txt, p.suffix)
        for pin in fact.get("pins", []):
            for m in re.finditer(re.escape(pin["find"]), txt):
                got = re.compile(pin["regex"]).match(txt, m.start())
                line = txt[: m.start()].count("\n") + 1
                if not got or got.group(1) != v:
                    bad.append(f"{rel}:{line} 이 판을 {got.group(1) if got else '안 적었다'!s} "
                               f"— 정본은 {v}")
                elif rel not in listed:
                    bad.append(f"{rel}:{line} 에 값이 있는데 목록(consumers)에 없다")
        if fact.get("exclusive") and rel not in listed:
            # ★ 2026-09-23 (DECISIONS §222-5). `near` 가 없으면 **맨숫자**를 사본으로 읽는다.
            #   `3.0` 은 버퍼 거리 · 허용오차 · 배율로 저장소 곳곳에 있고, 그것을 「통과 하한의
            #   사본」이라고 부르면 열 곳이 거짓으로 운다 — 그러면 사람이 이 검사를 끈다.
            #   문맥 낱말과 **같은 줄**에 있을 때만 이 사실의 사본으로 센다.
            near = fact.get("near")
            for i, ln in enumerate(txt.splitlines(), 1):
                if v not in ln:
                    continue
                if near and not re.search(near, ln):
                    continue
                bad.append(f"{rel}:{i} 에 {v} 가 literal 로 있는데 목록에 없다"
                           + (f" (문맥 {near!r})" if near else ""))
                break
    return bad


@pytest.mark.parametrize("name", sorted(SPEC))
def test_fact_consumers_follow_owner(name: str):
    fact = SPEC[name]
    v = owner_value(fact)
    bad = consumer_errors(fact, v) + scan_errors(fact, v)
    assert not bad, (f"사실 {name!r} (정본 {fact['owner']['file']} = {v}) 이 갈렸다:\n  "
                     + "\n  ".join(bad)
                     + "\n  정본을 고쳤으면 따르는 자리를 같이 고치고, 새 자리면 "
                       "이 파일의 SPEC consumers 에 더한다.")


def test_the_spec_covers_the_declared_facts():
    """빈 그물 금지 — 맡은 사실이 목록에서 빠지면 검사도 조용히 빠진다."""
    need = {"uv", "node", "python", "pytest", "coverage_floor",
            "truck_m", "park_m", "cctv_range_m", "code_owner", "font_stack"}
    assert need <= set(SPEC), f"빠진 사실: {sorted(need - set(SPEC))}"


# ── SPEC ↔ MASTER §17-1 (2026-09-23) ──────────────────────────
# 표 한 행 = `| `사실` | `정본 파일` | 따르는 곳 | 강제자 |`
MASTER_ROW = re.compile(r"^\|\s*`([\w]+)`\s*\|\s*`([^`]+)`\s*\|")


def master_table() -> dict[str, str]:
    """MASTER §17-1 의 사실 → 정본 파일. 표를 못 읽으면 빈 dict 가 아니라 실패다."""
    txt = MASTER.read_text(encoding="utf-8")
    m = re.search(r"^### 17-1\.[^\n]*\n(.*?)(?=^#{2,3} )", txt, re.M | re.S)
    assert m, ("docs/MASTER.md 에 `### 17-1.` 절이 없다 — 사람이 읽는 정본 표가 사라졌다.\n"
               "  절을 되살리거나 이 시험이 보는 자리를 같이 옮긴다.")
    rows = {}
    for line in m.group(1).splitlines():
        if hit := MASTER_ROW.match(line):
            rows[hit.group(1)] = hit.group(2)
    assert rows, ("MASTER §17-1 표에서 행을 하나도 못 읽었다 — 서식이 바뀌었거나 표가 비었다.\n"
                  "  행은 `| `사실` | `정본 파일` | 따르는 곳 | 강제자 |` 꼴이다.")
    return rows


def test_master_table_and_spec_agree():
    """사람이 읽는 표(MASTER §17-1)와 기계가 읽는 판(SPEC)이 **양방향**으로 같은가.

    ★ 2026-09-23. 목록이 둘로 갈린 순간 갈릴 자리가 생긴다 — 한쪽만 고치는 것이
      이 저장소가 반복한 2족(정본이 둘)이다. 그래서 한 방향이 아니라 둘을 본다.
      ① SPEC 의 사실마다 표에 행이 있고 정본 파일이 같다
      ② 표의 행마다 SPEC 에 사실이 있다(표에만 적고 강제를 안 붙인 것이 없다)
    """
    rows, bad = master_table(), []
    for name, fact in sorted(SPEC.items()):
        want = fact["owner"]["file"]
        if name not in rows:
            bad.append(f"SPEC 의 {name!r} 이 MASTER §17-1 표에 없다 — 사람이 볼 자리가 없다")
        elif rows[name] != want:
            bad.append(f"{name!r} 의 정본 파일이 갈렸다 — 표 {rows[name]!r} · SPEC {want!r}")
    for name in sorted(set(rows) - set(SPEC)):
        bad.append(f"MASTER §17-1 표의 {name!r} 이 SPEC 에 없다 — 적어놓고 강제자가 없다")
    assert not bad, ("MASTER §17-1 표와 SPEC 이 갈렸다:\n  " + "\n  ".join(bad)
                     + "\n  사실을 더하거나 지울 때는 **둘 다** 고친다.")


# ── 검사가 무는가 ──────────────────────────────────────────────

def test_unpinned_installer_and_stray_literal_are_caught(tmp_path, monkeypatch):
    """판 없는 설치 줄 · 목록 밖 literal · 어긋난 consumer 가 각각 잡힌다."""
    (tmp_path / "Dockerfile").write_text("COPY --from=ghcr.io/astral-sh/uv:9.9.9 /uv /bin/\n")
    (tmp_path / "setup.sh").write_text("curl -LsSf https://astral.sh/uv/install.sh | sh\n")
    (tmp_path / "other.yml").write_text("# uv 9.9.9 를 쓴다\n")
    (tmp_path / "ci.yml").write_text('version: "9.9.8"\n')
    monkeypatch.setattr(__import__(__name__), "ROOT", tmp_path)
    fact = {"owner": {"file": "Dockerfile", "regex": r"astral-sh/uv:([\w.]+)"},
            "consumers": [{"file": "setup.sh", "has": "astral.sh/uv/{v}/install.sh"},
                          {"file": "ci.yml", "has": 'version: "{v}"'}],
            "scan": ["*"], "exclusive": True,
            "pins": [{"find": "astral.sh/uv/", "regex": r"astral\.sh/uv/([\d.]+)/install\.sh"}]}
    v = owner_value(fact)
    assert v == "9.9.9"
    errs = consumer_errors(fact, v) + scan_errors(fact, v)
    joined = "\n".join(errs)
    assert "setup.sh 에" in joined and "ci.yml 에" in joined, joined
    assert "안 적었다" in joined, joined
    assert "other.yml:1 에 9.9.9" in joined, joined


def test_master_table_reader_bites(tmp_path, monkeypatch):
    """표 읽기가 살아 있는가 — 행이 빠지면 · 정본이 다르면 각각 잡힌다."""
    doc = tmp_path / "MASTER.md"
    doc.write_text(
        "### 17-1. 정본\n\n"
        "| 사실 | 정본 파일 | 따르는 곳 | 강제자 |\n"
        "|---|---|---|---|\n"
        "| `uv` | `Dockerfile` | CI 둘 | `x.py` |\n"
        "| `ghost` | `nowhere` | 없다 | `x.py` |\n\n"
        "## 18. 다음\n", encoding="utf-8")
    monkeypatch.setattr(__import__(__name__), "MASTER", doc)
    got = master_table()
    assert got == {"uv": "Dockerfile", "ghost": "nowhere"}, got
    assert set(got) - set(SPEC) == {"ghost"}, "강제자 없는 행이 안 드러난다"
    assert {n for n in SPEC if n not in got}, "표에서 빠진 사실이 안 드러난다"
