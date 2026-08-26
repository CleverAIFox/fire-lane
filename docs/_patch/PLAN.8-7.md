### 8-7. 저장소 위생 🟡

**★ 2026-08-26 재판정.** 세 항목을 "하류 없음"으로 묶었으나 실제로 대조하니
둘이 틀렸다. 근거 없이 묶은 것이 원인이다.

| 순 | 대상 | 판정 | 근거 |
|---|---|---|---|
| 1 | `web/data/{ortho,terrain}` 타일 | **기각** | `web/js/map.js` 가 `./data/ortho/{z}/{x}/{y}.jpg` 를 상대경로로 읽는다. `pages.yml` 은 `checkout` 한 트리를 그대로 발행하므로, 추적을 끊으면 **배포된 지도의 정사영상·지형이 사라진다.** 재생성에는 raw 정사영상 1.3GB 가 필요해 CI 가 만들 수 없다 |
| 2 | 조사 스크립트 여덟 | **보류** | 하류가 있다. `test_guards` 가 `route_probe` · `naver_join` 을, `paths.py` · `layers.py` · `test_layers` 가 `jijeok_probe` 를, `width_fn` · `corner_probe` · `jijeok_review` · `naver_page` 가 서로를 참조한다. 옮기려면 임포트 다섯 곳을 함께 고친다 |
| 3 | `data/baseline/*` 전량 복사 | 유효 | git 태그와 지문이 같은 일을 한다. `baseline.py` 를 고칠 때 §1 #30 과 함께 판정한다 |

1 번을 정말 걷어내려면 타일을 저장소 밖(오브젝트 스토리지)에 두고 `map.js` 가
절대 URL 을 보게 해야 한다. **그것은 배포 인프라 결정이라 여기서 다루지 않는다.**
23.6MB 는 지금 아무것도 막고 있지 않다.

§1 #26 · #31 · #34 · #35
