/* Fire-Lane · 설정 계층
   ─────────────────────────────────────────────────────────────
   ★ 2026-09-22. 이 파일을 싣던 옛 GIS 지도(index.html · js/ · style.css)를 걷어냈다.
     지금은 **파이프라인 설정**이다 — 화면(web/navi)은 이 파일을 직접 안 싣는다.
       publish_navi.py   verdict(색 · 라벨 · 설명) · terrain  → navi_graph.json.style · .terrain
       publish_fleet.py  fleet(관내 편성)                     → fleet.json
       시험              params 사본(test_declaration_sync) · reason 표(test_contract)
   ★ 2026-09-22 (DECISIONS §218-6) 옛 지도만 읽던 블록을 지웠다 — vworld · cctvCov ·
     lightTint · chrome · markers · camera · scope · dispatch · minimap · layers · poles ·
     poi · vehicleProfiles · vehicleSpec · vehicleClearance · turnNote. src · tools · tests ·
     web/navi · .github 어디서도 읽지 않았다(grep). 지운 뒤 publish_navi · publish_fleet 를
     다시 돌려 navi_graph.json · fleet.json 이 바이트 그대로임을 확인했다.
     남긴 것 중 fleetGroups · fleetDefault · fleetSource 는 코드가 안 읽는다. 앞의 둘은
     sources.yaml 서술이 `CONFIG.fleetDefault` · `CONFIG.fleetGroups` 로 가리키고, 뒤의 것은
     공공누리 출처 문구라 옮길 자리를 정하기 전까지 둔다.
   ★ 블록 끝을 정규식이 잡는다 — verdict 는 첫 `\n  },`, fleet 는 첫 `\n  ],` 까지다.
     블록 안에 그 모양을 끼우지 말 것. 다른 파일에 같은 값을 복사하지 말 것.

   ★ 임계값(3.0 / 7.0 / 25.0)은 산출 파이프라인의 값과 반드시 같아야 한다.
     정본은 src/firelane/seg/params.py 다. 여기 값은 화면 설명용 사본이며,
     바꿔도 판정 결과는 안 바뀐다. 파이프라인을 먼저 고치고 여기를 맞출 것.
   ───────────────────────────────────────────────────────────── */

const CONFIG = {

  /* 판정 색상. style.css 의 --blocked 등과 같은 값을 유지할 것.
     ★ color = 다크 모드용, lightColor = 라이트 모드용.
       다크용 색은 검은 배경에 올리려고 밝고 채도 높게 고른 것이다. 흰 배경에
       그대로 쓰면 '밝은 것 위의 밝은 것'이 되어 대비는 떨어지고 채도만 남아
       눈이 아프다.
     ★ 그렇다고 style.css 의 패널용 색(#0f8a55 등)을 그대로 가져오면 안 된다.
       그건 작은 글씨용이라, 화면 절반을 덮는 굵은 도로선에 쓰면 너무 무겁고
       주황·회색은 지면에 묻혀 4색이 사실상 1색이 된다(2025-08 실패 사례).
       아래 값은 배경을 #dfe3ea 로 낮춘 상태에서 네 색이 모두 대비 2.4~3.5,
       색상(hue)도 서로 충분히 떨어지도록 다시 고른 것이다. */
  verdict: {
    blocked : { color:[255, 77, 61], lightColor:[224, 53, 38], label:"통행 불가",
                desc:"벽 사이 폭 3.0m 미만. 주차 차량이 없어도 소방차가 못 지나간다" },
    needs_cv: { color:[255,171, 46], lightColor:[212,124, 10], label:"판정 보류",
                desc:"도면만으로 결론이 안 난다. 영상판정(호모그래피) 대상" },
    clear   : { color:[ 74,209,143], lightColor:[ 26,150, 96], label:"통행 가능",
                desc:"도로 폭 7.0m 이상. 양쪽에 주차가 있어도 통과. 영상판정 불필요" },
    unknown : { color:[ 90, 98,114], lightColor:[110,120,138], label:"영상판정 불가",
                desc:"CCTV 유효범위 25m 밖. 영상판정 자체가 성립하지 않는다" },
  },

  /* noCctvColor(갈색)는 제거했다. 화면 색은 verdict 4종이 전부다.
     CCTV 사각 구간은 unknown(회색)에 그대로 포함된다 — 회색의 정의가 곧
     "CCTV 없음 / 25m 밖"이기 때문이다. 되살리지 말 것. */

  /* 회색(unknown)의 사유. 2026-08-22 에 넷으로 쪼갰다.
     종전에는 352구간이 전부 no_cctv 하나여서, 화면이 "왜 회색인가" 를
     설명하지 못했다. 판정과 색은 그대로다 — 문구만 정확해진다.
     ★ 정본은 segments.py 다. 여기 없는 키가 오면 툴팁이 빈칸이 된다. */
  reason: {
    no_cctv_narrow: "노면 3m 미만 · 도로대장도 3m 미만 · 담 사이는 여유 있음",
    no_cctv_thin  : "노면 3m 미만 · 대장폭은 3m 이상 — 근거 하나뿐",
    no_cctv_band  : "3~7m 대역 · 주정차 여부로 갈림 · CCTV 25m 밖",
    no_cctv_single: "7m 이상이나 표본 부족으로 통과 확정 보류",
    /* 옛 키. 재발행 전 산출물을 열었을 때를 위해 남긴다. */
    no_cctv: "CCTV 유효범위 25m 밖 · 영상판정 불가",
    width  : "실폭도로·건물 폴리곤 부재 · 폭 산출 불가",
  },

  /* ── 기준 차량 — 동명동 관할 보유 차량 ────────────────────────
     publish_fleet.py 가 이 배열을 정규식으로 읽어 fleet.json 을 낸다(내비 VehiclePicker 가 읽는다).

   ★ 여기는 "무엇을 띄우는가"만 적는다. 제원(전폭·회전반경)의 정본은
     web/assets/vehicles/profiles.json 이고 vehicle.js 가 그 파일을
     fetch 해서 profile 키로 붙인다. 숫자를 여기 복사하지 말 것 —
     실측으로 교체될 때 두 곳이 갈라진다.

   ★ **동명동은 지산119안전센터 관할이다.** 대인이 아니다.
     「전남광주통합특별시_동부소방서 관할구역 현황」(2025-07-31, 공공데이터포털
     15048895) 이 지산을 "동명동 등 4개 법정동" 으로 적는다. 2021년 기준
     디지털광주문화대전 서술과도 일치한다.

     그런데 지산 보유는 펌프차(중형) 2 · 구급차 1 · 생활안전차 1 이 전부다.
     물탱크차 · 화학차 · 사다리차 2종 · 조연차는 **전부 대인에만 있다.**
     인터뷰의 "물탱크차는 커서 못 들어갈 때가 있다" 도 대인 차량 이야기다.

   ★ 그래서 소속 센터로 묶는다. 선착/후발로 가르지 않는다 —
     대인이 화재 시 동시 출동하는지 요청 후 오는지를 아직 모른다.
     관할은 문서로 확정된 사실이고 출동 편성은 추론이다. 확정된 것만 쓴다.
     D-30 광주 인터뷰 질문 목록에 넣을 것.

   ★ 펌프차와 구급차가 두 묶음에 각각 나온다. 중복이 아니라 사실이다 —
     지산 펌프차 2대와 대인 펌프차 2대는 따로 움직이는 자원이다. 제원이
     같아 통과선은 같지만, "어디서 오는 차인가" 가 관제사의 판단 재료다.

   ★ 왜 profiles.json 10종을 다 띄우지 않는가.
     그 파일은 조달 규격 분류라 전국 대표 제원이다. 동부소방서에 대형
     펌프차는 한 대도 없다 — 목록에 두면 있지도 않은 차의 회전반경을
     근거로 골목을 판단하게 된다.

   ★ 뺀 것과 이유. 생활안전차(대인1·지산1)는 화재 출동 차량이 아니고,
     구조버스(2)는 인원 수송이라 골목 진입 대상이 아니다. 행정·순찰·진단·
     화물·화재조사·트레일러·장비운반·교육차는 출동 차량이 아니다.
     용산119안전센터는 관할이 다르고 GRAPH_BUFFER 1.5km 밖이라 뺐다.

   ★ match — profiles.json 항목과의 대응 신뢰도. 이것을 화면에 밝힌다.
       확정  보유 대장의 차종명이 profiles.json 항목과 그대로 맞는다
       추정  가장 가까운 항목을 골랐다. 다른 축으로 분류돼 있다
       없음  profiles.json 에 대응 항목이 없다
     ★ 추정을 확정처럼 보이게 하지 않는다. 회전반경은 7.3 과 11.9 사이가
       세 배 차이 나는 자리라, 모르면서 아는 척하면 그게 곧 사고다.

   ★ grade 를 문자열로 박아 둔 이유. 화면이 반경 수치를 보고 등급을
     계산하면 그것도 일종의 재판정이다. 등급은 선언이지 계산이 아니다.

   ★ 차량을 바꿔도 지도 색은 바뀌지 않는다(설계 원칙 6).

       id       내부 키
       label    화면에 뜨는 이름. 보유 대장의 어휘를 그대로 쓴다
       profile  profiles.json 의 id. 없으면 null
       count    그 센터의 보유 대수
       at       배치된 곳
       group    드롭다운 묶음. 소속 센터. fleetGroups 의 값이어야 한다
       match    "확정" · "추정" · "없음"
       grade    "여유" · "주의" · "미판정"
       turnUnknown  true 면 profiles.json 의 회전반경을 안 가져온다
       outrigger    아우트리거 최대 전개너비(m). 전폭과 다른 축이다
       note     추정·없음일 때 그 사유. 화면에 그대로 뜬다
   ──────────────────────────────────────────────────────────── */
  fleet: [
    /* ── 지산119안전센터 — 동명동 관할 ── */
    { id:"pump-js",  label:"펌프차 (중형)",      profile:"pump_medium",     group:"지산119안전센터",
      count:2, at:"지산", match:"확정", grade:"여유" },
    { id:"amb-js",   label:"구급차",           profile:"ambulance_current_example", group:"지산119안전센터",
      count:1, at:"지산", match:"확정", grade:"미판정",
      note:"제원표에 회전반경이 비어 있다" },

    /* ── 대인119안전센터 — 관할은 아니나 특수차가 전부 여기 있다 ── */
    { id:"pump-di",  label:"펌프차 (중형)",      profile:"pump_medium",     group:"대인119안전센터",
      count:2, at:"대인", match:"확정", grade:"여유" },
    { id:"tanker",   label:"물탱크차 (대형)",     profile:"tanker_large",    group:"대인119안전센터",
      count:1, at:"대인", match:"확정", grade:"주의" },
    { id:"chem",     label:"화학차",           profile:"chemical_large",  group:"대인119안전센터",
      count:1, at:"대인", match:"추정", grade:"주의",
      note:"보유 대장에 대형·고성능 구분이 없어 대형으로 잡았다" },
    { id:"ladder-s", label:"직진형 사다리차 53m", profile:"ladder_33m_plus", group:"대인119안전센터",
      count:1, at:"대인", match:"추정", grade:"미판정",
      turnUnknown:true, outrigger:6.0,
      note:"광주 규격서(2025-06)에 회전반경 규정이 없다. 차대가 6x4 3축·전장 13m 이하라 제원표의 2축 대표값(11.89m)은 실제보다 작다 — 그래서 안 띄운다" },
    { id:"ladder-a", label:"굴절형 사다리차 27m", profile:"ladder_under_33m",group:"대인119안전센터",
      count:1, at:"대인", match:"추정", grade:"미판정",
      turnUnknown:true,
      note:"제원표는 길이로 갈리는데 굴절형은 관절 유무로 갈린다. 다른 축이라 회전반경을 가져오지 않는다" },
    { id:"amb-di",   label:"구급차",           profile:"ambulance_current_example", group:"대인119안전센터",
      count:3, at:"대인", match:"확정", grade:"미판정",
      note:"제원표에 회전반경이 비어 있다" },
    { id:"light",    label:"조연차",           profile:null,              group:"대인119안전센터",
      count:1, at:"대인", match:"없음", grade:"미판정",
      note:"제원표에 항목이 없다. 전폭 미상" },

    /* ── 동부소방서 본서 — 119구조대는 동구 전역이 관할이다 ── */
    { id:"rescue",   label:"구조차",           profile:"rescue_5t",       group:"본서 119구조대",
      count:2, at:"본서 · 동구 전역", match:"확정", grade:"미판정",
      note:"제원표에 회전반경이 비어 있다" },
  ],
  /* 묶음 표시 순서. 관할 센터가 맨 위여야 한다 —
     관제사가 드롭다운을 열었을 때 처음 보는 것이 동명동에 오는 차다. */
  fleetGroups: ["지산119안전센터", "대인119안전센터", "본서 119구조대"],
  /* 기본 선택. 동명동 관할 센터의 차이고 골목 진입을 실제로 시도한다. */
  fleetDefault: "pump-js",
  /* 출처. 대수는 공공누리 4유형이라 화면 표기가 의무다.
     제원 출처는 profiles.json 이고, 사다리차 전폭·전고·차대·아우트리거는
     「소방고가차-사다리차(53m) 규격서」(2025-06, 나라장터 R25BK00911861)다.
     근거는 docs/DECISIONS.md §84 를 볼 것. */
  fleetSource: "보유 대수 — 동부소방서 소방차량현황 (2026-05-14) · 관할 — 동부소방서 관할구역 현황 (2025-07-31) · 광주광역시 소방안전본부",

  /* 지형. 공개DEM 90m 를 8배 보간한 표현용 값이다.
     ★ 판정에는 쓰지 않는다. 90m 격자는 골목 20개를 한 픽셀로 덮는다.
     raster-dem 타일(terrain.py 산출) + map.setTerrain() 으로 지면 자체를 휘게 한다.
     exaggeration 을 올리면 기복이 과장되어 입체감이 살지만 실제 지형과 멀어진다. */
  terrain: {
    enabled     : true,
    exaggeration: 1.0,   // ★ 1.0 = 실제 비율. GIS 는 현실을 반영해야 하므로 기본은 1.0 이다.
                         //    올리면 보기는 좋아지지만 표고가 왜곡된다.
                         //    발표 영상용으로 잠깐 올릴 수는 있으나 그 사실을 명시할 것.
  },
};
