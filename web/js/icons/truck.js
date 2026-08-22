/* Fire-Lane · 표지판 아이콘 — 소방차(사다리차) 표지
   ────────────────────────────────────────────────────────────
   ★ app.js 에서 잘라낸 원문이다. 캔버스 좌표 하나 안 건드렸다.
     이 파일들은 순수 함수다 — map 도 CONFIG 도 모른다(cctv 제외).
     그래서 브라우저 없이도 눈으로 대조할 수 있고, 아이콘을 고칠 때
     지도 로직을 읽지 않아도 된다.
   ──────────────────────────────────────────────────────────── */

import { SIGN_PX } from "./size.js";

export function makeTruckImage(){
  const W = SIGN_PX, c = document.createElement("canvas");
  c.width = c.height = W;
  const g = c.getContext("2d");
  const RED = "#e2221c";

  /* 빨간 둥근 사각 판 + 흰 테두리.
     소화전 간판은 '원'이라 멀리서도 형태만으로 둘이 구분된다. */
  const r = 30, pad = 10;
  g.beginPath();
  g.moveTo(pad+r, pad);
  g.arcTo(W-pad, pad,   W-pad, W-pad, r); g.arcTo(W-pad, W-pad, pad, W-pad, r);
  g.arcTo(pad,   W-pad, pad,   pad,   r); g.arcTo(pad,   pad,   W-pad, pad,   r);
  g.closePath();
  g.fillStyle = RED; g.fill();
  g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();

  /* 소방차(사다리차) 픽토그램 — 흰색.
     칸을 나누는 선은 배경과 같은 빨강으로 그어야 덩어리로 안 뭉친다. */
  g.fillStyle = "#ffffff";
  const box = (x,y,w,h,rr=4)=>{ g.beginPath();
    g.moveTo(x+rr,y); g.arcTo(x+w,y,x+w,y+h,rr); g.arcTo(x+w,y+h,x,y+h,rr);
    g.arcTo(x,y+h,x,y,rr); g.arcTo(x,y,x+w,y,rr); g.closePath(); g.fill(); };

  /* 사다리 — 기울여 얹는다 */
  g.save();
  g.translate(70, 60); g.rotate(-0.33);
  box(-44, -7, 88, 14, 4);
  g.fillStyle = RED;
  [-33,-19,-5,9,23].forEach(x => g.fillRect(x, -7, 4, 14));
  g.restore();

  g.fillStyle = "#ffffff";
  box(28, 82, 84, 46, 5);          // 적재함
  box(112, 74, 48, 54, 6);         // 운전석
  box(126, 62, 16, 10, 3);         // 경광등
  g.strokeStyle = "#ffffff"; g.lineWidth = 5; g.lineCap = "round";
  [[134,58,134,44],[124,60,116,50],[144,60,152,50]].forEach(([a,b,cc,d])=>{
    g.beginPath(); g.moveTo(a,b); g.lineTo(cc,d); g.stroke(); });

  g.fillStyle = RED;               // 창문 · 적재함 칸막이
  box(121, 82, 28, 24, 4);
  [46, 64, 82].forEach(x => g.fillRect(x, 100, 14, 5));

  [[58,128],[136,128]].forEach(([x,y])=>{        // 바퀴
    g.beginPath(); g.arc(x, y, 17, 0, Math.PI*2); g.fillStyle="#ffffff"; g.fill();
    g.beginPath(); g.arc(x, y,  7, 0, Math.PI*2); g.fillStyle=RED;       g.fill(); });

  return c;                      // 캔버스를 돌려준다 — 지도와 범례가 같이 쓴다
}
