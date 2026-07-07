# Telegram notification setup

보호구역 모니터링은 변경사항이 있을 때만 Telegram 알림을 보냅니다. 변경사항이 없으면 알림을 보내지 않습니다.

## 필요한 값

GitHub Actions Repository Secrets에 다음 두 값을 추가합니다.

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

이미 사용 중인 필수 값은 그대로 유지합니다.

```text
OPEN_API_SERVICE_KEY
DATABASE_URL
```

## 1. Telegram bot token 만들기

Telegram에서 `@BotFather`를 열고 `/newbot`으로 새 bot을 만듭니다.

BotFather가 발급하는 token을 GitHub Repository Secret에 저장합니다.

```text
Name: TELEGRAM_BOT_TOKEN
Value: BotFather가 발급한 token
```

## 2. chat id 확인

만든 bot에게 아무 메시지나 한 번 보냅니다.

그 다음 브라우저에서 아래 주소를 엽니다. `<TOKEN>`에는 실제 bot token을 넣습니다.

```text
https://api.telegram.org/bot<TOKEN>/getUpdates
```

응답 JSON에서 다음 값을 찾습니다.

```text
message.chat.id
```

이 값을 GitHub Repository Secret에 저장합니다.

```text
Name: TELEGRAM_CHAT_ID
Value: message.chat.id 값
```

## 3. 알림 동작 방식

알림은 다음 조건에서만 전송됩니다.

```text
polygon 변경 이벤트 있음
또는
facility point 변경 이벤트 있음
```

같은 조건으로 재실행해서 전부 `UNCHANGED`인 경우에는 Telegram 알림이 가지 않는 것이 정상입니다.

## 4. 알림 테스트 방법

알림 연결 직후 바로 메시지를 보고 싶다면 `SGG_CODES` 범위를 확장합니다.

예를 들어 기존 3개 구에서 서울 25개구로 확장하면 새 보호구역이 감지되므로 Telegram 알림이 발송됩니다.

서울 25개구 GitHub Variables 예시:

```text
SGG_CODES=11110,11140,11170,11200,11215,11230,11260,11290,11305,11320,11350,11380,11410,11440,11470,11500,11530,11545,11560,11590,11620,11650,11680,11710,11740
```

운영 안정성 확인 후에는 같은 조건으로 한 번 더 실행해서 알림이 가지 않는지 확인합니다.
