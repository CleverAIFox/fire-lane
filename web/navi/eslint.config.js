// eslint.config.js — React 훅 규칙을 **실제로 돌린다**.  (DECISIONS §279-4)
//
// ★ 2026-09-28. 이 파일이 생기기 전까지 저장소에는 eslint 가 **하나도 없었다** —
//   설정도, 의존성도, 스크립트도. 그런데 `// eslint-disable-next-line
//   react-hooks/exhaustive-deps` 가 **28개** 있었다. 있지도 않은 검사를 억제하는
//   주석이고, 이 저장소가 「1족 — 무음 통과」라고 부르는 것의 교과서적 형태다.
//
// ★ 규칙을 **error 로** 켠다. warn 은 관문이 아니다 — 아무것도 안 막는다.
//   기존 억제 28개는 지우지 않는다(28개 훅을 오늘 고칠 수는 없다). 대신
//   `tools/suppress.py` 가 **양방향 래칫**으로 그 수를 붙든다 — 늘면 울고,
//   줄여도 기록을 안 내리면 운다. 규칙은 오늘부터 진짜고, 빚은 세어진다.
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**", "coverage/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  // ★ 2026-09-29 (§312). `scripts/` 는 **Node 에서 도는 빌드 도구**다.
  //   브라우저 전역만 아는 채로 보면 `console` · `process` 가 전부 미정의로 뜬다.
  //   규칙을 끄는 것이 아니라 **어디서 도는지를 적는 것**이다.
  {
    files: ["scripts/**/*.mjs", "*.config.{js,ts}"],
    languageOptions: { globals: { console: "readonly", process: "readonly" } },
  },
  // ★ 2026-09-29 (§312). 서비스 워커는 **브라우저도 Node 도 아닌 제3의 전역**에서
  //   돈다(`self` · `caches` · `clients`). 어디서 도는지를 적는 것이지 규칙을 끄는
  //   것이 아니다 — 여기서 `no-undef` 를 끄면 진짜 오타를 놓친다.
  {
    files: ["public/sw.js"],
    languageOptions: {
      globals: {
        self: "readonly", caches: "readonly", clients: "readonly",
        fetch: "readonly", location: "readonly", URL: "readonly", Response: "readonly",
      },
    },
  },
  {
    files: ["src/**/*.{ts,tsx}", "test/**/*.{ts,tsx}"],
    plugins: { "react-hooks": reactHooks },
    rules: {
      // ★ 28개 억제가 전부 이 규칙을 가리킨다. 이것이 이 설정의 이유다.
      "react-hooks/exhaustive-deps": "error",
      "react-hooks/rules-of-hooks": "error",
      // 타입 검사는 `tsc --noEmit` 이 든다 — 여기서 두 벌로 보지 않는다(R3).
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": [
        "error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
);
