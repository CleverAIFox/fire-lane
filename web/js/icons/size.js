/* 표지판 아이콘 원본 크기(px).
   ★ 확대해도 안 뭉개지게 크게 굽는다.
   ★ 여기가 정본이다. layers/signs.js 의 bake() 가 이 값으로
     getImageData(0,0,SIGN_PX,SIGN_PX) 를 한다 — 아이콘이 다른 크기로
     그려지면 잘리거나 여백이 붙는다. 원본 app.js 에서는 같은 스코프의
     지역 상수였고, hydrant 만 192 를 손으로 박아 쓰고 있었다(같은 값이라
     드러나지 않았을 뿐 갈라지면 조용히 깨지는 자리다). */
export const SIGN_PX = 192;
