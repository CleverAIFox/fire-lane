#!/usr/bin/env python3
"""
b5_dec.py — **오늘 판단 여섯을 적고, 내가 만든 죽은 참조 21곳을 고친다.**

    uv run python tools/batches/b5_dec.py            무엇을 할지만
    uv run python tools/batches/b5_dec.py --apply    실제로

★ `§123~143` 스물한 절이 `test_closed_plan_items_are_slots` 를 강제자로
  적었는데 **그 검사는 없다.** `test_plan_has_no_closed_items` 로 뒤집었기
  때문이다. 오늘 내내 "강제자가 옛 규약을 가리킨다" 를 잡아놓고
  **같은 것을 21곳 만들었다.** 옮길 때 강제자 이름을 본문에 박은 탓이다.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
ROOT = (_HERE.parent if _HERE.name == "batches" else _HERE).parent
DEC = ROOT / "docs/DECISIONS.md"

OLD_G = """강제자  `tests/test_doc_fsck.py::test_closed_plan_items_are_slots`
        — ⬛ 항목이 본문을 들고 있으면 운다."""
NEW_G = """강제자  `tests/test_doc_fsck.py::test_plan_has_no_closed_items`
        — PLAN 에 ⬛ 가 하나라도 있으면 운다."""

BODY = """

## 144. B3 — "지문 불변" 오분류 셋을 B4 로 넘긴다

> 2026-09-13 · 오창준

강제자  `tools/widen.py` W2 — 임계값 사본을 전 저장소에서 센다.
        되박으면 1건, 빼면 0건인 것을 실측했다(원칙 ④).

감사 232건은 B3 81건을 전부 **지문 불변**으로 분류했다. 열어보니 셋은
아니다. 합치는 순간 판정이 바뀌므로 재잠금 절차를 타야 한다.

★ **인코딩 후보 4벌 — 순서가 곧 판정이다.** `cp949` 를 먼저 보면 UTF-8
  파일도 "성공적으로" 읽히고 모지바케가 된다. `encoding.py` 머리말이
  이미 적어놨다 — *"판별 순서가 곧 신뢰도 순서다."* 넷의 순서가 서로
  다르므로 통합은 사본 제거가 아니라 판정 변경이다.

★ **`TEXT_EXT` 3벌 — 셋이 다른 질문에 답한다.** 자료 형식 판별 ·
  전처리 대상 · **저장소 소스** 검사. 같은 이름을 쓴 것이 잘못이지
  값이 다른 것이 잘못이 아니다.

★ **union-find 5벌 · 등거리 근사 3벌 — 동치성이 확인되지 않았다.**
  노드 묶음이 달라지면 `seg_uid` 가 움직이고 그것은 산출물 변경이다.

`b3_const` 가 앞의 둘에 대해 한 일은 **모으기**다. 값과 순서를 한 글자도
안 바꾸고 `encoding.py` 한 곳에 이름을 달리해 올렸다. 정본 파일이 하나가
되고 **차이가 한 화면에 보인다.** 합칠지는 B4 에서 사람이 정한다.

★ **감사 건수는 하한이다.** 규칙 조립이 3벌이 아니라 4벌이었고
(`test_normalize_rules.py` 가 `EXT` 를 전역과 테스트 지역에 두 번 들었다),
색 사본 5벌 중 둘은 사본이 아니었다(`markers.js` 는 이미 `CONFIG` 를 읽고
`render_figures` 는 인쇄용 별도 팔레트라 통일하면 `그림 ↔ 정본` 이 운다).


## 145. 환경 설정을 `.env` 로 모은다 — 셸이 이긴다

> 2026-09-13 · 오창준

강제자  `tools/env_check.py` — `.env.example` ↔ 코드를 **양방향**으로 본다.
        코드에만 있는 키와 예시에만 있는 키를 둘 다 잡는다.

`~/.fire-lane.local` 은 **아무도 안 읽는 파일이었다.** `paths.py:35` 의
`os.environ.get` 이 전부였고 그 파일을 읽는 코드가 한 줄도 없다.
인수인계서는 "복원됨" 이라고 적었는데 실물은 없었고, 있었어도 효력이
없었다. 선언이 실물보다 앞선 전형이다.

`paths._load_dotenv()` 가 저장소 루트 `.env` 를 읽는다.

★ **셸이 `.env` 를 이긴다.** 반대로 하면 `FIRE_LANE_RAW` 사고가 재현된다 —
  폐기된 변수가 현역을 경고 없이 이기던 그 자리다. `.env` 는 기본값이고
  `export` 는 그 판을 덮는 일회성 판단이다.

★ **`.env` 는 저장소 루트에 둔다.** 레이크에 두면 그 파일을 찾으려고 또
  레이크 경로가 필요하다. 그리고 오늘 증명됐듯 레이크는 사라져도 저장소는
  남는다 — `~/projects` 는 ext4 이고 `/mnt/f` 는 drvfs 다.

★ **의존성을 안 늘렸다.** `python-dotenv` 를 `paths.py` 에 물리면 순수
  표준 라이브러리 도구까지 전염된다. 15줄 파서로 끝난다.

★ **"`paths.py` 가 유일한 독자" 는 목표지 현재 상태가 아니다.**
  `os.environ` 을 직접 읽는 파일이 12개이고 **그것들은 `.env` 를 못 읽는다.**
  오늘 `lakecheck` 가 정확히 그것으로 실패했다 — `.env` 에 값이 있는데
  "FIRE_LANE_DATA 가 없다" 를 냈다. `env_check --readers` 가 세는 숫자가
  곧 `.env` 가 안 먹는 곳의 수다. 다음 배치의 첫 항목이다.


## 146. V-World 키는 숨길 수 없다 — 옮기는 목적이 다르다

> 2026-09-13 · 오창준

강제자  `.github/workflows/secret-scan.yml` — gitleaks 가 `fetch-depth: 0`
        으로 **이력 전체**를 본다. 훅(`~/.githooks/credential-check`)은
        커밋 전 · 내 기계만 보고, 이쪽은 push 후 · 모든 기여자를 본다.

`web/config.js` 에 평문으로 커밋돼 있던 것을 `web/key.js`(생성물 ·
gitignore)로 뺐다. `tools/stage_pages.py` 가 환경에서 읽어 만들고,
로컬은 `.env` · 배포는 GitHub Secrets 가 같은 이름으로 넣는다.

★ **은닉이 목적이 아니다. 될 수도 없다.** 브라우저가 WMTS 를 직접 부르니
  빌드 결과에 실려 나가고 F12 한 번에 보인다. 실효 방어는 **도메인 잠금
  하나**이고 만료는 2027-02-04 다(§6 부류 — 코드로 못 닫는다).

★ 목적은 둘이다 — ⒜ 이력에 더 안 쌓이게 한다 ⒝ **재발급을 값싸게**
  만든다. 종전에는 키를 바꾸려면 커밋을 해야 했고, 이제 Secret 만 고친다.

★ **이미 나간 이력은 감수한다.** 무료 발급이고 도메인이 고정돼 있어
  실질 위험이 낮다. 재발급하지 않는다 — **판단이며 누락이 아니다.**
  적어두지 않으면 다음 사람이 이것을 붙잡고 다시 한 시간을 쓴다.

★ `MAPBOX_TOKEN` 은 처음부터 Secrets 에 있었다. 소스에 평문이 없다.


## 147. 미러 이관이 GitHub 층을 통째로 떨어뜨렸다

> 2026-09-13 · 오창준

강제자  `tools/ruleset_check.py` — 룰셋·저장소 설정·admin·bypass·Secret 을
        `EXPECT` 와 대조한다. `REPO` 를 `git remote` 에서 읽는다.

`woongtopia` 조직에서 `CleverAIFox` 개인으로 미러 이관하면서 **브랜치 보호
룰셋 3종(`release`·`trunk`·`part`)이 통째로 안 따라왔다.**
`allow_rebase_merge` 도 `true` 로 돌아가 있었다.

★ **아무도 몰랐던 이유가 더 중요하다.** `ruleset_check.py` 가
  `"woongtopia/fire-lane"` 을 상수로 들고 있어서 `gh api` 가 404 를 냈고,
  화면은 *"로그인·권한을 확인하라"* 고 안내했다. **검사가 도는 척하고
  아무것도 안 봤다.** 원인을 엉뚱한 데서 찾게 만드는 실패 메시지가
  침묵보다 나쁘다.

★ 상수를 새 값으로 바꾸지 않고 `git remote` 에서 읽게 했다. 저장소가
  자기 이름의 정본이다. 못 읽으면 상수로 떨어지되 **그 사실을 화면에 적는다.**

★ **`@woongtopia` 흔적은 일부러 남긴다.** 이 저장소는 팀 운영 방식을
  기록으로 보존하는 것이 목적이다. 고친 것은 **지금 동작하는 코드** 두 줄
  뿐이고(`REPO` · `config.js` 의 등록 도메인 주석), 문서·그림의 옛 조직
  표기는 사실이므로 그대로 둔다.

★ **bypass 는 영구 예외다.** 개인 저장소에서 `release` 의 승인 1은 자기
  PR 을 자기가 승인할 수 없어 만족할 수 없다. 규칙을 낮추지 않고 예외를
  뒀다 — 낮추면 팀이 돌아와도 낮은 채 남고, 예외는 지우면 끝난다.
  §12-1 룰셋 표는 손대지 않았다.

★ **회수를 날짜가 아니라 조건으로 적었다.** *"본인 외 협업자가 생기면
  제거한다."* `§76`("적어두지 않은 완화는 영구가 된다")이 막으려던 것은
  적어두지 않은 완화이지 날짜 없는 예외가 아니다. **날짜는 지나가도 아무
  일이 안 일어나지만 조건은 검사가 건다** — `ruleset_check` 이 협업자를
  세고 둘이 되면 운다. §12-1c 가 죽은 문서가 아니라 실행되는 계약이다.


## 148. PLAN 은 빚 목록이다 — 슬롯을 남기지 않는다

> 2026-09-13 · 오창준

강제자  `tests/test_doc_fsck.py::test_plan_has_no_closed_items`
        — ⬛ 가 하나라도 있으면 운다.
        `tools/plan_renumber.py` — 결번을 1..N 으로 당긴다.

`§0-2` 는 *"⬛ 완료·기각. 결과는 MASTER 로 갔고 여기는 **슬롯만 남는다**"*
였다. 실물은 ⬛ 34개가 **본문을 통째로** 들고 있었고, 같은 내용이 PLAN 과
DECISIONS 두 곳에 살았다.

본문을 옮긴 뒤 슬롯을 남길 뻔했다. **그 규약 자체가 틀렸다.**
PLAN 은 앞으로 갚을 빚을 적는 문서다. 갚으면 목록에서 사라져야 한다.
갚았다는 기록은 DECISIONS 가 들고 있는데 영수증을 또 붙여두면 그것이 곧
중복이고, **개발이 끝나도 문서가 안 빈다.** 남은 일이 없는데 문서가
두꺼우면 무언가 잘못된 것이다.

★ **번호는 영구 식별자가 아니라 현재 목록의 순번이다.** 그래서 당겨도
  된다. 영구 식별자는 `DECISIONS §N` 이 맡는다 — append-only 라 안 움직인다.
  없어질 문서의 번호를 영구 식별자로 쓴 것이 애초에 잘못이었다.

★ **재배번은 지워진 번호를 가리키는 참조가 있으면 멈춘다.** 처음엔 경고만
  하고 진행했고, 그 결과 `§1 #16`(지워진 항목)이 재배번 뒤 **다른 항목을
  가리키게** 됐다. 죽은 참조보다 나쁘다 — 조용히 틀린다.
  **경고는 읽히지 않는다. 멈추는 것만 읽힌다.**

★ 치환은 대응표에 있는 것만 한다. `§12 #18` 은 기획서 §12 의 항목이지
  PLAN 번호가 아니다. 한 번 그것을 바꿨고 diff 로 잡았다.


## 149. 강제자 ↔ 규약 정합 — 어떤 도구도 안 세는 축

> 2026-09-13 · 오창준

강제자  **없다.** 그것이 이 절의 내용이다.

오늘 같은 부류를 다섯 봤다. 규약은 있는데 강제자가 없거나, **강제자가 옛
규약을 강제한다.**

    naming.vintage          "데이터 기준일" 규약이 있는데 `_plausible_date`
                            는 형식만 본다. 날짜가 틀린 것은 못 잡는다
    ruleset_check           404 로 침묵. 룰셋 3종 소실을 못 봤다
    contract.yml            죽은 게이트가 CI 에서 한 번도 안 돌았다
    PLAN §0-2               규약이 틀렸는데 그것을 **정확히 강제하는**
                            검사를 만들 뻔했다
    test_declaration_sync   *"뒤 번호를 당기지 말고 슬롯을 채운다"* —
                            슬롯을 남기던 시절의 안내가 그대로 있었다

★ **잘못된 것을 정확히 지키게 만드는 검사가 제일 위험하다.** 검사가
  있다는 사실 자체가 규약을 검증한 것처럼 보이게 하고, 그러면 아무도
  의심하지 않는다.

★ **분모를 세는 도구가 없다.** `deadcheck` 는 검사가 **도는지**를 보고
  `widen` 은 **범위가 좁은지**를 본다. 그런데 *검사가 옳은 것을 검사하는가*
  는 어느 쪽도 안 센다. 자동화가 안 된다 — 검사의 메시지와 현재 규약을
  사람이 나란히 읽어야 한다.

★ 그래서 **B6 에 축을 신설한다.** 232건 감사가 코드를 203파일 6회차로
  나눠 읽은 것과 같은 방식이다. 그때는 검사의 **존재**를 봤고 **내용**은
  안 봤다. 분모는 `verify.sh` 38단계 + pytest 578 + 훅이다.

★ 오늘 스물한 곳을 **내가 만들었다.** `§123~143` 이 옮겨질 때 강제자
  이름을 본문에 박았고, 그 검사를 곧바로 뒤집었다. 이 배치가 같이 고친다.
  **잡는 사람이 곧 만드는 사람이다** — 그래서 축이 필요하다.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    t = DEC.read_text(encoding="utf-8")
    n = t.count(OLD_G)
    done = "## 144. B3" in t

    print(f"  죽은 강제자 참조  {n}곳  → test_plan_has_no_closed_items")
    print(f"  새 절            §144~§149  {'(이미 있음)' if done else ''}")

    nums = [int(x) for x in re.findall(r"^## (\d+)\.", t, re.M)]
    if not done and max(nums) != 143:
        sys.exit(f"★ 마지막 절이 §{max(nums)} 다. §143 을 기대했다. 멈춘다.")

    if not a.apply:
        print("\n  ★ dry-run. --apply 를 붙일 것")
        return 0

    if n:
        t = t.replace(OLD_G, NEW_G)
    if not done:
        t = t.rstrip("\n") + "\n" + BODY
    DEC.write_text(t, encoding="utf-8")

    after = [int(x) for x in re.findall(r"^## (\d+)\.", t, re.M)]
    if len(after) != len(set(after)):
        sys.exit("★ 절 번호가 중복됐다. 되돌린다.")
    print(f"\n  ✓ 참조 {n}곳 · 절 {len(after)}개 · 최대 §{max(after)} · 중복 0")
    print("\n다음 — uv run python tools/doc_fsck.py")
    print("       uv run python -m pytest tests/ -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
