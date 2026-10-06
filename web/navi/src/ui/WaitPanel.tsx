/**
 * ui/WaitPanel.tsx — **출동 대기.** 지령이 오기 전 운전석 화면.  (DECISIONS §400)
 *
 * ★ 종전에 이 자리에는 「출동 정보 입력」이 있었다 — 센터를 고르고, 목적지를
 *   검색하고, 출발·도착을 뒤집는 판이다. 사람이 그 전제를 잘랐다:
 *
 *       「내비가 스스로 고를 수 있는건 없다」
 *
 *   그래서 이 판에는 **버튼이 하나도 없다.** 받은 것을 적고 기다린다.
 *
 * ★ **빈 칸을 숨기지 않는다.** 차량이 안 왔으면 「—」가 보인다. 숨기면 기사가
 *   「원래 안 나오는 칸」으로 읽고, 지령이 반쯤 온 상태를 알아챌 길이 없다.
 *
 * IN    센터 이름 · 차량 이름 · 사건 이름 (전부 지령에서 온다)
 * OUT   화면
 * 밖    **아무것도 안 바꾼다.** 설정자를 안 받는다 — 받을 수 있으면 언젠가 받는다.
 */
import { Sheet } from "./Sheet";
import { C } from "./tokens";

const row: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline",
  padding: "10px 0", borderBottom: `1px solid ${C.sheetLine}`,
};
const k: React.CSSProperties = { fontSize: 12, color: C.panelSub, letterSpacing: .4 };
const v: React.CSSProperties = { fontSize: 15, fontWeight: 800 };

export function WaitPanel(
  { station, vehicle, incident }:
  { station: string | null; vehicle: string | null; incident: string | null },
) {
  const ready = !!(station && vehicle && incident);
  return (
    <Sheet wf="00">
      <div style={{ fontSize: 17, fontWeight: 900, marginBottom: 2 }}>
        {ready ? "경로를 내는 중" : "출동 지령 대기"}
      </div>
      <div style={{ fontSize: 12, color: C.panelSub, marginBottom: 10 }}>
        {ready
          ? "관제가 보낸 지령으로 경로를 낸다."
          : "관제가 지령을 보내면 여기에 뜬다. 운전석에서 고를 것은 없다."}
      </div>
      <div style={row}><span style={k}>사건</span><span style={v}>{incident ?? "—"}</span></div>
      <div style={row}><span style={k}>출발</span><span style={v}>{station ?? "—"}</span></div>
      <div style={{ ...row, borderBottom: "none" }}>
        <span style={k}>차량</span><span style={v}>{vehicle ?? "—"}</span>
      </div>
    </Sheet>
  );
}
