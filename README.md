# Safety Zone Change Monitoring System (MVP)

경찰청 전국 보호구역 Open API를 매일 수집해 폴리곤 보호구역의 신규·변경·누락을 찾고,
PostgreSQL/PostGIS에 현재 상태와 변경 이력을 저장하는 Python MVP입니다. 웹 대시보드와
표준노드링크 매칭은 의도적으로 포함하지 않았습니다.

공식 데이터는 어린이·노인·장애인 보호구역과 geometry를 제공하며, 첨부 절차서 기준 API
주소와 필드명, 원본 좌표계 EPSG:5181을 사용합니다. Point 데이터는 제외하고 Polygon 및
GeometryCollection 안의 Polygon만 저장합니다.

## 변경 판정

- `zone_key`: 경찰청의 `ptznMngNo`를 기준으로 만든 SHA-256입니다. 관리번호가 없으면 시설명,
  유형, 주소, 최초 등록일 등 안정 필드를 사용합니다.
- `data_hash`: 정규화한 전체 속성과 방향·시작점이 정규화된 폴리곤 geometry의 SHA-256입니다.
- `NEW`: 현재 테이블에 키가 없음
- `UPDATED`: 키는 같고 `data_hash`가 다름
- `UNCHANGED`: 키와 `data_hash`가 같음. 실행 집계에는 포함하지만 이벤트는 만들지 않음
- `MISSING`: 이번 완전 수집에 키가 없음. `change_event`에 이전 스냅샷을 남긴 후 현재
  `safety_zone` 테이블에서 제거

MISSING은 이번 실행에 설정한 `SGG_CODES` 범위 안에서만 판정합니다. 어느 시군구든 API 호출이
실패하면 DB 반영을 시작하지 않습니다. 전체 응답이 0건일 때도 대량 삭제 오인을 막기 위해
실행을 실패 처리합니다.

## 로컬 실행

필요 조건: Python 3.11 이상, Docker Desktop.

```powershell
Copy-Item .env.example .env
# .env의 OPEN_API_SERVICE_KEY와 SGG_CODES를 실제 값으로 수정

docker compose up -d db
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m safety_zone_monitor init-db
python -m safety_zone_monitor run
```

`OPEN_API_SERVICE_KEY`에는 공공데이터포털의 **Decoding key**를 사용합니다. 첨부 문서에는 실제
키가 들어 있으므로 저장소에 커밋하지 않았습니다. 공개되었거나 공유 범위를 알 수 없다면
공공데이터포털에서 키를 재발급하는 편이 안전합니다.

`config/sgg_codes.example.txt`는 연기 테스트용 일부 코드뿐입니다. 전국 운영 전에는 전체 최신
5자리 시군구 코드 목록을 준비하여 `SGG_CODES`에 쉼표로 넣거나 아래처럼 파일로 지정하세요.

```dotenv
SGG_CODES=
SGG_CODES_FILE=config/sgg_codes.txt
```

## 알림

변경 이벤트가 한 건 이상일 때만 알림을 보냅니다. `.env`에 Slack Incoming Webhook 또는
Telegram bot 정보를 설정할 수 있으며, 둘 다 설정하면 양쪽으로 전송합니다. 알림 설정이 없으면
변경은 정상 저장되고 경고 로그만 남습니다.

## 데이터베이스

- `safety_zone`: 최신 활성 폴리곤 레코드
- `change_event`: `NEW`, `UPDATED`, `MISSING` 이벤트와 전·후 JSON 스냅샷
- `ingestion_run`: 실행 범위, 상태, 수집/판정 건수, 알림 전송 시각

geometry는 `MultiPolygon, EPSG:5181`로 저장합니다. 향후 표준노드링크가 EPSG:5179 등 다른
좌표계라면 PostGIS의 `ST_Transform`으로 매칭용 좌표계를 파생할 수 있습니다.

## 테스트

```powershell
pytest
ruff check .
```

## GitHub Actions 전환

`.github/workflows/daily-monitor.yml`은 매일 `00:00 UTC`, 즉 `09:00 KST`에 실행됩니다.
GitHub 저장소에 다음을 설정합니다.

- Secrets: `OPEN_API_SERVICE_KEY`, `DATABASE_URL`
- Repository variable: `SGG_CODES`
- 선택 Secrets: `SLACK_WEBHOOK_URL` 또는 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

Actions에서 접근할 수 없는 로컬 DB 주소는 사용할 수 없습니다. 운영 전에는 외부에서 접근 가능한
PostgreSQL/PostGIS와 TLS 연결 문자열을 준비하고, 네트워크 허용 목록과 최소 권한 DB 계정을
설정하세요.
