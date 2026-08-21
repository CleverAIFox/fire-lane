/* DOM 헬퍼.
   ★ 없는 요소를 참조하면 거기서 죽고 그 뒤 코드가 전부 안 돈다.
     더미를 돌려주고 콘솔에 남긴다. 화면 일부가 비는 건 봐도 알지만
     지도 절반이 안 뜨는 건 원인 찾기가 어렵다. (원본 app.js 주석 그대로) */
export const $ = sel => document.querySelector(sel) || (
  console.warn("DOM 없음:", sel), {style:{}, classList:{toggle(){},add(){},remove(){}},
                                   set textContent(v){}, set innerHTML(v){}});
