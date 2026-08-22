/* Fire-Lane · config.js 접근 지점
   ════════════════════════════════════════════════════════════
   config.js 는 UI 담당(@marscoolcat)의 파일이고 클래식 스크립트다.
   ★ 그 파일을 ES 모듈로 바꾸라고 요구하지 않는다 — 소유권이 다르고,
     바꾸면 UI 쪽 작업 흐름이 깨진다. 전역을 여기 한 곳에서만 읽어
     나머지 모듈은 전부 정상적인 import 로 쓴다.

   ★★ `window.CONFIG` 로 쓰면 안 된다 — undefined 다.
      config.js 는 `const CONFIG = {...}` 로 선언한다. 클래식 스크립트의
      최상위 const/let 은 전역 **선언적 환경**에 들어가고, 그것은
      window(전역 객체)의 프로퍼티가 되지 않는다. var 와 함수 선언만
      프로퍼티가 된다. 실측(node vm, 같은 컨텍스트):

          const CONFIG = {a:1};  var LEGACY = 2;
          typeof CONFIG             -> "object"
          typeof globalThis.CONFIG  -> "undefined"   ★
          typeof globalThis.LEGACY  -> "number"

      ES 모듈의 스코프 체인은 전역 선언적 환경까지 닿으므로 **이름으로**
      참조하면 보인다. 그래서 아래처럼 typeof 로 먼저 확인한다
      (선언되지 않은 이름에 typeof 를 쓰면 ReferenceError 가 안 난다).
      config.js 가 나중에 `var CONFIG` 나 `globalThis.CONFIG =` 로 바뀌어도
      아래 코드는 그대로 동작한다.
   ════════════════════════════════════════════════════════════ */
const _config =
  (typeof CONFIG !== "undefined") ? CONFIG :
  (typeof globalThis !== "undefined" && globalThis.CONFIG) ? globalThis.CONFIG :
  null;

if (!_config) {
  throw new Error(
    "CONFIG 가 없다. index.html 에서 config.js 가 js/main.js 보다 먼저 " +
    "로드되는지 확인할 것. (module 은 defer 처럼 동작하므로 클래식 " +
    "스크립트가 항상 먼저 실행된다 — 순서가 맞다면 config.js 자체를 볼 것)");
}

export { _config as CONFIG };
