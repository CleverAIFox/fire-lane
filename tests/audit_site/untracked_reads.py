"""시험이 연 **비추적 실존 파일**(생성물 · 환경 파일)의 선언표와 판별 — 선언 없는 읽기가 있으면 운다.

IN    읽기 장부 사본(`data/golden/testreads.json` 의 `untracked` · `reads` 칸 — 시험 파일 → 비추적 상대 경로들) · 아래 두 표
OUT   위반 문장 목록(비면 통과). `judge` · `incomplete` 는 **순수 함수**다 — 장부 사본 · 선언표 · 허용 목록을 인자로 받고 파일을 안 연다
PARAM 없음
밖    **읽기 장부가 잰 만큼만 안다** — 장부가 낡으면(`testpick` 의 `reads_stale`) 새로 읽게 된 파일은 아직 장부에 없다. 이 판별은 「재 본 칸」만 가린다(`incomplete` 가 안 잰 칸을 말한다).
      파이썬이 아닌 자식 프로세스 · `os.listdir` 같은 디렉터리 읽기는 훅이 못 본다(`fsaudit.py` 머리말).

★ 왜 있나 — 2026-11-20. `tests/test_fieldmark.py` 의 한 시험이 `data/processed/width_samples.csv`(`.gitignore` 생성물 · CI 러너에 없다)를 읽어 로컬은 초록 · CI 는 `FileNotFoundError` 로 빨갰다.
  시험 285 파일을 감사하니 `.env`(200) · `src/fire_lane.egg-info` 말고 비추적 파일을 연 시험 파일이 22개였다(8개는 「환경skip(산출물)」로 건너뛰고 14개는 안 건너뛰고 통과한다).
  이름을 문자열로 든 정적 세기(`test_ci_divergence` ④)는 **상한**이라 이것을 못 봤다. 훅이 연 것을 장부에 적고(`n` 종류 · `untracked` 칸) 이 표에 사유와 함께 든 것만 허용한다.

★ 표의 뜻 — 읽어도 **되는** 이유를 시험마다 한 줄로 적는다. 사유 분류(앞말):
    「환경skip(산출물) — …」   산출물이 없으면 건너뛴다(CI 에서 안 돈다). 레이크 기계에서는 돈다(`skip_policy` 가 산출물 skip 이 레이크 기계에서 나면 실패로 센다).
    「있으면 읽고 없으면 거른다 — …」   글롭 · 복사 · 선택 읽기라 없어도 시험이 안 깨진다. **빈 채 초록**이다 — 이 시험이 실제로 무엇을 훑었는지는 이 표가 안 말한다.
  새 읽기를 표에 올리기 전에 **그 시험이 산출물 없는 러너에서 초록인지** 먼저 본다(임시 체크아웃에서). 초록이 아니면 표가 아니라 시험을 고친다(표본 입력을 스스로 만든다 · 33d95841).
"""
from __future__ import annotations

from collections.abc import Mapping
from fnmatch import fnmatchcase

MIN_REASON = 10          # 글자 — 이보다 짧은 사유는 「사유 없음」이다

# 모든 시험에 면제인 배경 — **이 셋 말고 늘리지 않는다**(`test_untracked_reads.py` 가 셋으로 박는다). 항목마다 한 줄 사유.
ALLOW: dict[str, str] = {
    ".env": "파이썬 환경 로더가 import 때 읽는다(200개 시험이 간접으로 읽는다) — 시험이 고르는 입력이 아니다",
    "src/fire_lane.egg-info/*": "패키지 메타데이터 — 편집 설치가 만들고 `importlib.metadata` 가 import 때 읽는다",
    "web/navi/dist/*": "CI 가 `npm run build` 로 만든다 — 러너에도 있다",
}

# 시험 파일 → {비추적 경로 패턴(`fnmatch`) → 읽어도 되는 이유 한 줄}. 2026-11-20 감사의 실제 경로로 채웠다(시험 22개).
DECLARED: dict[str, dict[str, str]] = {
    "test_ci_env.py": {"data/processed/*": "환경skip(산출물) — 실제 트리(`route_vehicle.csv` 등)가 없으면 건너뛴다. 이 검사는 CI 에서 안 돈다"},
    "test_dest_scope.py": {"data/processed/*": "환경skip(산출물) — `boundary_emd.geojson` · `civil_office.geojson` 이 없으면 건너뛴다(표본 `tests/fixtures` 로 이름 셋은 돈다)"},
    "test_dms_ids.py": {"data/dms/*": "있으면 읽고 없으면 거른다 — `data/dms` 를 통째로 임시 디렉터리에 복사할 뿐이다(단언은 추적 파일 `BOOKMARK.json` 만 본다)"},
    "test_doc_fsck.py": {
        "data/processed/*": "있으면 읽고 없으면 거른다 — `check_absent` 가 `data/processed/*.json|csv` 를 글롭해 「없다」고 선언한 말이 남았나 훑는다(없으면 훑을 것이 줄 뿐)",
        "web/review.html": "있으면 읽고 없으면 거른다 — `check_expiry` 가 `web/*.html` 을 글롭해 `data-expires` 가 남았나 훑는다",
    },
    "test_embeddable.py": {"web/review.html": "있으면 읽고 없으면 거른다 — `web/` 의 화면을 글롭해 프레임 차단 · 정적 파일 여부를 훑는다(있는 화면만)"},
    "test_evalgen.py": {"data/processed/*": "환경skip(산출물) — `need_real` 이 산출물(`segments.geojson` · `route_vehicle.csv`)이 없으면 건너뛴다"},
    "test_evalgen_building.py": {"data/processed/route_vehicle.csv": "임포트가 읽는다 — `from test_evalgen import` 가 모듈 수준 `_why_no_real()` 을 돌려 파일이 있을 때만 `gate_manifest` 가 연다. 이 파일의 시험 9개는 합성 트리만 쓰고, 그 파일을 치워도 같은 9개가 초록이다(재서 확인)"},
    "test_evalset.py": {"data/processed/width_samples.csv": "환경skip(산출물) — `width_samples.csv`(커밋 안 되는 파일)가 없으면 건너뛴다"},
    "test_fixture_rules.py": {"data/processed/*": "있으면 읽고 없으면 거른다 — `fixture_recut.run` 이 원본이 없으면 `[건너뜀]` 을 찍고 지나간다(레이크 기계에서만 잰다 · 빈 채 초록)"},
    "test_lineage_last_writer.py": {"data/processed/*": "환경skip(산출물) — 실제 계보 `_lineage.json` 이 없으면 건너뛴다(`.gitignore` 라 CI 에 없다) · 지문은 그 계보가 가리키는 산출물"},
    "test_n1.py": {
        "data/processed/*": "있으면 읽고 없으면 거른다 — 옛 주소 문자열을 저장소 전체 `rglob` 로 훑는다(있는 파일만 · 빈 채 초록)",
        "data/dms/*": "있으면 읽고 없으면 거른다 — 옛 주소 `rglob` 훑기(있는 파일만)",
        "data/interim/*": "있으면 읽고 없으면 거른다 — 옛 주소 `rglob` 훑기(있는 파일만)",
        "web/review.html": "있으면 읽고 없으면 거른다 — 옛 주소 `rglob` 훑기(있는 파일만)",
        "REDLIST.json": "있으면 읽고 없으면 거른다 — 옛 주소 `rglob` 훑기(`.gitignore` 로컬 목록)",
        "LAKELIST.json": "있으면 읽고 없으면 거른다 — 옛 주소 `rglob` 훑기(`.gitignore` 로컬 목록)",
        ".wrangler/*": "있으면 읽고 없으면 거른다 — 옛 주소 `rglob` 훑기(`.gitignore` 로컬 캐시)",
    },
    "test_processed_env.py": {"data/processed/*": "환경skip(레이크) — 격리 재취입의 원본이 레이크에 없으면 건너뛴다. 메인 `data/processed` 를 복사해 전후 해시만 본다"},
    "test_rvpower.py": {"data/processed/width_samples.csv": "환경skip(산출물) — `_hy_real` 이 `width_samples.csv` 나 발행본이 없으면 건너뛴다"},
    "test_scope_tier.py": {"data/processed/*": "환경skip(산출물) — 발행본 `web/data/segments.geojson` 이 없으면 건너뛴다 · `fire_access.csv` 는 있을 때만 읽는다"},
    "test_scopedecl.py": {"data/_scopedecl_selftest.py": "자기가 쓴 임시 파일이다 — `scopedecl --selftest` 가 합성 소스를 쓰고 읽고 곧 지운다. 생성물이 아니라 읽기 전에 스스로 만든다(CI 러너에서도 같다)"},
    "test_seal_axes.py": {"data/processed/*": "있으면 읽고 없으면 거른다 — `rawcache` 가 `.rawprint.json` 이 없으면 빈 표로 간다(봉인 SEAL 이 없으면 따로 건너뛴다)"},
    "test_seg_uid_first_class.py": {"data/processed/*": "환경skip(산출물) — 발행본이 없으면 건너뛴다. 산출물 csv · json 은 글롭이라 있는 것만 훑는다"},
    "test_shardseal.py": {"data/processed/*": "있으면 읽고 없으면 거른다 — `rawcache` 가 `.rawprint.json` 이 없으면 빈 표로 간다"},
    "test_sources_of_truth.py": {"web/review.html": "있으면 읽고 없으면 거른다 — 사실 소비처를 `web/*.html` 글롭으로 훑는다(있는 화면만)"},
    "test_tasktpl.py": {"data/dms/*": "있으면 읽고 없으면 거른다 — PLAN 을 읽는 시험을 찾으려 `rglob` 로 `.md` · `.txt` 를 훑는다(있는 파일만)"},
    "test_tonecheck.py": {"web/review.html": "있으면 읽고 없으면 거른다 — `tonecheck.targets` 가 `web/*.html` 을 훑는다(있는 화면만)"},
    "test_width_any_gate.py": {"data/processed/width_samples.csv": "환경skip(산출물) — `width_samples.csv` · `segments.geojson` 이 없으면 건너뛴다(`fire-lane --from segments` 가 만든다)"},
    "test_width_fn_reproduces.py": {"data/processed/width_samples.csv": "환경skip(산출물) — `segments_5186.gpkg` · `width_samples.csv` 가 없으면 건너뛴다"},
    "test_width_med.py": {"data/processed/width_samples.csv": "환경skip(산출물) — `width_samples.csv` 가 없으면 건너뛴다"},
}


def _hit(path: str, patterns: Mapping[str, str] | list[str]) -> bool:
    return any(fnmatchcase(path, p) for p in patterns)


def judge(untracked: Mapping[str, list[str]], declared: Mapping[str, Mapping[str, str]], allow: Mapping[str, str]) -> list[str]:
    """(장부의 `untracked` 사본 · 선언표 · 허용 목록) → 위반 문장들. 순수 함수.

    ① 선언 없는 읽기 — 허용 목록에도 그 시험의 선언에도 안 든 비추적 읽기.
    ② 죽은 선언 — 선언표에 있는데 장부에 그 읽기가 없다(시험이 더는 안 읽거나 시험이 없어졌다). 죽은 선언은 사각지대다.
    ③ 사유가 빈 선언 — 허용 목록 · 선언표의 사유가 `MIN_REASON` 글자 미만이다."""
    bad: list[str] = []
    for test, paths in sorted(untracked.items()):
        decl = declared.get(test, {})
        for p in sorted(paths):
            if not _hit(p, allow) and not _hit(p, decl):
                bad.append(f"선언 없는 비추적 읽기 — {test} 가 {p} 를 연다(생성물 · 환경 파일 — CI 러너에 없을 수 있다)")
    for test, pats in sorted(declared.items()):
        for pat, why in sorted(pats.items()):
            if not any(fnmatchcase(p, pat) for p in untracked.get(test, [])):
                bad.append(f"죽은 선언 — {test} 의 「{pat}」 는 장부에 그 읽기가 없다(선언을 지우거나 장부를 다시 잰다)")
            if len(why.strip()) < MIN_REASON:
                bad.append(f"사유가 빈 선언 — {test} 의 「{pat}」")
    for pat, why in sorted(allow.items()):
        if len(why.strip()) < MIN_REASON:
            bad.append(f"사유가 빈 허용 — 「{pat}」")
    return bad


def dead_allow(untracked: Mapping[str, list[str]], allow: Mapping[str, str]) -> list[str]:
    """④ 죽은 허용 — 허용 목록 항목을 장부의 **어느 시험도** 안 읽는다(목록이 실물보다 넓으면 방패가 아니라 사각지대다). 장부 전체의 성질이라 `judge` 와 따로다. 순수 함수."""
    return [f"죽은 허용 — 허용 목록 「{pat}」 를 장부의 어느 시험도 안 읽는다" for pat in sorted(allow)
            if not any(fnmatchcase(p, pat) for ps in untracked.values() for p in ps)]


def incomplete(ledger: Mapping[str, object]) -> list[str]:
    """장부 사본에서 **비추적 읽기를 아직 안 잰** 시험 파일 — `reads` 에 칸이 있는데 `untracked` 에 칸이 없다. 순수 함수.

    측정(`testpick --measure-reads --write`)은 시험마다 `untracked` 칸을 적는다(빈 칸 = 안 읽는다). 칸이 없으면 옛 장부이거나 그 시험이 아직 안 재졌다."""
    reads = ledger.get("reads")
    got = ledger.get("untracked")
    names = sorted(reads) if isinstance(reads, dict) else []
    have = got if isinstance(got, dict) else {}
    return [n for n in names if n not in have]
