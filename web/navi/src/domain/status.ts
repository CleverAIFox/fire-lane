/**
 * domain/status.ts — 주행 화면의 **상태 한 자리.**  (와이어프레임 2026-09-21)
 *
 * ── 왜 표 하나인가 ──────────────────────────────────────────────
 * 지혜님 09-21 와이어프레임 28장 중 18장(03 · 03B · 05~17A · 23)은 **화면이
 * 다른 것이 아니다.** 상단바 하나에 제목 · 부제 · 모드 배지 · ETA 표시만
 * 바뀐다. 18개 컴포넌트를 만들면 18곳을 고쳐야 하고, 표 한 줄씩이면 한
 * 곳이다. 상단바(`ui/TopBar.tsx`)는 이 표를 읽기만 한다.
 *
 * ── 신호가 있는 것과 없는 것 ───────────────────────────────────
 * 이탈 · 도착 · 경로 없음 · CCTV 없는 골목 · 최종 접근 · 통행 불가/우회는
 * **실제 신호**에서 나온다(`deriveStatus`). GPS 약함 · 통신 끊김 · 서버
 * 오류 · 데이터 지연은 지금 그 신호를 내는 곳이 없다 — 서버도 없고
 * GPS 정확도도 안 받는다. 그래서 `injected: true` 로 표시하고 시연 막대가
 * 주입한다. **주입인 줄 모르고 보면 그것이 거짓 화면이다** — 그래서
 * 상단바가 주입 상태에 작은 표지를 단다.
 *
 * ★ 판정 임계값·판정색은 여기 없다. 정본은 `seg/params.py` 와
 *   `web/config.js` 다. 여기는 **화면 어휘**만 든다.
 */

/** 와이어프레임 파일 번호. 검수표가 이 번호로 화면을 맞춘다. */
export type StatusKey =
  | "safe"          // 03   안전 경로 안내중
  | "fast"          // 03B  빠른 경로 안내중
  | "approach"      // 05   최종 접근 지점
  | "reroute"       // 06   경로 재탐색 중
  | "noCctv"        // 07   CCTV 없는 골목 주행
  | "gpsWeak"       // 08   GPS 신호 약함
  | "offline"       // 09 · 09A  통신 끊김 · 저장 경로
  | "restored"      // 10   안내 복구
  | "dataDelayed"   // 11   도로 정보 지연
  | "serviceError"  // 12   경로 서비스 오류
  | "noRoute"       // 13   폭 조건 경로 없음
  | "noData"        // 14   도로 데이터 부족
  | "blocked"       // 16   전방 통행 불가
  | "detour"        // 17 · 17A  우회 경로 적용
  | "detourAccess"  // 17   우회 불가 → 대체 접근 지점 (§214-2)
  | "noDetour"      // 13   통행 불가 신고 뒤 닿는 곳이 없다 (§214-2)
  | "arrived"       // 15   접근 지점 도착
  | "reported";     // 23   도착 보고 공유

/** 배지 색. 와이어프레임의 네 톤 그대로다. */
export type Tone = "green" | "yellow" | "cyan" | "white";

/** 예상 도착 칸에 무엇을 띄우나. */
export type EtaMode = "value" | "computing" | "checking" | "none" | "arrivedAt";

/** 경로선 모양. */
export type RouteLook = "solid" | "pending" | "faded";

export interface StatusSpec {
  /** 와이어프레임 번호 — 검수표가 이것으로 스크린샷을 짝짓는다 */
  wf: string[];
  tone: Tone;
  /** 배지 윗줄 작은 태그 */
  tag: string;
  /** 배지 아랫줄 큰 글씨 */
  label: string;
  /** 비면 회전 안내를 제목으로 쓴다 */
  title?: string;
  /** `{last}` · `{vehicle}` · `{need}` · `{road}` · `{len}` 을 채운다 */
  sub?: string;
  /** 제목 왼쪽 표지. 비면 회전 화살표 */
  icon?: "P";
  eta: EtaMode;
  route: RouteLook;
  /** 남은 시간·거리 알약을 비우나 */
  blankRemain?: boolean;
  /**
   * 알약을 **아예 안 띄우나.** 05 · 15 · 23 은 와이어프레임에 알약이 없다 —
   * 차량 안내가 끝났거나 끝나 가는 자리다(2026-09-22 검수).
   */
  noRemain?: boolean;
  /** 신호가 없어 시연 막대가 넣는 상태 */
  injected?: boolean;
  /** 경고 한 줄 — 07 의 「주정차 여부 미확인 · 감속 주행」 */
  caution?: string;
}

export const STATUS: Record<StatusKey, StatusSpec> = {
  safe: { wf: ["03", "03A"], tone: "green", tag: "빠른 경로 안내",
    label: "안전 경로 안내중", eta: "value", route: "solid" },
  fast: { wf: ["03B"], tone: "yellow", tag: "안전 경로 안내",
    label: "빠른 경로 안내중", eta: "value", route: "solid" },
  approach: { wf: ["05"], tone: "green", tag: "폭 기준 추천", label: "목적지 도착",
    title: "최종 접근 지점", sub: "차량 진입 가능 구간 종료", icon: "P",
    eta: "none", route: "solid", noRemain: true },
  reroute: { wf: ["06"], tone: "cyan", tag: "경로 이탈", label: "새 경로 확인 중",
    title: "경로 재탐색 중", sub: "새 경로 확정 후 안내 재개",
    eta: "computing", route: "pending", blankRemain: true },
  noCctv: { wf: ["07"], tone: "white", tag: "CCTV 없는 골목 주행 중",
    label: "CCTV 없는 골목 주행 중", caution: "주정차 여부 미확인 · 감속 주행",
    eta: "value", route: "solid" },
  gpsWeak: { wf: ["08"], tone: "cyan", tag: "위치 확인", label: "GPS 신호 약함",
    title: "현재 위치 확인 중", sub: "마지막 수신 {last}",
    eta: "checking", route: "faded", blankRemain: true, injected: true },
  offline: { wf: ["09", "09A"], tone: "cyan", tag: "통신 끊김",
    label: "저장 경로로 안내 중", eta: "value", route: "solid", injected: true },
  restored: { wf: ["10"], tone: "cyan", tag: "안내 복구",
    label: "현재 위치 확인 완료", eta: "value", route: "solid", injected: true },
  dataDelayed: { wf: ["11"], tone: "cyan", tag: "갱신 지연",
    label: "도로 정보 확인 필요", eta: "value", route: "solid", injected: true },
  serviceError: { wf: ["12"], tone: "cyan", tag: "연결 오류", label: "경로 계산 실패",
    title: "경로 안내 일시 중지", sub: "경로 계산 서버 응답 없음",
    eta: "none", route: "pending", blankRemain: true, injected: true },
  noRoute: { wf: ["13"], tone: "cyan", tag: "폭 조건 불충족", label: "다른 접근 지점 필요",
    title: "차량 경로 없음", sub: "{vehicle} · 요구 폭 {need}m",
    eta: "none", route: "pending", blankRemain: true },
  // ★ 2026-09-22 (§214-2). 신고 뒤에 경로가 없으면 **폭 문제가 아니다.** 종전에는 13 의
  //   「{차종} · 요구 폭 3.0m」 가 떠서 폭 때문인 것처럼 읽혔다. 원인을 말한다.
  noDetour: { wf: ["13"], tone: "cyan", tag: "통행 불가 · 우회 없음", label: "다른 접근 지점 필요",
    title: "우회 경로 없음", sub: "{road} 통행 불가 · 300m 안 접근 지점 없음",
    eta: "none", route: "pending", blankRemain: true },
  noData: { wf: ["14"], tone: "cyan", tag: "미측정 구간", label: "현장 확인 필요",
    title: "경로 판정 보류", sub: "도로 폭 정보 부족",
    eta: "none", route: "pending", blankRemain: true },
  blocked: { wf: ["16"], tone: "cyan", tag: "현장 통행 불가", label: "우회 경로 필요",
    title: "전방 통행 불가", sub: "{road} · {len}m 구간",
    eta: "none", route: "solid", blankRemain: true },
  detour: { wf: ["17", "17A"], tone: "cyan", tag: "통행 불가 구간 제외",
    label: "우회 경로 적용 완료", eta: "value", route: "solid" },
  // ★ 2026-09-22 (§214-2). 우회가 **없을** 때. 종전에는 13(경로 없음)으로 떨어졌다.
  //   닿는 가장 가까운 곳에 대고 걸어 들어간다 — 도보는 **직선** 거리다.
  detourAccess: { wf: ["17"], tone: "cyan", tag: "우회 불가 · 접근 지점 변경",
    label: "대체 접근 지점 안내", title: "대체 접근 지점으로 안내",
    sub: "{road} 통행 불가 · 도보 약 {walk}m(직선)", eta: "value", route: "solid" },
  arrived: { wf: ["15"], tone: "cyan", tag: "도착 완료", label: "차량 안내 종료",
    title: "접근 지점 도착", sub: "차량 안내 종료 · 현장 접근 준비", icon: "P",
    eta: "none", route: "solid", blankRemain: true, noRemain: true },
  reported: { wf: ["23"], tone: "cyan", tag: "도착 완료", label: "차량 안내 종료",
    title: "접근 지점 도착", sub: "차량 안내 종료", icon: "P",
    eta: "arrivedAt", route: "solid", blankRemain: true, noRemain: true },
};

/** 시연 막대가 넘기는 순서. 와이어프레임 번호순이다. */
export const STATUS_ORDER: StatusKey[] = [
  "safe", "fast", "approach", "reroute", "noCctv", "gpsWeak", "offline",
  "restored", "dataDelayed", "serviceError", "noRoute", "noData", "arrived",
  "blocked", "detour", "detourAccess", "noDetour", "reported",
];

/** 상태를 정하는 신호. 전부 `useNavigation` 과 앱이 이미 가진 값이다. */
export interface StatusSignals {
  phase: "guiding" | "arrived" | "other";
  choice: "safe" | "fast";
  rerouting: boolean;
  noRoute: boolean;
  /** 통행 불가를 신고했고 아직 우회를 못 냈다 */
  blockedPending: boolean;
  /** 우회를 적용한 뒤 몇 초 동안 */
  detourFresh: boolean;
  /** 경로 끝이 사건 지점이 아니라 대체 접근 지점이다(§214-2) */
  accessAlt?: boolean;
  /** 통행 불가로 신고한 구간이 하나라도 있다 */
  blockedAny?: boolean;
  /** 도착 보고가 관제에 닿았다 */
  arrivalAcked: boolean;
  /** 경로 끝까지 남은 거리(m) */
  remainM: number | null;
  /**
   * 지금 구간이 **CCTV 로 검증되지 않는** 좁은 구간인가.
   * `unknown` 은 전부 CCTV 25m 밖이다(layers.ts · `unknown` 354).
   */
  onUnverified: boolean;
  /** 시연 막대가 넣은 상태. 있으면 이긴다 */
  injected: StatusKey | null;
}

/** 최종 접근으로 바꾸는 남은 거리(m). 와이어프레임 05 가 목적지 100여 m 앞이다. */
export const APPROACH_M = 120;

/**
 * 신호 → 상태. **순서가 곧 우선순위다.**
 *
 * ★ 도착 · 경로 없음 · 재탐색이 위다 — 안내가 성립하지 않는 상태가
 *   골목 경고보다 앞선다. 경로가 없는데 「CCTV 없는 골목 주행 중」 을
 *   띄우면 거짓이다.
 */
export function deriveStatus(s: StatusSignals): StatusKey {
  if (s.injected) return s.injected;
  if (s.phase === "arrived") return s.arrivalAcked ? "reported" : "arrived";
  if (s.noRoute) return s.blockedAny ? "noDetour" : "noRoute";
  if (s.blockedPending) return "blocked";
  if (s.rerouting) return "reroute";
  if (s.detourFresh) return s.accessAlt ? "detourAccess" : "detour";
  if (s.remainM != null && s.remainM <= APPROACH_M) return "approach";
  if (s.onUnverified) return "noCctv";
  return s.choice === "fast" ? "fast" : "safe";
}

/** 부제의 자리표를 채운다. 모르는 자리표는 그대로 둔다 — 빈칸보다 낫다. */
export function fillText(t: string | undefined, v: Record<string, string>): string | undefined {
  if (!t) return t;
  return t.replace(/\{(\w+)\}/g, (m, k: string) => v[k] ?? m);
}
