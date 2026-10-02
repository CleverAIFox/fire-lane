"""
roster.py — **지금 누가 나가 있는가.**

── 왜 이 파일이 생겼나 (DECISIONS §342) ────────────────────────
관제는 출동을 **3인칭으로 보며 지휘**하고, 내비는 **각각의 에이전트**다. 그러면
중개자가 알아야 하는 것이 하나 생긴다 — 지금 누가 붙어 있나.

★ 그런데 **저장소(DB)는 필요 없다.** 연결 자체가 곧 명부다. 붙어 있으면 출동
  중이고 끊기면 빠진다. 서버가 죽으면 다 다시 붙고, 그 사이를 화면이
  `HB_TTL_MS`(4초)로 이미 메운다 — `domain/opsProtocol.ts` 가 그 규약의 정본이다.

★ **출동 이력은 여기서 안 든다.** 그것은 남겨야 하는 것이고, 남기는 순간
  저장소와 스키마와 이관이 같이 생긴다. 지금 요구가 아니다.

IN    인자뿐 — 시계도 소켓도 안 읽는다
OUT   값뿐
밖    **메시지의 뜻을 안 본다.** `UnitState` 가 무엇인지 모른다 — 그 정본은
      `web/navi/src/domain/opsProtocol.ts` 이고, 중개자가 그것을 알면 말이
      바뀔 때마다 서버를 고쳐야 한다. 여기가 드는 것은 **누가 어느 방에
      있는가** 하나다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: 방 이름. 하나뿐이다 — 한 출동을 한 관제가 본다.
#: ★ 여러 출동을 동시에 보려면 방이 여럿이어야 하고, 그때 이 상수가 인자가 된다.
#:   지금 쪼개면 쓰지 않는 갈래를 시험까지 같이 들고 가게 된다.
ROOM = "fire-lane"


@dataclass(frozen=True)
class Peer:
    """붙어 있는 한 쪽."""
    cid: str
    """연결 식별자. 서버가 준다 — 같은 `unit` 이 두 번 붙을 수 있다(재접속)."""
    kind: str
    """`"ops"` 또는 `"unit"`."""
    unit: str
    """내비면 차량 식별자, 관제면 빈 문자열."""


@dataclass
class Roster:
    """붙어 있는 쪽들. **순수** — 소켓을 모른다."""

    peers: dict[str, Peer] = field(default_factory=dict)

    # ── 바뀌는 자리 ────────────────────────────────────────────
    def join(self, p: Peer) -> None:
        self.peers[p.cid] = p

    def leave(self, cid: str) -> None:
        self.peers.pop(cid, None)

    # ── 묻는 자리 ──────────────────────────────────────────────
    def units(self) -> list[str]:
        """나가 있는 차량. **중복을 접는다** — 같은 차가 두 번 붙을 수 있다."""
        return sorted({p.unit for p in self.peers.values() if p.kind == "unit" and p.unit})

    def ops_present(self) -> bool:
        """관제가 붙어 있는가.

        ★ 화면은 `HB_TTL_MS` 로 같은 것을 판단한다(§214-3). 여기 값은 **더 빠를
          뿐 다른 답을 내면 안 된다** — 관제가 끊긴 순간 서버는 바로 알고,
          화면은 4초 안에 안다.
        """
        return any(p.kind == "ops" for p in self.peers.values())

    def targets(self, sender: Peer) -> list[str]:
        """이 메시지를 받을 연결들.

        ★ **보낸 쪽에게 돌려주지 않는다.** `BroadcastChannel` 이 그렇게 동작하고
          (자기 탭은 제 메시지를 안 받는다), 어댑터를 갈아 끼워도 말이 같아야
          한다. 안 그러면 화면이 제 상태를 두 번 적용한다.

        ★ 관제가 보내면 **차량 전부**에게, 차량이 보내면 **관제에게만** 간다.
          차량끼리는 안 닿는다 — 지휘가 관제를 거치지 않으면 3인칭 시점이
          깨진다.

        ★ 2026-10-03 (DECISIONS §363). **영상은 관제와 차량 둘 다에게 간다.**
          관제는 3인칭으로 어느 골목이 지금 막혔는지 봐야 하고, 그 골목으로
          가는 차는 **관제를 기다릴 수 없다** — 통과폭은 들어가기 전에 알아야
          하고 관제가 중계하면 그만큼 늦는다. 지휘가 관제를 거친다는 규율은
          **명령**에 대한 것이고 측정은 명령이 아니다.

        ★ **영상은 아무것도 안 받는다.** 카메라는 경로를 모르고 알 필요도 없다 —
          `want` 에 `cv` 가 한 번도 안 들어가는 것이 그 선언이다. 받게 하면
          그 순간 카메라가 상태를 들게 되고, 상태를 든 센서는 센서가 아니다.
        """
        if sender.kind == "ops":
            want = ("unit",)
        elif sender.kind == "cv":
            want = ("ops", "unit")
        else:
            want = ("ops",)
        return sorted(cid for cid, p in self.peers.items()
                      if p.kind in want and cid != sender.cid)
