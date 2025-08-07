# Заметки по интеграции ЮKassa

## Основные методы API

### Создание платежа
- POST /payments - создание платежа
- Требуется: amount, currency, description
- Возвращает: payment_id, confirmation_url

### Проверка статуса платежа
- GET /payments/{payment_id} - получение информации о платеже
- Статусы: pending, waiting_for_capture, succeeded, canceled

### Webhook'и
- Автоматические уведомления о смене статуса платежа
- Требуется настройка endpoint'а для получения уведомлений

## Альтернативный подход через YooMoney API

Из статьи на Habr узнал про более простой подход через YooMoney API:

### Quickpay - быстрые платежи
```python
from yoomoney import Quickpay

quickpay = Quickpay(
    receiver="410019014512803",  # номер кошелька
    quickpay_form="shop",
    targets="Описание платежа",
    paymentType="SB",  # способ оплаты
    sum=150,  # сумма
    label="unique_payment_id"  # уникальная метка
)
```

### Проверка оплаты
```python
from yoomoney import Client

client = Client(token)
history = client.operation_history(label="unique_payment_id")
```

## Выбор подхода

Для Telegram-бота лучше использовать YooMoney API (не ЮKassa), так как:
1. Проще интеграция
2. Не требует webhook'ов
3. Можно проверять статус по запросу
4. Подходит для физических лиц

## Необходимые шаги

1. Получить токен YooMoney API
2. Создать модуль для работы с платежами
3. Интегрировать в бота создание ссылок на оплату
4. Добавить проверку статуса платежей
5. Начислять кредиты после успешной оплаты

