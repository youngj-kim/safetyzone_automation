# 매일 09:00 KST 자동실행 준비

워크플로 파일은 `.github/workflows/daily-monitor.yml`이다. GitHub 예약 시간은 UTC를
사용하므로 `0 0 * * *`가 매일 한국시간 09:00이다.

## 실행 환경

기존 PostGIS가 사용자 PC의 `localhost:5433`에 있으므로 GitHub 공용 서버에서는 접근할
수 없다. 다음 조건을 갖춘 Windows self-hosted runner를 사용한다.

- 라벨: `self-hosted`, `windows`, `x64`
- 매일 09:00에 PC가 켜져 있음
- GitHub Actions Runner 서비스가 실행 중
- Docker Desktop과 `mobility_postgis` 컨테이너가 실행 중
- Python 설치는 워크플로의 `setup-python` 단계가 처리

## GitHub 저장소 설정

Settings → Secrets and variables → Actions에서 다음을 설정한다.

### Secrets

- `OPEN_API_SERVICE_KEY`
- `DATABASE_URL`
- 선택: `SLACK_WEBHOOK_URL`
- 선택: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

### Variables

소규모 시험은 다음처럼 직접 지정한다.

```text
SGG_CODES=11110
```

전국 코드 파일을 저장소에 반영한 뒤에는 다음을 사용하고 `SGG_CODES`는 비운다.

```text
SGG_CODES_FILE=config/sgg_codes_nationwide.txt
```

두 값이 모두 있으면 합쳐서 실행되므로 전환할 때 기존 값을 반드시 확인한다.

## 실행 순서

1. 저장소 체크아웃
2. Python 3.12 준비 및 패키지 설치
3. 기존 `mobility_db`와 표준노드링크 객체 확인
4. 보호구역 수집·정규화·변경감지·저장·알림
5. 중복·도형·시군구 범위 품질검사

## 운영 전 수동 확인

GitHub Actions의 `Daily safety-zone monitor`에서 `Run workflow`를 눌러 한 번 실행한다.
모든 단계가 초록색인지 확인하고 다음 날 예약 실행 이력을 확인한다. 예약 실행은 PC,
Runner 서비스 또는 Docker가 꺼져 있으면 정상 완료될 수 없다.
