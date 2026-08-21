/* Fire-Lane · 표지판 아이콘 — CCTV 표지
   ────────────────────────────────────────────────────────────
   ★ app.js 에서 잘라낸 원문이다. 캔버스 좌표 하나 안 건드렸다.
     이 파일들은 순수 함수다 — map 도 CONFIG 도 모른다(cctv 제외).
     그래서 브라우저 없이도 눈으로 대조할 수 있고, 아이콘을 고칠 때
     지도 로직을 읽지 않아도 된다.
   ──────────────────────────────────────────────────────────── */

import { CONFIG } from "../config-access.js";
import { SIGN_PX } from "./size.js";

export function makeCctvImage(){
  const W = SIGN_PX, c = document.createElement("canvas");
  c.width = c.height = W;
  const g = c.getContext("2d");
  const DISC = CONFIG.cctvCov.colorDark, BLK = "#111111";

  g.beginPath(); g.arc(W/2, W/2, 82, 0, Math.PI*2);
  g.fillStyle = DISC; g.fill();
  g.lineWidth = 12; g.strokeStyle = BLK; g.stroke();

  g.fillStyle = BLK; g.strokeStyle = BLK;
  g.lineJoin = "round"; g.lineCap = "round";

  /* 벽 브래킷 — 몸통보다 먼저 깔아 뒤로 보낸다 */
  g.lineWidth = 9;
  g.beginPath(); g.moveTo(118, 96); g.lineTo(140, 112); g.stroke();
  g.fillRect(138, 88, 13, 48);

  /* 카메라 몸통 — 왼쪽 위로 기울인 원통 */
  g.save();
  g.translate(88, 84); g.rotate(-0.30);
  const bx=-44, by=-20, bw=80, bh=40, br=19;
  g.beginPath();
  g.moveTo(bx+br,by); g.arcTo(bx+bw,by,bx+bw,by+bh,br);
  g.arcTo(bx+bw,by+bh,bx,by+bh,br); g.arcTo(bx,by+bh,bx,by,br);
  g.arcTo(bx,by,bx+bw,by,br); g.closePath(); g.fill();
  g.beginPath(); g.arc(bx+2, 0, 21, 0, Math.PI*2); g.fill();
  g.beginPath(); g.arc(bx+2, 0, 11, 0, Math.PI*2);
  g.fillStyle = DISC; g.fill();                      // 렌즈를 원판색으로 뚫는다
  g.beginPath(); g.arc(bx+2, 0,  5, 0, Math.PI*2);
  g.fillStyle = BLK; g.fill();
  g.restore();

  return c;
}
