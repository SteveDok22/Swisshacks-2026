# День 6: Database persistence + Audit Log

Сегодня заменили in-memory store на **настоящую базу данных** и добавили **immutable audit log**. Это критический compliance feature для AMINA.

## Список изменений в проекте

### Новые файлы
- `backend/app/db/session.py` — async DB session setup
- `backend/app/db/models.py` — SQLModel database models
- `backend/app/db/seed.py` — заполнение БД mock данными
- `backend/app/schemas/audit.py` — audit + decision schemas
- `backend/app/services/db_store.py` — DB-backed store (заменяет InMemoryStore)
- `backend/app/services/audit.py` — AuditService (append-only logging)
- `backend/app/services/decision.py` — DecisionService (compliance officer actions)
- `backend/app/api/v1/decisions.py` — POST/GET для decisions
- `backend/app/api/v1/audit.py` — search audit log

### Изменённые файлы (переписаны под async DB)
- `backend/app/main.py` — DB init + close в lifespan
- `backend/app/services/risk_engine.py` — async + DB
- `backend/app/services/counterfactual.py` — async + DB
- `backend/app/services/jurisdiction.py` — async + DB
- `backend/app/services/explanation.py` — async + DB
- `backend/app/api/v1/cases.py` — async + DB, + `/history` endpoint
- `backend/app/api/v1/clients.py` — async + DB
- `backend/app/api/v1/scoring.py` — async + DB
- `backend/app/api/v1/counterfactuals.py` — async + DB
- `backend/app/api/v1/jurisdictions.py` — async + DB
- `backend/app/api/v1/explanations.py` — async + DB
- `backend/app/api/v1/__init__.py` — добавлены decisions + audit routers
- `backend/app/schemas/__init__.py` — добавлены audit exports
- `backend/pyproject.toml` — добавлен greenlet

### Удалённые файлы
- `backend/app/services/store.py` — заменён на db_store.py

### Не трогать
- `backend/.env`
- `backend/.venv/`
- `.git/`
- `backend/data/models/social_engineering_v1.joblib` — модель остаётся

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -q ~/Downloads/swisshacks-2026-day6.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
```

## Шаг 2: Обнови зависимости

```bash
cd backend
source .venv/bin/activate
uv pip install -r pyproject.toml
```

Новые пакеты: `sqlmodel`, `aiosqlite`, `greenlet`. Около 30 секунд установки.

## Шаг 3: Запусти сервер (DB будет создана автоматически)

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

При **первом запуске** должен увидеть:
```
database_initialized          tables=['clients', 'cases', 'decisions', 'audit_log']
seed_starting
seed_completed                client_count=10  case_count=6
database_seeded_with_mock_data
ml_models_loaded              loaded_count=1
jurisdictions_loaded          count=4
application_ready
```

DB файл создастся в `backend/data/risk_platform.db`.

При **повторных запусках** seed пропускается (`seed_skipped reason='already_populated'`).

Чтобы пересоздать БД с нуля:
```bash
rm backend/data/risk_platform.db
# Затем перезапусти сервер
```

## Шаг 4: Проверь новые endpoints в Swagger UI

Открой **http://localhost:8000/docs**. Появились **2 новые секции** и **1 новый endpoint в cases**:
- `cases` — добавлен `GET /cases/{case_id}/history`
- `decisions` — POST + GET
- `audit` — GET с filters

### 4.1: Запиши compliance decision

1. Раскрой `POST /api/v1/decisions`
2. Try it out → body:

```json
{
  "case_id": "22222222-2222-2222-2222-222222222204",
  "action": "block",
  "officer_id": "anna.mueller@amina.ch",
  "rationale": "Confirmed via callback — client unaware of request. Filed MROS report."
}
```

3. Execute → должен получить 201 Created с decision ID
4. Поле `overrode_ai`: `false` (officer согласился с AI что нужно BLOCK)

Теперь попробуй **override**:

```json
{
  "case_id": "22222222-2222-2222-2222-222222222204",
  "action": "allow",
  "officer_id": "anna.mueller@amina.ch",
  "rationale": "Client confirmed identity through secondary biometric channel"
}
```

Поле `overrode_ai`: `true`, `ai_recommended_action`: `"block"` — система зафиксировала, что officer пошёл против AI.

Если попробовать override **без rationale** — получишь 400 error: "Rationale is required when overriding AI recommendation".

### 4.2: View case history

1. Раскрой `GET /api/v1/cases/{case_id}/history`
2. case_id: `22222222-2222-2222-2222-222222222204`
3. Execute

Получишь полный audit trail в chronological order:
- `case_scored` — когда AI оценил case
- `decision_recorded` — когда officer принял решение
- Любые другие events (explanations, etc.)

Каждый event содержит `payload` с детальной информацией.

### 4.3: Search audit log

1. Раскрой `GET /api/v1/audit`
2. Параметры:
   - `event_type`: `decision_recorded`
   - `actor_id`: `anna.mueller@amina.ch`
3. Execute → все decisions от Anna Müller

Это **прямой compliance feature**: "покажите мне все decisions конкретного officer'a за период".

Другие полезные filters:
- `risk_level=critical` — все critical events
- `from_date=2026-05-01` — события с конкретной даты
- `event_type=case_scored` — все ML scorings

### 4.4: Persistence test

1. Сделай decision (Шаг 4.1)
2. Останови сервер (Ctrl+C)
3. Запусти заново
4. `GET /api/v1/cases/22222222-...-204/history` → events на месте!

Это **главное** — мы теперь имеем настоящую persistence. Сервер можно перезапускать, данные сохраняются.

## Шаг 5: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 6: Database persistence + immutable audit log

- Migrated from InMemoryStore to async SQLite + SQLModel
- Added 4 DB tables: clients, cases, decisions, audit_log
- Added DecisionService — compliance officer actions
- Added AuditService — append-only event logging
- Added /decisions endpoints (POST + GET by case)
- Added /audit endpoint with filtering (event_type, actor, dates, etc.)
- Added /cases/{id}/history — full audit trail for a case
- All endpoints now persist across restarts
- 19 endpoints total, backend persistence-complete
"
```

## Чек-лист завершения дня

- [ ] Сервер запускается с `database_initialized tables=['clients', 'cases', 'decisions', 'audit_log']`
- [ ] DB файл создан в `backend/data/risk_platform.db`
- [ ] `POST /api/v1/decisions` записывает decision и возвращает 201
- [ ] Override без rationale возвращает 400 error
- [ ] `GET /cases/{id}/history` показывает chronological audit trail
- [ ] `GET /api/v1/audit` поддерживает filtering
- [ ] После перезапуска сервера данные сохраняются
- [ ] Git commit сделан

## Что узнал сегодня (теория для джуна)

### Async SQL — почему важно

```python
async def list_cases(session: AsyncSession):
    result = await session.execute(select(CaseDB))
    return list(result.scalars().all())
```

Каждое `await` означает: "если БД занята, отпусти CPU для других requests". Без async — сервер блокируется на каждом query, обрабатывает по 1 request за раз.

Sync vs Async на 100 одновременных users:
- **Sync**: 100 req queue, каждый ждёт предыдущий → 5 секунд per user
- **Async**: все 100 параллельно, CPU работает с тем что готово → 50ms per user

FastAPI **родился async**. Sync calls внутри = anti-pattern.

### Append-only audit log

Этот pattern из мира банковского compliance:
- **Никогда** UPDATE — события неизменны
- **Никогда** DELETE — даже ошибочные события остаются
- Если нужна "правка" — добавляешь **новый** event

Почему? FINMA Circular 2018/3:
> "Banks must maintain complete and immutable records of all client-affecting decisions and the reasoning behind them."

Если бы мы могли UPDATE/DELETE audit log — теряли бы возможность доказать что произошло.

### Repository pattern

`DbStore` — это **repository**. Он:
- Получает session (зависимость)
- Возвращает domain objects (`Client`, `Case`), не DB rows
- Скрывает SQL detail от рестa приложения

Это даёт нам:
- Тестируемость (mock'ать DbStore легче чем SQLAlchemy)
- Гибкость (завтра можем перейти на Postgres без изменения services)
- Чистый интерфейс между слоями

### Dependency injection через `Depends`

```python
async def list_cases(
    session: Annotated[AsyncSession, Depends(get_session)],
):
```

FastAPI **сам** создаёт session при каждом request, передаёт её в endpoint, commit'ит после успеха или rollback'ит при ошибке.

Это паттерн **"Unit of Work"**: одна транзакция = один request. Если что-то в request упало — DB не остаётся в неконсистентном состоянии.

### JSON columns в SQLite

```python
context_data: dict[str, Any] = Field(
    default_factory=dict,
    sa_column=Column(JSON),
)
```

Зачем JSON?
- Разные case_types имеют разные поля
- Нет смысла делать таблицу с 50 nullable колонками
- JSON позволяет быстро добавлять новые fields

**Trade-off**: меньше queryability. Если хотим фильтровать по `context_data.amount` — нужны JSON path expressions (SQLite поддерживает). Для нашего MVP — overkill.

### Override detection logic

```python
overrode_ai = (
    ai_recommended is not None
    and ai_recommended != payload.action
)
```

Когда officer сохраняет решение:
1. Берём текущий `risk_score` из БД
2. Маппим в action (как ML pipeline)
3. Сравниваем с тем что officer выбрал
4. Если != → `overrode_ai = True` + требуем rationale

Это **compliance защита**: если officer часто override'ит AI — significant signal что либо AI плохо работает, либо officer проблемный. Audit log позволяет анализировать.

---

## Архитектурные решения объяснённые

**Почему два типа моделей (DB + API schemas)?**

Завтра может потребоваться:
- Добавить колонку для analytics, которая не показывается в API
- Переименовать поле в БД без breaking API contract
- Денормализовать данные для performance

Separate layers = independent evolution.

**Почему `flush()` вместо `commit()` в services?**

`flush()` — пишет в БД, но не закрывает транзакцию (можно ROLLBACK).
`commit()` — финализирует.

FastAPI dependency `get_session()` делает `commit()` **сам** в конце request. Если внутри services мы `commit()` — теряем контроль над транзакцией.

Pattern: services делают `flush()`, FastAPI dependency делает финальный `commit()`.

**Почему DB модели в отдельном модуле от SQLModel.metadata?**

`SQLModel.metadata` — global registry всех таблиц. Если импортируем модель — она автоматически регистрируется. Если **не импортируем** — `create_all()` её пропустит.

Внутри `init_db()` мы делаем `from app.db import models  # noqa: F401` именно для этого: импорт ради side-effect регистрации.

**Почему JSON для profile_data + отдельные колонки для важных полей?**

Поля типа `aum_chf`, `is_pep`, `primary_jurisdiction` часто фильтруются → отдельные индексированные колонки.
Поля типа `preferred_asset_classes`, `whitelist_wallets` — read-mostly, не фильтруем → JSON.

Это **hybrid design**: производительность для горячих fields + гибкость для холодных.

---

## Дальше: что после Дня 6

Бэкенд **полностью готов** для MVP. У нас есть:
- 19 endpoints
- Persistent DB
- Audit log
- ML pipeline с SHAP + Counterfactuals
- Anonymization + Jurisdiction Engine
- Claude API integration (mock + real)
- Streaming SSE

Следующие приоритеты:
- **День 7**: Integration tests + типобезопасность (mypy strict)
- **Дни 8-9**: Voice deepfake detection module (Resemblyzer + AASIST)
- **Дни 10-11**: Behavioral baselines per client + Optuna hyperparameter tuning
- **Дни 12-13**: Расширенные mock data (faker), audio samples generation
- **Дни 15-21**: Frontend (Next.js + Tailwind + shadcn/ui)

Скажи когда День 6 готов, и мы решим: либо двигаемся к Дню 7 (testing), либо сразу к Дню 8 (voice analysis), либо к фронтенду (если хочешь быстрее увидеть визуальный прогресс).
