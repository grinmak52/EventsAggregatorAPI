# Events Aggregator

Сервис-агрегатор мероприятий на FastAPI + PostgreSQL. Данные берёт из Events Provider API, продаёт билеты через него и отправляет пользователю уведомление через Capashino.

## Запуск локально

```powershell
uv sync
copy .env.example .env   # заполните значения
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Документация API (Swagger): `http://localhost:8000/docs`.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `DATABASE_URL` | строка подключения к PostgreSQL | локальная БД |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USERNAME`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE_NAME` | параметры БД в кластере, если заданы `POSTGRES_HOST`, строка собирается из них | нет |
| `PROVIDER_URL` | адрес Events Provider | внешний хост провайдера |
| `PROVIDER_API_KEY` | API-ключ провайдера | пусто |
| `SYNC_INTERVAL_SECONDS` | период синхронизации событий | 86400 |
| `CAPASHINO_URL` | адрес Capashino (в кластере внутренний хост) | внешний хост Capashino |
| `CAPASHINO_API_KEY` | токен для заголовка `X-API-Key` | пусто |
| `OUTBOX_INTERVAL_SECONDS` | пауза между проходами воркера outbox | 5 |
| `OUTBOX_BATCH_SIZE` | сколько записей outbox обрабатывается за проход | 10 |
| `OUTBOX_MAX_ATTEMPTS` | число попыток отправки, после него статус `failed` | 5 |
| `IDEMPOTENCY_TTL_SECONDS` | срок хранения ключей идемпотентности | 86400 |
| `IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS` | период очистки устаревших ключей | 3600 |
| `SENTRY_DSN` | DSN проекта в GlitchTip, если пусто, отправка ошибок выключена | пусто |

## Фоновые процессы

Все фоновые задачи запускаются в том же процессе, что и API, отдельными корутинами в `lifespan` FastAPI (`app/main.py`):

- `sync_loop`: синхронизация событий с провайдером;
- `outbox_loop`: отправка уведомлений из таблицы `outbox`;
- `cleanup_loop`: удаление устаревших ключей идемпотентности.

Отдельный запуск воркера не нужен: контейнер применяет миграции и запускает `uvicorn`.

## Transactional Outbox

При покупке билета запись в `outbox` (`ticket_created`, `payload` с `ticket_id` и названием события) сохраняется в одной транзакции с билетом. Воркер берёт записи со статусом `pending`, вызывает `POST /api/notifications` в Capashino (`reference_id` = `ticket_id`, `idempotency_key` = id записи outbox) и после успеха ставит `sent`. При ошибке запись остаётся `pending` и отправляется повторно. После `OUTBOX_MAX_ATTEMPTS` неудач запись получает статус `failed`.

## POST /api/tickets

Тело запроса:

```json
{
  "event_id": "uuid",
  "first_name": "Иван",
  "last_name": "Иванов",
  "email": "ivan@example.com",
  "seat": "A15",
  "idempotency_key": "любая-строка-до-255-символов"
}
```

`idempotency_key` необязателен и передаётся **в теле запроса**.

| Код | Когда |
|---|---|
| 201 | билет создан; ответ `{"ticket_id": "uuid"}` |
| 201 | повторный запрос с тем же ключом и теми же данными: новый билет не создаётся, провайдер не вызывается, возвращается тот же `ticket_id` |
| 409 | ключ уже использован с другими данными (другое событие, место, email и т. д.) |
| 409 | регистрация закрыта или провайдер отклонил запрос (например, место занято) |
| 404 | событие не найдено |
| 400 | ошибка валидации тела запроса |
| 502 | ошибка на стороне провайдера |

Если провайдер вернул ошибку, ключ не сохраняется: повторный запрос с тем же ключом обрабатывается как новый. Без ключа каждый запрос обрабатывается как новый. Ключи хранятся `IDEMPOTENCY_TTL_SECONDS` секунд.

## Разработка

```powershell
uv run ruff check .
uv run ruff format .
uv run pytest
```

CI (GitHub Actions) выполняет: ruff (lint и format) → тесты → сборка образа → деплой. Деплой начинается только после успешной проверки линтера.

## Мониторинг ошибок

Необработанные исключения отправляются в GlitchTip через `sentry-sdk` (интеграция с FastAPI). DSN задаётся переменной `SENTRY_DSN`.