# День 2: API endpoints + Pydantic schemas + Mock data

Сегодня превращаем пустой сервер в работающий API с реалистичными данными.

## Что мы сделали

1. ✅ **Pydantic schemas** — типобезопасные модели для Cases, Clients, общих компонентов
2. ✅ **Enums** — единый источник истины для CaseType, RiskLevel, Jurisdiction, etc.
3. ✅ **Mock data generator** — 10 реалистичных швейцарских/международных клиентов + 5 cases
4. ✅ **In-memory store** — временное хранилище (заменим на SQLite в День 6)
5. ✅ **API endpoints** — GET/POST/PATCH для cases, GET для clients
6. ✅ **Router подключен** к main app через `/api/v1` prefix

## Новая структура backend

```
backend/app/
├── api/v1/
│   ├── __init__.py          # Собирает все routers
│   ├── cases.py             # ← НОВОЕ: 4 endpoints для cases
│   └── clients.py           # ← НОВОЕ: 2 endpoints для clients
├── schemas/
│   ├── __init__.py          # ← НОВОЕ: публичный API пакета
│   ├── common.py            # ← НОВОЕ: TimestampedModel, PaginatedResponse
│   ├── enums.py             # ← НОВОЕ: CaseType, RiskLevel, etc.
│   ├── client.py            # ← НОВОЕ: ClientProfile, Client
│   └── case.py              # ← НОВОЕ: Case, CaseContext, CaseRead
├── services/
│   ├── mock_data.py         # ← НОВОЕ: реалистичные клиенты и cases
│   └── store.py             # ← НОВОЕ: in-memory storage
├── core/                    # без изменений
└── main.py                  # обновлён: подключены routers + seed на старте
```

## Шаг 1: Распакуй обновлённый архив

Замени **только содержимое папок** `backend/app/` на новые файлы из архива.

**Важно**: твой `.env`, `.git/`, `data/` — НЕ трогай. Они остаются.

Самый простой способ:

```bash
cd ~/Projects/swisshacks-2026

# Сохрани свой .env если ты его уже настроил
cp backend/.env backend/.env.backup 2>/dev/null || true

# Распакуй новый архив поверх (только новые/изменённые файлы перезапишутся)
unzip -o swisshacks-2026-day2.zip -d ../

# Верни .env
mv backend/.env.backup backend/.env 2>/dev/null || true
```

## Шаг 2: Запусти сервер

```bash
cd backend

# Если ещё не активировал venv:
source .venv/bin/activate

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ты должен увидеть в логах:
```
application_starting     app_name='SwissHacks Risk Intelligence Platform'
store_seeded             client_count=10  case_count=5
store_initialized        clients=10  cases=5
application_ready
```

Это значит mock данные загрузились.

## Шаг 3: Проверь Swagger UI

Открой **http://localhost:8000/docs** в браузере. Увидишь:

- **meta** секция: `/health`, `/`
- **cases** секция: 4 endpoint'а
- **clients** секция: 2 endpoint'а

Каждый endpoint полностью документирован (типы параметров, response schemas) **автоматически** благодаря Pydantic. Это критично — твоя команда увидит API и сразу поймёт как им пользоваться, без отдельной документации.

## Шаг 4: Попробуй API в Swagger

Прямо в браузере на `/docs`:

### 4.1: Список клиентов
1. Раскрой `GET /api/v1/clients`
2. Нажми "Try it out" → "Execute"
3. Должен увидеть 10 клиентов: Hans Müller, Elisabeth Schneider, Marc Weber, Claire Dubois, François Martin, Giulia Rossi, Klaus Hofmann, Wei Chen, Mei Lin Tan, Ahmed Al-Rashid

### 4.2: Список cases
1. Раскрой `GET /api/v1/cases`
2. Try it out → Execute
3. Должен увидеть 5 cases: social engineering (AMINA), investment recommendation (JB), XRPL transaction (Ripple)

### 4.3: Фильтрация
1. В том же endpoint `GET /api/v1/cases`
2. В поле `case_type` выбери `social_engineering`
3. Execute → должно вернуться 3 cases

### 4.4: Детали одного case
1. Скопируй один из UUID из списка cases (например `22222222-2222-2222-2222-222222222201`)
2. Раскрой `GET /api/v1/cases/{case_id}`
3. Вставь UUID, Execute
4. Увидишь полный context: requested amount, voice_sample_id, RM name, transcript excerpt

### 4.5: Создание case
1. Раскрой `POST /api/v1/cases`
2. Try it out
3. В body вставь:
```json
{
  "client_id": "11111111-1111-1111-1111-111111111101",
  "case_type": "social_engineering",
  "jurisdiction": "CH",
  "context": {
    "summary": "Test case created via API",
    "data": {
      "requested_amount_chf": 50000,
      "channel": "phone_call"
    }
  }
}
```
4. Execute → должен получить 201 Created с новым UUID
5. Снова `GET /api/v1/cases` — total теперь 6

## Шаг 5: Curl команды (для команды)

Полезно знать как делать requests из терминала:

```bash
# Список cases
curl http://localhost:8000/api/v1/cases | jq

# Фильтр
curl "http://localhost:8000/api/v1/cases?case_type=social_engineering&page_size=10" | jq

# Один client
curl http://localhost:8000/api/v1/clients/11111111-1111-1111-1111-111111111101 | jq
```

Если нет `jq` — установи: `brew install jq`. Это утилита для pretty-print JSON.

## Шаг 6: Сохрани прогресс в Git

```bash
cd ~/Projects/swisshacks-2026

git add .
git status   # проверь что в staging
git commit -m "Day 2: API endpoints + Pydantic schemas + mock data

- Added Pydantic schemas: Case, Client, Common, Enums
- Added InMemoryStore with mock data generator
- Added 10 realistic clients (CH/EU/HK/AE jurisdictions)
- Added 5 cases covering AMINA/JB/Ripple use cases
- Added /api/v1/cases (GET list, GET detail, POST, PATCH)
- Added /api/v1/clients (GET list, GET detail)
"
```

## Чек-лист завершения дня

- [ ] Сервер запускается без ошибок
- [ ] Логи показывают `store_seeded client_count=10 case_count=5`
- [ ] `/docs` показывает 6 endpoints в секциях cases и clients
- [ ] `GET /api/v1/clients` возвращает 10 клиентов
- [ ] `GET /api/v1/cases` возвращает 5 cases
- [ ] Фильтрация `?case_type=social_engineering` работает (3 results)
- [ ] `POST /api/v1/cases` создаёт новый case
- [ ] Git commit сделан

## Что узнал сегодня (теория для джуна)

### Pydantic schemas

Это **самое важное** что появилось сегодня. Pydantic делает три вещи одновременно:

1. **Валидация на входе**: если кто-то отправит `case_type: "blah"` — API вернёт 422 с понятной ошибкой, а не пустит мусор в систему
2. **Сериализация на выходе**: твой Python объект автоматически превращается в JSON
3. **Документация бесплатно**: Swagger UI всё это знает из типов

```python
class CaseCreate(BaseModel):
    client_id: UUID         # Pydantic проверит что это валидный UUID
    case_type: CaseType     # Только значения из enum'а
    jurisdiction: Jurisdiction
    context: CaseContext    # Вложенная схема — тоже валидируется
```

### Layered schemas (DTO pattern)

Заметь: у нас три похожих модели для Case:
- `CaseBase` — общие поля
- `CaseCreate` — что приходит в POST (без id, без status, без timestamps)
- `Case` — полная сущность (со всеми полями)
- `CaseRead` — что отдаём в response (то же что Case, но эксплицитно)
- `CaseListItem` — компактная версия для списков (только summary, без full context)

Почему так много? Это **DTO pattern**. На входе и выходе разные структуры:
- При создании клиент **не должен** передавать id (мы генерируем)
- В списке мы **не возвращаем** полный context (слишком много данных)
- В detail view мы **возвращаем** всё

Это критично для production. На хакатоне может казаться overkill, но **жюри видит профессиональный код**.

### Dependency Injection в FastAPI

```python
async def list_cases(
    store: Annotated[InMemoryStore, Depends(get_store)],
    ...
):
```

Это паттерн **Dependency Injection**. Мы говорим FastAPI: "вызови `get_store()` и передай результат в `store` параметр". 

Зачем? В День 6 мы заменим `get_store()` на функцию которая возвращает SQLAlchemy session — и **код endpoints не изменится**. Это называется "loose coupling" и это hallmark профессионального кода.

### structlog в действии

Заметь как мы логируем:

```python
logger.info(
    "cases_listed",
    count=len(items),
    total=total,
    filters={"case_type": case_type, ...},
)
```

Не строка, а **event name + kv-pairs**. Это значит можно искать в логах: "найди все cases_listed где total > 100". В Grafana/Datadog это первоклассные запросы.

### Pagination

```python
class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
```

Стандарт для всех list endpoints. На фронте мы сможем показать "Showing 1-20 of 156" и кнопки next/prev. Без этого UI выглядит непрофессионально.

## Архитектурные решения объяснённые

**Почему `case_type` в схеме, а не отдельный endpoint типа `/social-engineering/cases` и `/xrpl-transactions/cases`?**

Это наш дифференциатор — **универсальная архитектура**. Один endpoint `/cases` обрабатывает все типы. Различия в `case.context.data` (полиморфные данные). Это даёт:
- Одна логика scoring/audit для всех типов
- Frontend компонент `CaseQueue` работает с любым типом
- На хакатоне за 6 часов можем добавить новый case_type без рефакторинга

**Почему mock_data в коде, а не в JSON файлах?**

Сейчас — потому что быстрее. К дню 11 (когда добавим faker) — переедем на файлы. Принцип: **самое простое решение которое работает, оптимизируем когда станет проблемой**.

## Дальше: День 3

Завтра делаем **ML pipeline core** — переносим твой PP5 код (XGBoost + SHAP) в reusable форму. К концу Дня 3:
- `services/risk_engine.py` — универсальный scoring class
- Endpoint `POST /api/v1/scoring/{case_id}` — реальный ML scoring
- Synthetic данные для обучения первой модели
- Сохранённая модель в `data/models/`

Это самый важный день для тебя — будем превращать твой PP5 опыт в production-quality код.
