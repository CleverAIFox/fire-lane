/**
 * domain/fleetName.ts — 차종 이름 · 그림 종류 · 센터 이름.  (와이어프레임 01 · DECISIONS §214-2)
 *
 * 와이어프레임 01 은 「중형 펌프차」 처럼 **크기 먼저** 부르고, 차종마다 옆모습 그림을
 * 단다. 편성 정본(`web/config.js` CONFIG.fleet)은 「펌프차 (중형)」 으로 적는다. 정본을
 * 고치지 않고 **화면에서만** 뒤집는다 — 정본은 대장 · 파이썬 발행 · 시험이 같이 읽는다.
 */
export type VehicleClass =
  | "pump" | "tanker" | "chem" | "ladder" | "articulated" | "rescue" | "ambulance" | "light";

/** 「펌프차 (중형)」 → 「중형 펌프차」. 괄호가 없으면 그대로 */
export function displayName(label: string): string {
  const m = label.match(/^\s*(.+?)\s*\(\s*(.+?)\s*\)\s*$/);
  return m ? `${m[2]} ${m[1]}` : label.trim();
}

/**
 * `동부소방서_광주-지산-119 안전센터` → `지산119안전센터`
 *
 * ★ 2026-09-25 (PLAN §1 #130). `App.tsx` · `OpsApp.tsx` 에 **글자까지 같게** 따로 적혀
 *   있었다. 정본(`stations.geojson` 의 「소방서 및 안전센터명」)을 고치지 않고 화면에서만
 *   줄이는 일이라 `displayName` 과 같은 종류다 — 이름 표기의 집은 여기 하나다.
 */
export function shortStation(raw: string): string {
  const m = raw.match(/광주-(.+)$/);
  return (m ? m[1] : raw).replace(/[-\s]/g, "");
}

/** 이름 · id 로 그림 종류를 고른다. 모르면 펌프차 그림 */
export function vehicleClass(label: string, id = ""): VehicleClass {
  const s = `${label} ${id}`;
  if (/굴절/.test(s)) return "articulated";
  if (/사다리|ladder/.test(s)) return "ladder";
  if (/물탱크|tanker/.test(s)) return "tanker";
  if (/화학|chem/.test(s)) return "chem";
  if (/구조|rescue/.test(s)) return "rescue";
  if (/구급|amb/.test(s)) return "ambulance";
  if (/조연|light/.test(s)) return "light";
  return "pump";
}
