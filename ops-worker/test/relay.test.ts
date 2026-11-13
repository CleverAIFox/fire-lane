/** ops-worker/test/relay.test.ts — 중개자의 순수 규칙(파이썬 `roster.py` 와 같은 표 + 마지막 한 통). `node --test` 로 돈다. */
import assert from "node:assert/strict";
import { test } from "node:test";
import { Cache, MAX_BUCKETS, MAX_BYTES, authOk, wants } from "../src/relay.ts";

test("누가 누구에게 — 관제는 차량 전부 · 차량은 관제만 · 영상은 둘 다 · 영상은 아무것도 안 받는다", () => {
  assert.deepEqual(wants("ops"), ["unit"]);
  assert.deepEqual(wants("unit"), ["ops"]);
  assert.deepEqual(wants("cv"), ["ops", "unit"]);
  for (const k of ["ops", "unit", "cv"] as const) assert.ok(!wants(k).includes("cv"), "영상이 받는 쪽에 들었다");
});

test("마지막 한 통은 글자 그대로 — 새로 붙은 관제가 차량 마지막 상태와 영상을 받는다", () => {
  const c = new Cache();
  c.put("unit", "A", '{"t":"state","n":1}'); c.put("unit", "A", '{"t":"state","n":2}'); c.put("unit", "B", "b");
  c.put("cv", "cam1", "w");
  assert.deepEqual(c.replayFor("ops"), ['{"t":"state","n":2}', "b", "w"]);   // A 는 마지막 것 하나
  assert.deepEqual(c.replayFor("unit"), ["w"]);                              // 차량은 영상만(차량끼리는 안 닿는다)
  assert.deepEqual(c.replayFor("cv"), []);
});

test("관제가 보낸 것은 기억하지 않는다(옛 hb 재생 방지)", () => {
  const c = new Cache();
  assert.equal(c.put("ops", "", '{"t":"hb"}'), false);
  assert.equal(c.size, 0);
});

test("차량이 떠나면 버킷이 빠진다 · 영상은 남는다", () => {
  const c = new Cache();
  c.put("unit", "A", "a"); c.put("cv", "cam1", "w");
  c.drop("unit", "A"); c.drop("cv", "cam1");
  assert.deepEqual(c.replayFor("ops"), ["w"]);
});

test("상한 — 큰 글은 안 두고 버킷은 상한까지만(옮기기는 호출부가 그대로 한다)", () => {
  const c = new Cache();
  assert.equal(c.put("unit", "A", "x".repeat(MAX_BYTES + 1)), false);
  for (let i = 0; i < MAX_BUCKETS; i++) assert.ok(c.put("unit", `u${i}`, "t"));
  assert.equal(c.put("unit", "new", "t"), false, "상한을 넘어 들였다");
  assert.equal(c.put("unit", "u0", "t2"), true, "이미 있는 버킷은 갱신된다");
});

test("글자를 해석하지 않는다 — 깨진 글도 그대로 재생된다", () => {
  const c = new Cache();
  c.put("unit", "A", "{깨진 json");
  assert.deepEqual(c.replayFor("ops"), ["{깨진 json"]);
});

test("인증 — 토큰이 맞아야 하고 비면 열린 선언이 있어야 한다", () => {
  assert.equal(authOk("abc", "abc", false), true);
  assert.equal(authOk("abd", "abc", false), false);
  assert.equal(authOk("ab", "abc", false), false);
  assert.equal(authOk(null, "abc", false), false);
  assert.equal(authOk(null, "", false), false);
  assert.equal(authOk(null, "", true), true);
});
