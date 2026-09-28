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
