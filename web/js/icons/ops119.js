/* Fire-Lane · 표지판 아이콘 — 119 상황실 요원 표지
   ────────────────────────────────────────────────────────────
   ★ app.js 에서 잘라낸 원문이다. 캔버스 좌표 하나 안 건드렸다.
     이 파일들은 순수 함수다 — map 도 CONFIG 도 모른다(cctv 제외).
     그래서 브라우저 없이도 눈으로 대조할 수 있고, 아이콘을 고칠 때
     지도 로직을 읽지 않아도 된다.
   ──────────────────────────────────────────────────────────── */

import { SIGN_PX } from "./size.js";

export function make119Image(){
  const W = SIGN_PX, c = document.createElement("canvas");
  c.width = c.height = W;
  const g = c.getContext("2d");
  const RED = "#e2221c";

  /* 판 모양·색은 안전센터와 같게 간다. 안의 그림으로만 구분한다. */
  const r = 30, pad = 10;
  g.beginPath();
  g.moveTo(pad+r, pad);
  g.arcTo(W-pad, pad,   W-pad, W-pad, r); g.arcTo(W-pad, W-pad, pad, W-pad, r);
  g.arcTo(pad,   W-pad, pad,   pad,   r); g.arcTo(pad,   pad,   W-pad, pad,   r);
  g.closePath();
  g.fillStyle = RED; g.fill();
  g.lineWidth = 9; g.strokeStyle = "#ffffff"; g.stroke();

  /* 헤드셋 쓴 상황실 요원 — 흰색.
     ★ 그리는 순서가 중요하다. 헤드밴드·마이크를 먼저 깔고 머리·어깨를 나중에
       덮어야 밴드가 머리 뒤로 지나가는 것처럼 보인다.
     ★ 칸을 나누는 선은 배경과 같은 빨강으로 긋는다. 전부 흰색이면 뭉친다. */
  g.lineJoin = "round"; g.lineCap = "round";

  g.beginPath();                       // 헤드밴드(머리 위 아치)
  g.arc(96, 86, 40, Math.PI, 2*Math.PI);
  g.strokeStyle = "#ffffff"; g.lineWidth = 11; g.stroke();

  g.beginPath();                       // 마이크 붐
  g.moveTo(133, 104); g.quadraticCurveTo(130, 128, 108, 132);
  g.strokeStyle = "#ffffff"; g.lineWidth = 8; g.stroke();
  g.beginPath(); g.arc(104, 133, 8, 0, Math.PI*2);
  g.fillStyle = "#ffffff"; g.fill();

  const cup = (x)=>{ g.beginPath();    // 좌·우 이어컵
    g.moveTo(x+6, 74); g.arcTo(x+18, 74, x+18, 104, 6);
    g.arcTo(x+18, 104, x, 104, 6); g.arcTo(x, 104, x, 74, 6);
    g.arcTo(x, 74, x+18, 74, 6); g.closePath();
    g.fillStyle = "#ffffff"; g.fill();
    g.strokeStyle = RED; g.lineWidth = 5; g.stroke(); };
  cup(50); cup(124);

  g.beginPath();                       // 머리
  g.arc(96, 86, 26, 0, Math.PI*2);
  g.fillStyle = "#ffffff"; g.fill();
  g.strokeStyle = RED; g.lineWidth = 5; g.stroke();

  g.beginPath();                       // 어깨(반원 몸통)
  g.arc(96, 162, 40, Math.PI, 2*Math.PI); g.closePath();
  g.fillStyle = "#ffffff"; g.fill();
  g.strokeStyle = RED; g.lineWidth = 5; g.stroke();

  return c;
}
