/**
 * ui/DispatchPanel.tsx — 출동 정보 입력.  (와이어프레임 00)
 *
 * ★ 출발지는 **안전센터**다. 출동은 센터에서 나간다(`seg/params.py::STATIONS`).
 *   09-05 판은 출발지를 현위치(GPS)로 두었는데, 관제·출동 흐름에서 차량은
 *   센터 차고에 서 있다. 현위치는 주행 중 위치에 쓴다.
 *
 * ★ 사건 위치는 원래 **119 접수 시스템**이 넘긴다. 그 연동이 아직 없어서
 *   검색·지도 선택·URL(`?incident=경도,위도&label=…`)로 받는다. URL 은 접수
 *   시스템이 붙을 자리다.
 *
 * ★ 2026-10-04 (DECISIONS §393). **바꾸는 손이 `edit` 하나로 묶였다.**
 *   `edit` 이 `null` 이면 지령이 온 것이고, 이 판은 바꾸는 버튼을 **안 그린다**
 *   — 묶는 것이 아니라 없다. 종전에는 핸들러만 빈 함수로 바꿔서 버튼이
 *   그대로 보였고, 운전석에서 눌러도 말이 없었다.
 */
import type { CSSProperties } from "react";
import { C, F } from "./tokens";
import { Cta, Sheet, SmallBtn } from "./Sheet";
import { Flame } from "./icons";

export interface StationOpt { id: string; name: string; addr: string }

/**
 * **경로 지점을 바꾸는 손 전부.** 지령이 왔으면 이 묶음이 통째로 `null` 이고,
 * 그러면 아래 판에 바꾸는 버튼이 하나도 안 그려진다. 넷을 따로 두면
 * 하나를 묶는 것을 잊는다 — `onSwap` 이 실제로 그랬다(§393).
 */
export interface EditHands {
  onStation: (id: string) => void;
  onArm: (w: "origin" | "dest" | null) => void;
  onSearch: () => void;
  onSwap: () => void;
}

interface Props {
  station: StationOpt | null;
  stations: StationOpt[];
  incidentLabel: string | null;
  incidentSub: string | null;
  incidentAt: string | null;
  armed: "origin" | "dest" | null;
  /** `null` 이면 관제 지령이다 — 기사는 경로 지점을 **안 고른다** */
  edit: EditHands | null;
  onNext: () => void;
  canNext: boolean;
}

export function DispatchPanel(p: Props) {
  const e = p.edit;
  const nextStation = e && (() => {
    if (!p.stations.length) return;
    const i = p.stations.findIndex((s) => s.id === p.station?.id);
    e.onStation(p.stations[(i + 1) % p.stations.length].id);
  });
  return (
    <Sheet wf="00" footer={<Cta onClick={p.onNext} disabled={!p.canNext}>출동 차량 선택</Cta>}>
      <div style={{ fontSize: 22, fontWeight: 800 }}>
        {e ? "출발지와 도착지를 입력하세요" : "관제 지령을 받았습니다"}
      </div>
      <div style={{ fontSize: 13, color: C.panelSub, marginTop: 4 }}>
        {e ? "위치를 확인한 뒤 출동 차량을 선택합니다."
           : "경로 지점은 관제가 정합니다. 차량만 선택하세요."}
      </div>

      <div style={box}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <b style={{ fontSize: 14 }}>경로 지점</b>
          {e && <SmallBtn onClick={e.onSwap}>⇅ 출발·도착 바꾸기</SmallBtn>}
        </div>

        <Row kind="출발" color={C.station} title="출발지"
             name={p.station?.name ?? (e ? "안전센터를 고르세요" : "관제가 지정하지 않았습니다")}
             sub={p.station?.addr ?? ""}
             onChange={nextStation || null} armed={p.armed === "origin"} />
        <Row kind="도착" color={C.station} title="도착지" outline
             name={p.incidentLabel ?? (e ? "사건 위치를 입력하세요" : "관제가 지정하지 않았습니다")}
             sub={p.incidentLabel ? "사건 접수 위치"
                  : (e ? "검색하거나 지도에서 고릅니다" : "")}
             onChange={e ? e.onSearch : null} armed={p.armed === "dest"} />

        {e && (
          <button onClick={() => e.onArm(p.armed === "dest" ? null : "dest")}
                  style={{ ...mapPick, background: p.armed ? C.softBlue : "#fff" }}>
            ⌖ {p.armed ? "지도를 눌러 사건 위치를 찍으세요" : "지도에서 직접 선택"}
          </button>
        )}
      </div>

      {p.incidentLabel && (
        <div style={incident}>
          <div style={flame}><Flame size={22} /></div>
          <div>
            <div style={{ fontSize: 12, color: C.danger, fontWeight: 800 }}>사건 접수 위치</div>
            <div style={{ fontSize: 17, fontWeight: 800, marginTop: 2 }}>{p.incidentLabel}</div>
            <div style={{ fontSize: 12, color: C.panelSub, marginTop: 2 }}>
              화재 출동{p.incidentAt ? ` · 사건 접수 ${p.incidentAt}` : ""}
              {p.incidentSub ? ` · ${p.incidentSub}` : ""}
            </div>
          </div>
        </div>
      )}

      <div style={note}>
        {e ? "출발지와 도착지를 확인하면 다음 단계에서 차량별 통행 가능 경로를 계산합니다."
           : "경로 지점을 바꾸려면 관제에 요청하세요. 출동 기록은 관제가 남깁니다."}
      </div>
    </Sheet>
  );
}

/** `onChange` 가 `null` 이면 **「위치 변경」 버튼이 없다** — 묶인 것이 아니라 없다. */
function Row({ kind, color, title, name, sub, onChange, outline, armed }: {
  kind: string; color: string; title: string; name: string; sub: string;
  onChange: (() => void) | null; outline?: boolean; armed?: boolean;
}) {
  return (
    <div style={{ ...row, borderColor: armed ? C.cta : C.sheetLine }}>
      <div style={{ ...dot, background: outline ? "#fff" : color, color: outline ? color : "#fff",
                    border: `2px solid ${color}` }}>{kind}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 11, color: C.panelSub }}>{title}</div>
        <div style={{ fontSize: 16, fontWeight: 800, whiteSpace: "nowrap", overflow: "hidden",
                      textOverflow: "ellipsis" }}>{name}</div>
        {sub && <div style={{ fontSize: 11, color: C.panelSub }}>{sub}</div>}
      </div>
      {onChange && <SmallBtn onClick={onChange}>위치 변경</SmallBtn>}
    </div>
  );
}

const box: CSSProperties = {
  marginTop: 18, border: `1px solid ${C.sheetLine}`, borderRadius: 14, padding: 14,
  display: "flex", flexDirection: "column", gap: 10,
};
const row: CSSProperties = {
  display: "flex", alignItems: "center", gap: 12, border: "1.5px solid",
  borderRadius: 12, padding: "10px 12px",
};
const dot: CSSProperties = {
  width: 40, height: 40, borderRadius: 999, display: "grid", placeItems: "center",
  fontSize: 11, fontWeight: 800, flex: "0 0 auto",
};
const mapPick: CSSProperties = {
  border: `1.5px solid ${C.cta}`, borderRadius: 10, padding: "10px 0", color: C.cta,
  fontWeight: 800, fontSize: 14, cursor: "pointer", fontFamily: F.family,
};
const incident: CSSProperties = {
  marginTop: 14, border: `1px solid ${C.sheetLine}`, borderRadius: 14, padding: 14,
  display: "flex", gap: 12, alignItems: "center",
};
const flame: CSSProperties = {
  width: 40, height: 40, borderRadius: 999, background: "#fdecec", display: "grid",
  placeItems: "center", fontSize: 20,
};
const note: CSSProperties = {
  marginTop: 14, background: C.softBlue, borderRadius: 10, padding: "10px 12px",
  fontSize: 12, color: "#334155", lineHeight: 1.5,
};
