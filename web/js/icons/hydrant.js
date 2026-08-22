/* Fire-Lane · 표지판 아이콘 — 소화전 표지
   ────────────────────────────────────────────────────────────
   ★ app.js 에서 잘라낸 원문이다. 캔버스 좌표 하나 안 건드렸다.
     이 파일들은 순수 함수다 — map 도 CONFIG 도 모른다(cctv 제외).
     그래서 브라우저 없이도 눈으로 대조할 수 있고, 아이콘을 고칠 때
     지도 로직을 읽지 않아도 된다.
   ──────────────────────────────────────────────────────────── */

import { SIGN_PX } from "./size.js";

export function makeHydrantImage(){
  const W = SIGN_PX, c = document.createElement("canvas");
  c.width = c.height = W;
  const g = c.getContext("2d");
  const RED = "#e2221c";

  /* 빨간 원판 + 흰 테두리 */
  g.beginPath(); g.arc(W/2, W/2, 84, 0, Math.PI*2);
  g.fillStyle = RED; g.fill();
  g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();

  /* 소화전 픽토그램 — 흰색.
     선까지 흰색으로 두면 몸통·플랜지·방수구가 한 덩어리로 뭉친다.
     그래서 테두리는 배경과 같은 빨강으로 그어 형태를 갈라 놓는다. */
  g.fillStyle = "#ffffff"; g.strokeStyle = RED;
  g.lineWidth = 5; g.lineJoin = "round";
  const box = (x,y,w,h,r=3)=>{ g.beginPath();
    g.moveTo(x+r,y); g.arcTo(x+w,y,x+w,y+h,r); g.arcTo(x+w,y+h,x,y+h,r);
    g.arcTo(x,y+h,x,y,r); g.arcTo(x,y,x+w,y,r); g.closePath(); g.fill(); g.stroke(); };

  box(52, 92, 15, 20, 3);          // 좌측 방수구
  box(125,92, 15, 20, 3);          // 우측 방수구
  box(58, 136, 76, 15, 4);         // 베이스 플랜지
  g.beginPath();                   // 몸통 + 돔
  g.moveTo(72, 136); g.lineTo(72, 70);
  g.arc(96, 70, 24, Math.PI, 0);
  g.lineTo(120, 136); g.closePath();
  g.fill(); g.stroke();
  box(60, 60, 72, 13, 3);          // 어깨 플랜지
  box(89, 30, 14, 12, 3);          // 상단 캡
  g.beginPath();                   // 중앙 밸브 — 빨강으로 반전
  g.arc(96, 104, 13, 0, Math.PI*2);
  g.fillStyle = RED; g.fill();
  g.strokeStyle = "#ffffff"; g.lineWidth = 4; g.stroke();

  return c;
}
