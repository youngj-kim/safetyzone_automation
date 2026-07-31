# 보호구역 수동 실행 및 자동실행 전환 준비

워크플로 파일은 `.github/workflows/daily-monitor.yml`이다. Supabase 온라인 운영 전환 이후
예약 수집은 전국 단일 실행 대신 6개 청크 분산 schedule로 운영한다. 수동 검증과 긴급 재실행을 위해
`workflow_dispatch`도 계속 유지한다.

## 실행 환경

현재 보호구역 API 수집과 대시보드용 운영 DB는 Supabase Free PostgreSQL/PostGIS로 전환한다.
GitHub-hosted runner(`ubuntu-latest`)가 Supabase에 접속해 수집, 변경감지, 품질검사, 대시보드
export를 실행한다.

로컬 PostGIS와 Windows self-hosted runner는 표준노드링크, NGII, 매칭 검수 작업에는 계속 사용할
수 있지만, 보호구역 일일 수집 운영의 기본 실행 위치에서는 제외한다.

## GitHub 저장소 설정

Settings → Secrets and variables → Actions에서 다음을 설정한다.

### Secrets

- `OPEN_API_SERVICE_KEY`
- `DATABASE_URL`
- 선택: `SLACK_WEBHOOK_URL`
- 선택: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

### Variables

소규모 시험만 할 때는 다음처럼 직접 지정할 수 있다.

```text
SGG_CODES=11110
```

현재 기본 운영 설정은 전국 시군구 코드 파일을 사용하는 방식이다. 저장소 변수에는 다음을
둔다.

```text
SGG_CODES_FILE=config/sgg_codes_nationwide.txt
```

`SGG_CODES`와 `SGG_CODES_FILE`을 동시에 지정하면 합쳐서 실행되므로, 전환할 때 기존
값을 반드시 확인한다. 전국 청크를 수동 실행할 때는 repository variable을 바꾸지 않고
workflow dispatch 입력값 `sgg_codes_file`만 사용한다.

## 전국 수집 청크 실행

공공 API 429 rate limit 때문에 전국 269개 시군구를 한 번에 실행하면 중간 실패 시
그 실행 전체가 DB에 반영되지 않을 수 있다. 전국 기준선 또는 전국 보강 수집은 다음
청크 파일을 하나씩 수동 실행한다.

```text
config/sgg_chunks/nationwide_chunk_01.txt
config/sgg_chunks/nationwide_chunk_02.txt
config/sgg_chunks/nationwide_chunk_03.txt
config/sgg_chunks/nationwide_chunk_04.txt
config/sgg_chunks/nationwide_chunk_05.txt
config/sgg_chunks/nationwide_chunk_06.txt
```

GitHub Actions의 `Daily safety-zone monitor`에서 `Run workflow`를 누른 뒤
`sgg_codes_file`에 실행할 청크 파일 경로를 입력한다. `notification_test`는 `false`로
둔다. 청크 사이에는 API 제한 회복을 위해 충분한 간격을 둔다.

청크 실행은 성공한 시군구 범위만 DB에 반영되므로, 전국 전체 실행보다 실패 복구가 쉽다.
0건을 반환한 시군구는 삭제 판정 범위에서 제외해 기존 데이터를 대량 삭제로 오인하지
않는다.

전국 청크 실행이 모두 끝난 뒤 대시보드에 반영하려면 운영 DB에서 dashboard data를 다시
export하고, 변경된 `dashboard/data/*.json`, `dashboard/data/current_zones/*.geojson`,
`dashboard/data/current_points/*.geojson`, 변경 GeoJSON을 커밋한 뒤 GitHub Pages 배포를 진행한다.
현재 객체는 전국 단일 GeoJSON으로 배포하지 않고 시도 단위로 로드한다. 최근 변경 이벤트는
전국 단위 파일을 유지하고, 시도별 변경 건수는 별도 요약 JSON으로 표시한다.

일일 자동화에서는 변경 감지 결과가 있는 성공 실행에서만 변경 목록, 현재 객체, 지도 레이어용
대시보드 정적 데이터를 갱신한다. `run` 명령은 `run_summary.json`을 만들고, workflow는
`has_changes=true`일 때 전체 `dashboard/data`를 export한 뒤 커밋/푸시한다. 수집 실패나 품질
검증 실패 시에는 변경 데이터와 현재 객체 데이터는 갱신하지 않는다.

대신 대시보드의 `모니터링 이력`은 매번 상태를 확인할 수 있도록 별도로 관리한다. 변경이 없는
성공 실행이나 실패 실행에서는 `dashboard/data/overview.json`만 export/commit해 GitHub Pages에
성공/실패 이력과 실패 사유를 표시한다.

2026-07-28에 감지된 인천 `28125`, `28155`, `28275`, `28290`의 대량 `NEW`는 2026-07-01
인천 행정구역 개편에 따른 검단구 신설 및 서구 명칭 변경 반영분으로 본다. DB 원천 이벤트는
보존하되, 대시보드 export에서는 일반 신규 보호구역 목록과 시도별 신규 카운트에서 제외하고
`dashboard/data/change_exclusions.json`에 제외 사유를 남긴다.

## API 오류 유형

API 호출 실패는 `ApiError` 메시지 앞에 유형을 붙여 기록한다. 대시보드의 모니터링 이력과
GitHub Actions 로그에서 이 유형을 먼저 확인한다.

| 유형 | 의미 | 기본 대응 |
|---|---|---|
| `RATE_LIMIT` | 429 또는 공공 API 호출 한도 초과 | 당일 추가 재시도 중단, 다음 날 또는 더 작은 청크로 재실행 |
| `AUTH_ERROR` | 인증키 누락, 만료, 잘못된 키, GitHub Secret 미반영 | 공공데이터포털 키와 GitHub Secret `OPEN_API_SERVICE_KEY` 확인 |
| `EMPTY_RESULT` | 해당 시군구가 0건 응답 | 삭제 판정에서 제외. 반복되면 warning으로 관리 |
| `MALFORMED_RESPONSE` | JSON 구조, `response/body`, `totalCount` 등 응답 형식 이상 | API 일시 장애인지 확인 후 재실행. 반복되면 파서 보강 |
| `INCOMPLETE_PAGE` | `totalCount`보다 실제 item 수가 부족한 페이지 응답 | 데이터 반영 중단이 정상. 같은 청크를 나중에 재실행 |
| `TIMEOUT` | 요청 제한 시간 초과 | API 상태 확인 후 재실행. 반복되면 timeout/청크 크기 조정 |
| `NETWORK_ERROR` | DNS, 연결 실패, 네트워크 단절 | runner PC 네트워크와 공공 API 접속 확인 |
| `SERVER_ERROR` | 공공 API 5xx 응답 | API 서버 장애 가능성이 높으므로 시간을 두고 재실행 |
| `DB_READ_ONLY` | Supabase pooler 또는 DB가 읽기 전용 세션으로 응답 | `DATABASE_URL`이 Session pooler `:5432`인지 확인하고, DB 용량/쓰기 권한을 점검 |
| `DB_DISK_FULL` | Supabase 임시 디스크 또는 DB 용량 부족 | 전체 dashboard export를 피하고, 무변경/실패 이력은 `overview.json` 경량 export만 사용 |

## 실행 순서

1. 저장소 체크아웃
2. GitHub-hosted runner에서 Python 3.11 설정 및 패키지 설치
3. `prepare_db=true`일 때만 Supabase 운영 DB migration 실행
4. `audit-ops-db`로 Supabase 운영 DB 계약 확인
5. 보호구역 수집·정규화·변경감지·저장·알림
6. 중복·도형·시군구 범위 품질검사
7. 변경이 있으면 전체 `dashboard/data` export, 변경이 없거나 실패 이력만 필요하면 `overview.json`만 export

## 자동 실행 schedule

GitHub Actions cron은 UTC 기준이므로 한국시간 09:00~10:40에 맞춰 다음처럼 분산한다.

| KST | UTC cron | 대상 파일 |
|---|---|---|
| 09:00 | `0 0 * * *` | `config/sgg_chunks/nationwide_chunk_01.txt` |
| 09:20 | `20 0 * * *` | `config/sgg_chunks/nationwide_chunk_02.txt` |
| 09:40 | `40 0 * * *` | `config/sgg_chunks/nationwide_chunk_03.txt` |
| 10:00 | `0 1 * * *` | `config/sgg_chunks/nationwide_chunk_04.txt` |
| 10:20 | `20 1 * * *` | `config/sgg_chunks/nationwide_chunk_05.txt` |
| 10:40 | `40 1 * * *` | `config/sgg_chunks/nationwide_chunk_06.txt` |

수동 실행에서는 `sgg_codes_file` 입력값을 지정하면 해당 청크만 실행한다. schedule 실행에서는
cron 문자열에 따라 workflow 내부에서 청크 파일을 자동 선택한다.

## 운영 전 수동 확인

GitHub Actions의 `Daily safety-zone monitor`에서 `Run workflow`를 눌러 한 번 실행한다.
모든 단계가 초록색인지 확인한다. 2026-07-31 기준 `chunk_01`은 Supabase 운영 DB에서 일반
변경감지, 품질검사, 모니터링 이력 갱신까지 성공했다. 자동 schedule은 청크 분산 방식으로 켜져
있으므로 다음 실행일에는 각 청크가 순차적으로 성공하는지 확인한다.

## Windows 시간 동기화 점검

self-hosted runner가 GitHub와 HTTPS로 통신하므로 Windows 시간이 크게 어긋나면 인증서
검증이 실패할 수 있다. 다음과 같은 오류가 보이면 PC 시간을 먼저 동기화한다.

```text
certificate chain: NotTimeValid
```

관리자 권한 PowerShell에서 다음을 실행한다.

```powershell
net start w32time
w32tm /resync /force
```

동기화 후 GitHub Actions Runner 서비스를 재시작하고 workflow를 다시 수동 실행한다.
