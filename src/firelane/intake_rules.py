#!/usr/bin/env python3
"""
intake_rules.py — 편입 관문의 **판정 규칙 정본**.

★ 2026-08-30. `JUNK` 가 `tools/intake.py` 와 `tools/doctor.py`(두 번,
  같은 파일에) 세 벌로 있었고 셋이 갈렸다. intake 쪽은 `.sh` · `.py` 를
  막는데 doctor 사본은 안 막아서, Downloads 에 둔 작업 스크립트를
  doctor 가 "편입 대기 중" 이라고 말했다 — **도구가 서로 다른 답을 냈다.**

  같은 개념의 사본은 정의가 갈리는 것이 아니라 판정이 갈린다.
  tools 는 패키지를 import 할 수 있으나 그 반대는 아니다. 정본은 여기다.

IN    없음
OUT   없음 (규칙 선언)
PARAM 없음
"""
from __future__ import annotations

import re

# 브라우저·OS 부산물과 **작업 스크립트**. landing 으로 올리지 않는다.
# ★ 2026-08-26. `apply.sh` · `docx_fix.py` · `desktop.ini` 가 landing 에
#   올라갔다. 다운로드 폴더는 사용자의 작업 공간이라 데이터만 있지 않다.
#   확장자 화이트리스트가 아니라 블랙리스트인 이유는, 새 데이터 형식이
#   왔을 때 조용히 막히는 편보다 쓰레기가 한 번 섞이는 편이 낫기 때문이다.
JUNK = re.compile(
    # ★ 2026-08-30. `채용일정.html` 이 편입 대기열에 앉았다. 다운로드
    #   폴더는 작업 공간이고 웹페이지 저장본이 섞인다. html/htm 은
    #   이 프로젝트에서 데이터로 받은 적이 없다 — 생기면 그때 뺀다.
    r"\.(crdownload|part|tmp|partial|sh|py|mjs|ini|lnk|url|exe|msi|bat"
    r"|html|htm|torrent)$"
    r"|^~\$|^\.DS_Store$|^desktop\.ini$", re.IGNORECASE)
