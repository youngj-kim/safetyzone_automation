# Windows Scheduler → GitHub Actions dispatch

이 문서는 Windows 작업 스케줄러가 매일 09:00에 GitHub Actions workflow를 호출하도록 구성하는 절차입니다.

이 방식은 다음 구조입니다.

```text
Windows 작업 스케줄러 09:00
→ GitHub workflow_dispatch API 호출
→ GitHub Actions run 생성
→ self-hosted runner가 job 수신
→ Python monitor 실행
→ PostGIS 저장
→ GitHub Actions 화면에서 성공/실패 확인
```

## 왜 이 방식으로 바꾸는가

Python을 작업 스케줄러에서 직접 실행하면 `ops.pipeline_run`에는 기록이 남지만 GitHub Actions에는 실행 기록이 남지 않습니다.

반대로 이 방식은 시간 트리거는 Windows가 맡고, 실행 기록과 로그는 GitHub Actions에 남깁니다.

## 1. GitHub token 준비

GitHub에서 fine-grained personal access token을 생성합니다.

권장 범위:

- Repository: `youngj-kim/safetyzone_automation`
- Permission: Actions `Read and write`
- 만료일: 운영 정책에 맞게 설정

토큰은 절대 git에 커밋하지 않습니다.

## 2. 로컬 token 파일 생성

프로젝트 폴더에 `.secrets` 폴더를 만들고 토큰 파일을 저장합니다.

```powershell
cd D:\Project\3_safetyzone_monitoring_system
New-Item -ItemType Directory -Force .secrets
notepad .secrets\github_dispatch_token.txt
```

메모장에 GitHub token 값만 한 줄로 붙여넣고 저장합니다.

`.secrets/`는 `.gitignore`에 포함되어 있으므로 git에 올라가지 않습니다.

## 3. 수동 dispatch 테스트

PowerShell에서 다음을 실행합니다.

```powershell
cd D:\Project\3_safetyzone_monitoring_system
powershell.exe -ExecutionPolicy Bypass -File .\scripts\dispatch_github_workflow.ps1
```

성공하면 GitHub Actions에 `Daily safety-zone monitor` run이 새로 생성됩니다.

알림 테스트만 보내려면:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\dispatch_github_workflow.ps1 -NotificationTest true
```

## 4. Windows 작업 스케줄러 설정

기존 `Safety Zone Daily Monitor` 작업의 동작을 Python 직접 실행에서 GitHub dispatch 스크립트 실행으로 바꿉니다.

프로그램/스크립트:

```text
powershell.exe
```

인수 추가:

```text
-NoProfile -ExecutionPolicy Bypass -File "D:\Project\3_safetyzone_monitoring_system\scripts\dispatch_github_workflow.ps1"
```

시작 위치:

```text
D:\Project\3_safetyzone_monitoring_system
```

트리거:

```text
매일 09:00
```

설정 탭 권장값:

- 요청 시 작업이 실행되도록 허용
- 예약된 시작 시간을 놓친 경우 가능한 한 빨리 작업 시작
- 작업이 이미 실행 중이면 새 인스턴스 시작 안 함

## 5. runner는 계속 필요함

이 방식도 self-hosted runner가 온라인이어야 실제 monitor job이 실행됩니다.

Windows 로그인 후 runner가 다음 상태인지 확인합니다.

```text
Connected to GitHub
Listening for Jobs
```

runner가 꺼져 있으면 GitHub Actions run은 `Queued` 상태로 대기합니다.

## 6. 운영 확인 기준

GitHub Actions:

```text
Actions → Daily safety-zone monitor → 최신 run Success
```

DB:

```sql
select
    pipeline_run_id,
    started_at,
    finished_at,
    status,
    polygon_count,
    facility_point_count,
    error_message
from ops.pipeline_run
order by started_at desc
limit 5;
```

서울 25개구 기준 정상 기대값:

```text
status = SUCCESS
polygon_count = 1544
facility_point_count = 1862
error_message = null
```
