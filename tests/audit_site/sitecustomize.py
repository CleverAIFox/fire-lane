"""자식 파이썬 프로세스에 감사 훅을 물려준다 — `PYTHONPATH` 에 이 디렉터리가 들면 인터프리터가 시작하며 이 파일을 부른다. (PLAN #219 ①)

세션이 `FIRE_LANE_AUDIT_DIR` 를 안 켰으면 아무것도 안 한다. 설계 · 한계는 `fsaudit.py` 머리말.
"""
import fsaudit

fsaudit.install_child()
