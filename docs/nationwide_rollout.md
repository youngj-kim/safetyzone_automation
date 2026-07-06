# 전국 수집 전환 절차

전국 수집은 과거 시군구 코드 목록을 복사하지 않고 행정표준코드관리시스템의 최신
법정동 코드 전체자료에서 생성한다. 행정구역 개편으로 코드가 바뀔 수 있기 때문이다.

## 1. 공식 코드 파일 준비

행정표준코드관리시스템에서 **법정동 코드 전체자료 CSV**를 내려받는다. 파일에는
법정동코드와 폐지여부 또는 폐지구분 컬럼이 있어야 한다.

## 2. 현존 시군구 코드 생성

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor build-sgg-codes `
  --source "다운로드한_법정동코드.csv" `
  --output config/sgg_codes_nationwide.txt
```

생성기는 UTF-8과 CP949 CSV를 지원하고 폐지 코드를 제외한다. 폐지상태 컬럼이 없는
파일은 과거 코드를 안전하게 구분할 수 없으므로 실패 처리한다.

## 3. 로컬 시험 설정

`.env`에서 기존 `SGG_CODES=11110`을 제거하거나 비우고 다음을 설정한다.

```dotenv
SGG_CODES_FILE=config/sgg_codes_nationwide.txt
```

처음부터 운영 현재 테이블에 반영하지 말고 API 호출량과 예상 건수를 확인한 뒤 전국
기준선을 생성한다. 어느 한 시군구라도 응답이 0건이면 해당 실행 전체가 실패하며 기존
현재 데이터는 변경되지 않는다. 이는 부분 장애를 대량 삭제로 오인하는 것을 막는다.

## 4. 품질검사

```powershell
.\.venv\Scripts\python.exe -m safety_zone_monitor quality-report
```

검사 항목:

- 설정한 시군구 코드가 현재 데이터에 모두 존재하는지
- `ptznMngNo`가 서로 다른 현재 레코드에 중복됐는지
- Polygon과 Point가 유효하며 EPSG:5179인지
- Point만 있고 연결된 Polygon 그룹이 없는 경우가 있는지
- 현재 Polygon, Point, 통합 그룹 수

`status=PASS`를 확인한 뒤 자동실행 범위를 전국으로 전환한다. Polygon 없는 Point 그룹은
원본상 가능성이 있으므로 경고로 표시하고, 중복·잘못된 도형·예상 시군구 누락은 실패로
표시한다.
