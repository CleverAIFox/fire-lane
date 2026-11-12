"""
test_uicheck.py — 화면 관문이 **오늘의 두 결함을 실제로 잡는가**.
(DECISIONS §310 · `tools/uicheck.py` · `tools/mergecheck.py`)

── 왜 이 파일이 생겼나 (2026-09-29) ────────────────────────────
전수 73단계가 **통과 73 · 실패 0** 으로 끝난 뒤, 사람이 화면을 열었더니 관제가
아예 안 떠 있었다. 열흘 묵은 빌드본이 사유였고, **그것을 보는 관문이 하나도
없었다.** `verify.sh` 마지막 줄이 「WebGL 은 스크립트가 못 본다. 사람이 눈으로
확인할 것」이었고, 거기가 이 저장소에 남은 마지막 「사람이 본다」였다.

★ 그래서 이 시험이 무는 것은 「지금 초록인가」가 아니다. **「그날의 결함을
  다시 넣으면 빨개지는가」**다. 지금 초록인 것만 보면, 판별식이 죽어도 초록이다
  (§230 — 0건이 청결인가 죽음인가).

IN    tools/uicheck.py · tools/mergecheck.py · verify.sh · contract.yml
OUT   없음
밖    **화면이 예쁜가는 안 본다.** 색·자리·글자 크기는 사람의 판단이다.
      **브라우저를 안 띄운다** — WebGL 이 실제로 그려지는가는 여전히 관문 밖이고,
      그 사실은 `tools/uicheck.py` 의 `밖` 칸이 든다.
      **원격 상태는 안 본다** — `mergecheck` 의 실물 조회는 CI 소관이다.
      여기서는 그 도구의 **판정기**만 든다.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_t", ROOT / "tools" / f"{name}.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


UI = _load("uicheck")
MC = _load("mergecheck")
DV = _load("uidrive")


# ── ① 공유 층 — 「닮았다」의 실측 ───────────────────────────────

def test_the_two_screens_share_exactly_the_declared_layers():
    """지금 트리의 공유 층이 선언과 같다. **이것이 관문 자체다.**"""
    sh = UI.shared_layers()
    assert len(sh) == UI.SHARED_LAYERS, (
        f"공유 지도 층 {len(sh)} ≠ 선언 {UI.SHARED_LAYERS}\n  {' '.join(sh)}")


def test_the_shared_set_is_what_driving_still_needs():
    """★ 수만 맞추면 안 된다. **무엇이 남았는지**가 판단의 내용이다(§311).

    주행 화면에도 값이 있어 남긴 것들 — 바탕 · 도로 선 · 다음 회전 도로명 ·
    소화전. 이것이 사라지면 세는 법이 틀린 것이다.
    """
    sh = set(UI.shared_layers())
    for want in ("bg", "road-area", "seg-road", "lbl-road", "hydrant", "bldg"):
        assert want in sh, f"`{want}` 가 공유 목록에 없다 — 세는 법이 바뀌었으면 §311 을 고쳐라"


def test_what_driving_turns_off_is_really_gone():
    """★ 반대 방향. 사람이 「내비가 GIS 뷰어 같다」고 한 근거가 이것들이었다.

    끄기로 선언한 것이 공유에 남아 있으면 **수만 내려가고 화면은 그대로**다.
    """
    off, sh = set(UI.navi_off()), set(UI.shared_layers())
    assert off, "`NAVI_OFF` 선언을 못 읽었다"
    for gone in ("lbl-bldg", "lbl-poi", "seg-tint", "bldg-contact"):
        assert gone in off, f"`{gone}` 가 주행 예산에서 빠졌다"
        assert gone not in sh, f"`{gone}` 가 아직 공유다"


def test_the_declaration_has_exactly_one_home():
    """★ `NaviMap` 이 그 목록을 **실제로 돈다.** 도구가 제 목록을 따로 들면 정본이 둘이다."""
    navimap = (DV.SRC / "components" / "NaviMap.tsx").read_text(encoding="utf-8")
    assert "NAVI_OFF" in navimap, "내비가 선언을 안 쓴다 — 선언만 하고 안 끄는 꼴이다"
    opsmap = (DV.SRC / "components" / "OpsMap.tsx").read_text(encoding="utf-8")
    assert "NAVI_OFF" not in opsmap, "관제가 주행 예산을 쓴다 — 두 화면의 일이 다르다"
    for o in UI.navi_off():
        assert any(o in v for v in UI.layer_ids().values()), f"`{o}` 는 실재하지 않는 층이다"


def test_ops_starts_in_3d():
    """★ 관제 기본이 3D 다(§311). 토글은 2026-09-23 부터 있었고 기본이 꺼져 있었다."""
    src = (DV.SRC / "OpsApp.tsx").read_text(encoding="utf-8")
    import re as _re
    m = _re.search(r"bldg:\s*(true|false)", src)
    assert m, "`bldg` 기본값을 못 찾았다"
    assert m.group(1) == "true", "관제가 평면으로 시작한다 — 층수가 진입 판단에 든다"


def test_a_layer_moved_into_both_screens_turns_it_red():
    """★ 반대 방향. 층이 늘면 빨개지는가 — 없으면 항상 통과하는 검사다."""
    per = UI.layer_ids()
    assert "opsSegLayers" in per, "관제 전용 묶음을 못 찾았다"
    # 관제 전용 묶음을 내비도 부르게 만들면 공유가 는다
    orig = UI.NAVI_FNS
    try:
        UI.NAVI_FNS = (*orig, "opsSegLayers")
        grown = UI.shared_layers()
        assert len(grown) > UI.SHARED_LAYERS, "층을 섞었는데 공유 수가 안 늘었다"
        assert any("늘었다" in b for b in UI.split()), "늘었는데 빨간불이 안 난다"
    finally:
        UI.NAVI_FNS = orig


# ── ② 배타 부품 — 두 화면이 섞이는 것 ──────────────────────────

def test_each_screen_uses_only_its_own_parts():
    for app, parts in UI.EXCLUSIVE.items():
        other = next(a for a in UI.EXCLUSIVE if a != app)
        for p in parts:
            assert UI._uses(app, p), f"{app} 이 `<{p}>` 를 안 쓴다"
            assert not UI._uses(other, p), f"{other} 가 {app} 전용 `<{p}>` 를 쓴다"


def test_the_switch_itself_is_alive():
    """`main.tsx` 가 두 화면을 가른다. 이게 죽으면 루트가 관제를 못 띄운다."""
    src = (DV.SRC / "main.tsx").read_text(encoding="utf-8")
    assert UI.FLAG in src, f"`{UI.FLAG}` 를 안 읽는다 — 2026-09-29 의 결함이 이것이다"
    assert '=== "ops"' in src, "`view === \"ops\"` 분기가 없다"


# ── ③ 빌드본 — 그날의 결함 ─────────────────────────────────────

def test_a_stale_build_is_caught(tmp_path: Path, monkeypatch):
    """★ 빌드본이 소스보다 낡으면 빨개지는가. **2026-09-29 의 결함이다.**

    실물을 안 건드린다 — 임시 트리에 낡은 빌드를 세우고 판정만 본다.
    """
    import os
    dist, src = tmp_path / "dist", tmp_path / "src"
    (dist / "assets").mkdir(parents=True)
    src.mkdir()
    (dist / "index.html").write_text("<head></head>", encoding="utf-8")
    (dist / "assets" / "a.js").write_text(f'window.{UI.FLAG}', encoding="utf-8")
    (src / "main.tsx").write_text("x", encoding="utf-8")
    os.utime(dist / "index.html", (1_700_000_000, 1_700_000_000))
    os.utime(dist / "assets" / "a.js", (1_700_000_000, 1_700_000_000))
    monkeypatch.setattr(UI, "DIST", dist)
    monkeypatch.setattr(UI, "SRC", src)
    bad = UI.build()
    assert any("낡았다" in b for b in bad), f"낡은 빌드를 통과시킨다 — {bad}"


def test_a_bundle_that_ignores_the_flag_is_caught(tmp_path: Path, monkeypatch):
    """★ 서버가 깃발을 박아도 **번들이 그 말을 모르면** 관제가 안 뜬다.

    이것이 2026-09-29 에 실제로 일어난 일이다.
    """
    dist, src = tmp_path / "dist", tmp_path / "src"
    (dist / "assets").mkdir(parents=True)
    src.mkdir()
    (src / "main.tsx").write_text("x", encoding="utf-8")
    (dist / "index.html").write_text("<head></head>", encoding="utf-8")
    (dist / "assets" / "a.js").write_text("console.log(1)", encoding="utf-8")  # 깃발 없음
    monkeypatch.setattr(UI, "DIST", dist)
    monkeypatch.setattr(UI, "SRC", src)
    assert any(UI.FLAG in b and "없다" in b for b in UI.build()), (
        "깃발을 모르는 번들을 통과시킨다 — 그러면 관제가 영영 안 뜬다")


def test_a_missing_build_is_red_not_skipped(tmp_path: Path, monkeypatch):
    """★ 빌드본이 없으면 **건너뛰지 않고 빨간불**이다. 화면이 없다는 뜻이므로."""
    monkeypatch.setattr(UI, "DIST", tmp_path / "nope")
    bad = UI.build()
    assert bad and "빌드본이 없다" in bad[0]
    assert "건너뛸 사유가 아니다" in bad[0], "건너뜀으로 적으면 이 축이 조용히 사라진다"


# ── ④ 머지 절차 ────────────────────────────────────────────────

def test_a_red_merge_is_caught():
    """★ 빨간불 위에서 머지된 PR 을 잡는가. 2026-09-29 에 셋이 그랬다."""
    def node(n, st):
        return {"number": n, "title": "t", "mergedAt": "",
                "commits": {"nodes": [{"commit": {"statusCheckRollup":
                                                  ({"state": st} if st else None)}}]}}
    for st in ("FAILURE", "PENDING", None):
        bad, ok, _ = MC.judge([node(1, st)])
        assert bad and not ok, f"{st} 를 초록으로 본다"
    bad, ok, _ = MC.judge([node(1, "SUCCESS")])
    assert not bad and ok == 1


def test_a_declared_bypass_is_shown_not_hidden():
    """★ 이미 일어난 우회는 **사유와 함께 찍히고** 빨강으로 안 센다(§320).

    ★ 왜 선언이 필요한가. 이 도구는 최근 20건을 본다 — 이미 일어난 우회는
      20건이 지나갈 때까지 매번 빨갛다. 매번 뜨는 빨강은 안 읽히는 빨강이 되고,
      그때 **진짜 우회도 같이 묻힌다**(§313-1 ③ 과 같은 족).
    """
    def node(n, st):
        return {"number": n, "title": "t", "mergedAt": "",
                "commits": {"nodes": [{"commit": {"statusCheckRollup":
                                                  ({"state": st} if st else None)}}]}}
    n = next(iter(MC.KNOWN_BYPASS))
    bad, _ok, known = MC.judge([node(n, "FAILURE")])
    assert not bad and len(known) == 1, "선언된 우회를 빨강으로 센다"
    assert "그 뒤" in known[0], "**그 뒤에 무엇이 달라졌나**를 안 찍는다 — 그것이 없으면 미결이다"

    # ★ 반대 방향 둘. 없으면 목록이 면죄부가 된다.
    bad, _ok, _k = MC.judge([node(424242, "FAILURE")])
    assert bad, "선언에 없는 새 우회를 덮는다"
    bad, _ok, _k = MC.judge([node(n, "SUCCESS")])
    assert bad, "죽은 선언(초록이었던 PR)을 통과시킨다 — 거짓말하는 면제다"

    for k, v in MC.KNOWN_BYPASS.items():
        assert len(v) == 3, f"#{k} 선언이 날짜 · 무엇을 · 그 뒤에 셋을 안 든다"
        assert all(len(x) >= MC.MIN_REASON for x in v[1:]), f"#{k} 사유가 사유가 아니다"
    assert len(MC.KNOWN_BYPASS) <= MC.BYPASS_MAX, (
        f"선언이 {len(MC.KNOWN_BYPASS)} — 래칫 {MC.BYPASS_MAX} 보다 늘었다."
        " 우회가 한 번 더 있었다는 뜻이다")


def test_mergecheck_is_ci_only_and_says_so():
    """★ 로컬에서 건너뛰는 것이 아니라 **물음이 성립하지 않는다**고 적혔는가."""
    src = (ROOT / "tools" / "mergecheck.py").read_text(encoding="utf-8")
    assert "CI 전용" in src, "왜 로컬에서 안 도는지가 도구에 안 적혀 있다"
    assert "물음이 성립하지 않는다" in src or "물음은 원격에만" in src


# ── ⑤ 배선 ─────────────────────────────────────────────────────

def test_verify_runs_both_axes():
    sh = (ROOT / "tools" / "verify.sh").read_text(encoding="utf-8")
    for want in ("tools/uicheck.py --split", "tools/uicheck.py --build"):
        assert want in sh, f"verify.sh 가 `{want}` 를 안 부른다"
    for ln in sh.splitlines():
        if "tools/uicheck.py" in ln and ln.strip().startswith("step "):
            break
    else:
        raise AssertionError("uicheck 가 `step` 이 아니다 — note 면 실패가 판정에 안 든다")


def test_the_source_axis_is_in_ci():
    """★ `--split` 은 소스만 보므로 CI 에서도 돈다. 여기가 빠지면 본체가 샌다."""
    yml = (ROOT / ".github" / "workflows" / "contract.yml").read_text(encoding="utf-8")
    assert "tools/uicheck.py --split" in yml, "공유 층 관문이 CI 에 없다"
    assert "tools/mergecheck.py" in yml, "머지 절차 관문이 CI 에 없다"


def test_selftests_are_alive():
    for t in ("uicheck", "mergecheck"):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / f"{t}.py"), "--selftest"],  # noqa: S603 — 트리 안의 도구다
                           capture_output=True, text=True, cwd=ROOT, timeout=120)
        assert r.returncode == 0, f"{t} --selftest 실패\n{r.stdout}{r.stderr}"


# ── 주행 중 화면의 시선 기준 (DECISIONS §702) ──────────────────────────────

_F = ("ui/TopBar.tsx",)


def _drive_tree(tmp_path: Path, body: str, tokens: str = "export const F = {\n  big: 22,\n  base: 14,\n} as const;\n") -> Path:
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "tokens.ts").write_text(tokens, encoding="utf-8")
    (tmp_path / "ui" / "TopBar.tsx").write_text(body, encoding="utf-8")
    return tmp_path


def test_a_long_driving_sentence_is_counted_and_a_short_one_is_not(tmp_path: Path):
    body = ('const a = "여기서 멈춘다";\n'
            'const b = "이 문장은 운전자가 한 번에 읽기에는 너무 길게 적었다 — 스무 자를 넘는다";\n'
            'const c = `${n}m 통행 불가`;\n'
            '// "주석 안의 아주 긴 문장은 세지 않는다 — 스무 자를 훌쩍 넘더라도 화면에 안 뜬다"\n'
            'const d = <p>JSX 글도 한 번에 읽는 양이라서 스무 자를 넘으면 센다</p>;\n')
    got = DV.drive_long_lines(_drive_tree(tmp_path, body), files=_F)
    assert [t[:6] for _, t in got] == ["이 문장은 ", "JSX 글도"], got


def test_a_placeholder_is_counted_as_the_width_it_takes(tmp_path: Path):
    """`${…}` 는 코드 글자가 아니라 **값이 차지하는 자리**로 잰다 — 안 그러면 짧은 말이 코드 길이로 길어진다."""
    got = DV.drive_long_lines(_drive_tree(tmp_path, 'const a = `전방 ${Math.round(d.aheadM)}m`;\n'), files=_F)
    assert got == []


def test_a_small_font_is_counted_through_tokens_and_ternaries(tmp_path: Path):
    body = ("const s = { fontSize: 30 }; const t = { fontSize: F.big }; const u = { fontSize: F.base };\n"
            "const v = { fontSize: i ? 13 : 26 }; const w = { fontSize: 24 };\n"
            "// const x = { fontSize: 10 };\n")
    got = DV.drive_small_fonts(_drive_tree(tmp_path, body), files=_F)
    assert [e for _, e in got] == ["F.big", "F.base", "i ? 13 : 26"], got


def test_driving_files_never_scroll_text_by_themselves():
    """★ Android Auto 품질 기준 ST-1 — **자동으로 흐르는 글자를 두지 않는다.** 소스에 `scrollTo` · `scrollIntoView` · 마퀴 · `setInterval` 이 없다(가운데 맞춤의 `translateX(-50%)` 는 정적이라 안 센다).
    (사용자가 손으로 넘기는 `overflowY: auto` 는 자동이 아니다.)"""
    bad = []
    for rel in DV.DRIVE_FILES:
        p = DV.SRC / rel
        assert p.is_file(), rel
        src = DV.uncomment(p.read_text(encoding="utf-8"))
        for pat in ("scrollTo", "scrollIntoView", "marquee", "setInterval"):
            if pat in src:
                bad.append(f"{rel}: {pat}")
    assert not bad, bad


def test_the_driving_ratchets_match_the_tree_and_are_declared_down_only():
    assert len(UI.drive_long_lines()) == UI.DRIVE_LONG
    assert len(UI.drive_small_fonts()) == UI.DRIVE_SMALL_FONT
    assert UI.RATCHETS["DRIVE_LONG"] == UI.RATCHETS["DRIVE_SMALL_FONT"] == "down"
    assert {"DRIVE_LONG", "DRIVE_SMALL_FONT"} <= set(UI.ratchet_values())


def test_the_ops_screen_is_not_a_driving_file():
    """★ 관제 화면은 **운전 중이 아니다** — 앉아서 여러 정보를 동시에 보는 화면이라 규범이 다르다. 주행 중 수에 관제 전용 파일이 들면 안 된다."""
    assert not any(f.startswith(("OpsApp", "ui/Ops", "ui/SegCard")) for f in DV.DRIVE_FILES)
