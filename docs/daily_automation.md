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
- Python 3.11 이상이 self-hosted PC의 PATH에 등록되어 있음
- Windows 시간이 정상 동기화되어 있음. 시간이 어긋나면 GitHub 연결에서
  `certificate chain: NotTimeValid` SSL 오류가 날 수 있다.

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

## 실행 순서

1. 저장소 체크아웃
2. self-hosted PC의 Python 버전 확인 및 패키지 설치
3. 기존 `mobility_db`와 표준노드링크 객체 확인
4. 보호구역 수집·정규화·변경감지·저장·알림
5. 중복·도형·시군구 범위 품질검사

## 운영 전 수동 확인

GitHub Actions의 `Daily safety-zone monitor`에서 `Run workflow`를 눌러 한 번 실행한다.
모든 단계가 초록색인지 확인하고 다음 날 예약 실행 이력을 확인한다. 예약 실행은 PC,
Runner 서비스 또는 Docker가 꺼져 있으면 정상 완료될 수 없다.

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
