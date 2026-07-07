# Seoul rollout validation — 2026-07-07

이 문서는 보호구역 모니터링 MVP를 서울 전체 25개구로 확장한 검증 결과입니다.

## 검증 범위

검증 일자: 2026-07-07  
실행 방식: GitHub Actions self-hosted runner 수동 실행  
대상 DB: 기존 `mobility_postgis` / `mobility_db`  
대상 스키마: `raw`, `analysis`, `ops`

대상 시군구 코드는 서울특별시 25개구입니다.

```text
11110,11140,11170,11200,11215,11230,11260,11290,11305,11320,11350,11380,11410,11440,11470,11500,11530,11545,11560,11590,11620,11650,11680,11710,11740
```

## 최종 멱등성 검증 결과

최종 확인 run:

```text
pipeline_run_id: 88abfa07-7dae-4dc9-b9dc-c05a782deba5
finished_at: 2026-07-07 09:12:32.509413+00
monitored_sgg_codes: {11110,11140,11170,11200,11215,11230,11260,11290,11305,11320,11350,11380,11410,11440,11470,11500,11530,11545,11560,11590,11620,11650,11680,11710,11740}
```

결과:

| 항목 | 값 |
| --- | ---: |
| polygon_count | 1544 |
| polygon_unchanged_count | 1544 |
| polygon_event_count | 0 |
| facility_point_count | 1862 |
| point_unchanged_count | 1862 |
| point_event_count | 0 |
| idempotency_status | PASS |

판정:

```text
PASS
```

같은 서울 25개구 조건으로 재실행했을 때 모든 폴리곤과 시설 포인트가 `UNCHANGED`로 판정되었고, 가짜 변경 이벤트는 생성되지 않았습니다.

## 검증된 기능

이번 단계에서 확인된 기능은 다음과 같습니다.

- 서울 25개구 Open API 수집
- 원본 item snapshot 저장
- 보호구역 polygon 정규화 및 보정
- 시설 point 분리 저장
- 대표관리번호 기반 통합 보호구역 그룹 뷰
- polygon 변경 감지
- point 변경 감지
- 동일 조건 재실행 시 멱등성 유지
- GitHub Actions self-hosted runner 실행
- Telegram 테스트 알림 발송

## Telegram 알림 검증

GitHub Actions Repository Secrets에 다음 값이 등록되었습니다.

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

`notification_test=true` 옵션으로 수동 workflow를 실행했고, Telegram에서 테스트 메시지 수신을 확인했습니다.

수신 메시지:

```text
[보호구역 모니터링 테스트]
Telegram/Slack 알림 연결이 정상입니다.
이 메시지는 운영 데이터를 변경하지 않는 테스트 발송입니다.
```

알림 동작 기준:

- 변경 이벤트가 있으면 Telegram 알림 발송
- 변경 이벤트가 없으면 알림 미발송

서울 25개구 재실행 결과는 `UNCHANGED` 상태이므로 운영 모니터링 실행에서는 알림이 오지 않는 것이 정상입니다.

## 운영상 주의사항

자동 실행이 안정적으로 동작하려면 Windows host에서 다음이 켜져 있어야 합니다.

1. Docker Desktop
2. `mobility_postgis` container
3. GitHub Actions self-hosted runner

수동 테스트 시에는 다음 순서로 진행합니다.

```powershell
cd D:\Project\3_safetyzone_monitoring_system\.actions-runner
.\run.cmd
```

runner가 `Listening for Jobs` 상태가 되면 GitHub Actions에서 workflow를 실행합니다.

## 다음 단계

서울 25개구 검증은 완료되었습니다. 다음 후보 작업은 다음과 같습니다.

1. 하루 이상 09:00 KST 자동 스케줄 실행 관찰
2. 전국 확대용 `SGG_CODES_FILE` 생성
3. 전국 단위 API 수집 시간 및 DB 적재량 점검
4. 표준노드링크 매칭 설계 단계 진입
