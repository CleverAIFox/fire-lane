# 지도 띄우기 — 팀원용 세팅 가이드

> `outputs/dongmyeong_map.html`(Mapbox) / `outputs/dongmyeong_map_naver.html`(Naver)
> 두 파일 모두 **API 키가 코드에 없다.** 각자 발급받아 넣어야 열린다.
> 키를 코드에 박으면 GitHub 비밀 스캔에 걸려 push 자체가 막힌다.

---

## 왜 키가 빠져 있나

2026-08-06 push 시 GitHub Push Protection 이 Mapbox 토큰을 탐지해 거부했다. 해결하려고 코드에서 키를 빼고 **런타임 주입 방식**으로 바꿨다.

```javascript
const MAPBOX_TOKEN = window.MAPBOX_TOKEN || "";   // ← 코드에는 빈 값
```

---

## 방법 1 — 로컬 키 파일 (권장)

프로젝트 루트에 `keys.local.js` 를 만든다. **이 파일은 `.gitignore` 에 등록되어 있어 커밋되지 않는다.**

```javascript
// keys.local.js  ← 절대 커밋하지 말 것
window.MAPBOX_TOKEN   = "pk.eyJ1Ijo...";        // Mapbox 공개 토큰
window.NAVER_CLIENT_ID = "abcdefghij";          // 네이버 클라우드 Client ID
```

HTML 의 `<head>` 안, 다른 스크립트보다 **먼저** 한 줄 추가한다.

```html
<script src="../keys.local.js"></script>
```

### 네이버 지도는 URL 에도 넣어야 한다

`dongmyeong_map_naver.html` 안에서 `NAVER_CLIENT_ID_PLACEHOLDER` 를 찾아 본인 ID 로 바꾼다.

```html
<script src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=NAVER_CLIENT_ID_PLACEHOLDER"></script>
```

⚠ 바꾼 뒤 **커밋하지 말 것.** 확인:

```bash
git diff --stat outputs/
```

`dongmyeong_map_naver.html` 이 뜨면 되돌린다.

```bash
git checkout outputs/dongmyeong_map_naver.html
```

## 방법 2 — 브라우저 콘솔 (임시 확인용)

HTML 을 그냥 열고 F12 → Console 에 붙여넣은 뒤 새로고침.

```javascript
window.MAPBOX_TOKEN = "pk.eyJ1Ijo...";
```

네이버는 스크립트 URL 에 키가 들어가서 이 방법으로는 안 된다. Mapbox 전용.

---

## 키 발급

### Mapbox

1. https://account.mapbox.com 가입
2. Access tokens → **Create a token**
3. 이름 `fire-lane-dev`, scope 는 기본값(public) 그대로
4. **URL restriction 을 반드시 걸 것** — `http://localhost:*`, 배포 도메인
5. 생성된 `pk.` 로 시작하는 토큰 복사

| 접두사 | 성격 |
|---|---|
| `pk.` | 공개 토큰. 브라우저 노출 전제. **이걸 쓴다** |
| `sk.` | 시크릿 토큰. 계정 수정 권한. **절대 브라우저에 넣지 말 것** |

무료 한도: 월 5만 로드. 팀 개발용으로 충분하다.

### 네이버 클라우드 플랫폼

1. https://www.ncloud.com 가입 (본인인증 + 결제수단 등록 필요)
2. Console → **Services → Application Service → Maps**
3. **Application 등록** — 이름 `fire-lane`
4. **Web Dynamic Map** 서비스 선택
5. **Web 서비스 URL** 에 아래 등록 (등록 안 하면 인증 오류)
   ```
   http://localhost
   http://127.0.0.1
   file://
   ```
6. 발급된 **Client ID** 복사

무료 한도: 월 10만 건.

> ⚠ 네이버는 등록한 URL 외에서 호출하면 지도가 아예 안 뜬다. `file://` 로 직접 열 거면 반드시 등록할 것.

---

## 로컬 서버로 여는 게 안전하다

`file://` 로 열면 브라우저 보안 정책 때문에 막히는 기능이 있다(특히 GPS).

```bash
cd outputs
python -m http.server 8000
```

→ http://localhost:8000/dongmyeong_map.html

**HTTPS 가 아니면 `navigator.geolocation` 이 동작하지 않는다.** 현장 답사에서 내 위치를 지도에 띄우려면 Netlify Drop 등으로 배포할 것(무료, HTTPS 기본, 드래그 앤 드롭 1분). 배포 시 해당 도메인을 Mapbox/네이버 허용 URL 에 추가해야 한다.

---

## 지도에 표시되는 것

| 레이어 | 내용 |
|---|---|
| 도로구간 | 222개, `current_status` 색상 |
| CCTV | 53개 마커 |
| 소화전 | 1개 (동명동 법정경계 내 실매칭) |
| 소방서 | 광주동부소방서 |
| 동명동 경계 | 폴리곤 |

### 색상 (2026-08-06 기준)

| 색 | 의미 | 개수 |
|---|---|---|
| BLUE | 주 도로, 판정 불필요 (`width_min_m` ≥ 12m) | 7 |
| YELLOW | 실시간 판정 대기 (CANDIDATE + CCTV 있음) | 98 |
| RED | 진입 불가 (`width_min_m` < 2m) | 55 |
| GRAY | 사각지대 (CCTV 없음 또는 폭 결측) | 62 |

GREEN / ORANGE 는 YOLO 연동 후 등장한다. 현재 CANDIDATE+COVERED 는 전부 잠정 YELLOW — 버그가 아니라 설계된 동작이다.

도로 클릭 시 팝업: **최소폭 / 중앙폭 / 출처(`width_src`) / tier / CCTV / 상태 / 서류값(참고)**

> `width_src` 가 `ngii_digitalmap`(수치지도 도로경계면) 또는 `silpok`(실폭도로)로 표시된다.
> 서류값(`road_bt_legacy`)은 **참고용일 뿐 판정에 쓰이지 않는다.** 2026-08-06 개정, `docs/PROJECT.md` §4 참조.

---

## 문제 해결

| 증상 | 원인 |
|---|---|
| 화면이 회색, 타일 안 뜸 | Mapbox 토큰 미설정 또는 URL restriction 불일치 |
| "인증 실패" 팝업 | 네이버 Client ID 오류 또는 Web 서비스 URL 미등록 |
| 도로는 뜨는데 지도 배경이 없음 | 타일 API 문제. 도로 데이터는 HTML 에 내장이라 항상 뜬다 |
| 콘솔에 401 / 403 | 키는 있으나 도메인 제한에 걸림 |

키를 바꾼 뒤에는 **브라우저 강력 새로고침**(Ctrl+Shift+R).
