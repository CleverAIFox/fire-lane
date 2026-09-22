/**
 * domain/fleetName.ts — 차종 이름 · 그림 종류.  (와이어프레임 01 · DECISIONS §214-2)
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
