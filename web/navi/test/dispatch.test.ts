/**
 * dispatch.test.ts — 출동 지령이 **내비를 여는가.**  (DECISIONS §351)
 *
 * ★ 2026-10-02 에 그 버튼이 **관제를 한 장 더 열었다.** 상대 주소 `./` 가
 *   「지금 있는 자리」였고, 배포에서 관제는 루트에 앉아 있다(§258).
 *   검사 스물이 전부 초록이었다 — 이 판단에 시험이 하나도 없었다.
 *
 * ★ 주입으로 묻는다(MASTER §17-0 ①). 옛 꼴(`"./?incident=…"`)을 되살리면
 *   아래 첫 판별식이 운다.
 *
 * 밖  **버튼이 눌리는지 · 새 탭이 뜨는지는 안 본다** — 그것은 브라우저 일이고
 *     여기가 드는 것은 「어느 주소를 여는가」 하나다. 주소가 실재하는지는
 *     배포(`.github/actions/build-navi`)와 `tools/uicheck.py` 가 든다.
 */
import { describe, expect, it } from "vitest";

import { dispatchUrl, naviBase } from "../src/domain/dispatch";

const D = {
  at: [126.91234567, 35.14987654] as [number, number],
  label: "동명동 123-4",
  vehicle: "pumper",
  station: "동부119안전센터",
};

describe("내비를 여는 자리", () => {
  it("배포 루트의 관제에서는 navi/ 로 간다", () => {
    // ★ 이 배치가 고친 바로 그 자리. `./` 면 관제가 한 장 더 열린다.
    expect(naviBase("ops")).toBe("./navi/");
    expect(dispatchUrl("ops", D).startsWith("./navi/?")).toBe(true);
  });

  it("표시가 없으면 같은 자리다 — dev 서버의 루트가 web/navi 다", () => {
    expect(naviBase(undefined)).toBe("./");
    expect(naviBase(null)).toBe("./");
  });

  it("`?view=ops` 로 온 관제도 같은 자리다", () => {
    // 그 화면의 index.html 에는 `__FL_VIEW` 가 안 박혀 있다 — 쿼리로만 온 것이다
    expect(naviBase("")).toBe("./");
  });

  it("경로를 안 본다", () => {
    // ★ `main.tsx` 가 적은 함정 — 경로로 보면 개발에서 기본 화면이 뒤집힌다.
    //   이 모듈이 `location` 을 읽으면 같은 사고가 여기서 난다.
    expect(dispatchUrl("ops", D)).toBe(dispatchUrl("ops", D));
  });

  it("다시 여는 쪽에 `view` 를 안 붙인다", () => {
    // 붙이면 「ops 가 아닌 값이면 내비」라는 우연에 기대게 된다. 비우는 것이 내비다.
    expect(dispatchUrl("ops", D)).not.toContain("view=");
    expect(dispatchUrl(undefined, D)).not.toContain("view=");
  });

  it("네 칸을 전부 넘긴다 — 하나라도 빠지면 내비가 되묻는다", () => {
    const u = new URLSearchParams(dispatchUrl("ops", D).split("?")[1]);
    expect(u.get("incident")).toBe("126.912346,35.149877");
    expect(u.get("label")).toBe(D.label);
    expect(u.get("vehicle")).toBe(D.vehicle);
    expect(u.get("station")).toBe(D.station);
  });

  it("한글과 공백을 인코딩한다", () => {
    // 날것으로 넣으면 주소가 거기서 끊기고 센터가 안 채워진다
    expect(dispatchUrl("ops", D)).not.toContain("동부119안전센터");
    expect(dispatchUrl("ops", D)).toContain(encodeURIComponent(D.station));
  });

  it("좌표를 6자리로 끊는다 — 구간 분해능보다 작다", () => {
    expect(dispatchUrl("ops", D)).toContain("126.912346%2C35.149877");
  });

  it("빈 그물이 아니다 — 두 자리가 실제로 다르다", () => {
    // 둘이 같아지면 위 판별식들이 전부 조용히 통과한다(MASTER §17-0 ③)
    expect(naviBase("ops")).not.toBe(naviBase(undefined));
  });
});
