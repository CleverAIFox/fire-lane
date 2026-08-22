/* Fire-Lane · 배경 타일 URL
   ────────────────────────────────────────────────────────────
   V-World 인증키. sources.yaml 의 basemap.key 와 같은 값이다.
   ★ 브라우저 호출은 &domain= 파라미터가 등록 URL과 문자열까지 정확히
     일치해야 타일이 나온다. 로컬은 V-World에 http://localhost:8000 을
     등록한 뒤 VW_DOMAIN 을 그 값으로 맞출 것.
   ★ WMTS 축 순서는 {z}/{y}/{x} 다. {z}/{x}/{y} 로 쓰면 타일이 어긋난다.
   키가 아직 안 풀렸으면 USE_VWORLD=false 로 두면 CARTO 다크 배경으로 뜬다.
   ──────────────────────────────────────────────────────────── */
import { CONFIG } from "./config-access.js";

export const VW_KEY     = CONFIG.vworld.key;
export const VW_DOMAIN  = location.origin;
export const USE_VWORLD = CONFIG.vworld.enabled;

export const vw = t => `https://api.vworld.kr/req/wmts/1.0.0/${VW_KEY}/${t}/{z}/{y}/{x}.${t==="Satellite"?"jpeg":"png"}?domain=${encodeURIComponent(VW_DOMAIN)}`;

export const CARTO = t => ["a","b","c","d"].map(s=>
  `https://${s}.basemaps.cartocdn.com/${t==="light"?"light_all":"dark_all"}/{z}/{x}/{y}@2x.png`);
