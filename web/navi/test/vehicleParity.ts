/**
 * test/vehicleParity.ts — 차량 통과 규칙 TS 판을 **격자로 불러 주는 자리**.
 *
 * ★ 2026-09-25 (PLAN §1 #126). 차량 통과 규칙(내륜차 · 필요폭 · 회전가부)이
 *   `src/firelane/seg/vehicle.py` 와 `src/domain/vehicle.ts` 두 구현으로 산다.
 *   **지금까지 아무도 알고리즘 동치를 안 봤다** — 강제자
 *   (`tests/test_sources_of_truth.py`)가 보는 것은 `OFFTRACK_MIN` 상수가 두
 *   파일에 같은 글자로 있는가 뿐이고, 한쪽 계산식을 고쳐도 아무도 안 운다.
 *
 * 이 파일은 **판정을 안 한다.** 같은 입력 격자를 TS 판에 먹여 결과를 돌려주는
 * 순수 함수 하나만 든다. 대조는 `tests/test_vehicle_parity.py` 가 하고,
 * 격자도 그쪽이 만든다 — 격자가 두 벌이면 그 둘이 갈리는 날이 오고,
 * 그러면 이 차분 시험이 정확히 이 파일이 막으려는 결함을 제 몸에 갖는다.
 *
 * ── 왜 입출력이 없나 ────────────────────────────────────────────
 * `node:fs` · `process` 를 쓰지 않는다. `@types/node` 를 더하지 않으려는
 * 것이고(`test/layering.test.ts` 와 같은 이유), 계층으로도 이쪽이 맞다 —
 * 표준입출력 배선은 파이썬이 만드는 glue 가 들고 여기는 **순수**로 남는다.
 * 그 대신 `npx tsc --noEmit` 이 이 파일을 본다. TS 쪽 함수 서명이 바뀌면
 * 대조가 돌기 전에 타입에서 걸린다.
 *
 * ── 왜 구현을 인자로 받나 ───────────────────────────────────────
 * ★ `domain/vehicle` 을 **값으로 import 하지 않는다.** node 가 `.ts` 를 그대로
 *   먹기는 하지만 확장자 없는 명세(`../src/domain/vehicle`)는 못 찾는다 —
 *   그것을 해결하는 것은 번들러(vite)이고 node 가 아니다. `.ts` 를 붙이면
 *   `tsc` 가 `allowImportingTsExtensions` 를 요구하므로 tsconfig 을 건드려야
 *   한다. 그래서 **타입만 import 하고**(타입 import 는 지워진다) 구현은
 *   glue 가 넣어 준다. 타입 대조는 그대로 남는다 — `runCases` 가 받는 것이
 *   `typeof import("../src/domain/vehicle")` 이므로 저쪽 서명이 바뀌면
 *   `npx tsc --noEmit` 이 여기서 운다.
 *
 * ── 부호화 ──────────────────────────────────────────────────────
 * JSON 은 `Infinity` · `NaN` 을 못 싣는다(`JSON.stringify(Infinity)` 는
 * `null` 이다 — 못 간다는 판정이 조용히 「값 없음」이 된다). 그래서 유한하지
 * 않은 수는 글자로 바꿔 보낸다. 파이썬 쪽이 같은 글자를 쓴다.
 *
 * 밖    **어느 쪽이 옳은지는 안 본다.** 두 판이 다르다는 것까지만 낸다 —
 *       식을 고치는 것은 사람의 몫이다(PLAN §1 #126 은 「파트 간 합의」다).
 *       그리고 `edgeCost` 의 `TUNING.avoidUncertain` 은 `edgeCost` 가 안
 *       쓰므로 여기서도 안 본다(`domain/graph.ts` 소관).
 */
import type * as Vehicle from "../src/domain/vehicle";
import type { VehicleSpec, Verdict } from "../src/domain/types";

/** 대조하는 구현. glue 가 `domain/vehicle.ts` 를 그대로 넣는다. */
export type VehicleApi = typeof Vehicle;

/** 유한하지 않은 수와 예외는 글자로 나간다. 파이썬이 같은 글자를 쓴다. */
export type Encoded = number | boolean | string;

/** 격자 한 칸. `spec` 은 `payload.specs` 의 색인이다(제원을 사례마다 싣지 않는다). */
export interface ParityCase {
  fn: "offtracking" | "requiredWidth" | "canTurn" | "edgeCost";
  spec: number;
  radius_m?: number | null;
  length_m?: number | null;
  width_m?: number | null;
  verdict?: Verdict | null;
  lenient?: boolean;
}

export interface ParityPayload {
  specs: VehicleSpec[];
  cases: ParityCase[];
}

/** 유한하지 않은 수를 글자로. `-0` 은 `0` 과 같게 본다(폭·반경에 부호 0 은 뜻이 없다). */
function enc(x: number): Encoded {
  if (Number.isNaN(x)) return "nan";
  if (x === Infinity) return "inf";
  if (x === -Infinity) return "-inf";
  return x === 0 ? 0 : x;
}

function one(v: VehicleApi, c: ParityCase, spec: VehicleSpec): Encoded {
  switch (c.fn) {
    case "offtracking":
      return enc(v.offtracking(spec, c.radius_m));
    case "requiredWidth":
      return enc(v.requiredWidth(spec, c.radius_m));
    case "canTurn":
      return v.canTurn(spec, c.radius_m);
    case "edgeCost":
      return enc(v.edgeCost(
        spec, c.length_m ?? null, c.width_m ?? null, c.verdict, c.radius_m, c.lenient ?? false));
  }
}

/**
 * 격자를 TS 판에 먹인다. 사례 순서 그대로 결과를 낸다.
 *
 * ★ 던지는 것도 결과다. 한쪽이 죽고 한쪽이 답을 내면 그것이 곧 불일치이므로
 *   `throw:<이름>` 으로 부호화해 보낸다 — 여기서 삼키면 차이가 안 보인다.
 */
export function runCases(v: VehicleApi, payload: ParityPayload): Encoded[] {
  return payload.cases.map((c) => {
    const spec = payload.specs[c.spec];
    if (!spec) return "throw:no-spec";
    try {
      return one(v, c, spec);
    } catch (e) {
      return `throw:${e instanceof Error ? e.constructor.name : typeof e}`;
    }
  });
}
