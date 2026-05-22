# День 5: Claude API Integration + Streaming Natural Language

Сегодня **финальный кусок backend перед frontend**. Соединили всё в один pipeline:

```
Case → ML score → SHAP → Counterfactuals → Anonymizer → Claude → Natural language
                                              ↑
                                  Privacy by design (FINMA)
```

К концу Дня 5 у тебя **production-quality backend** — 15 endpoints, streaming SSE, anonymization, mock fallback.

---

## Список изменений в проекте

### Новые файлы
- `backend/app/schemas/explanation.py` — schemas для natural language responses
- `backend/app/services/anthropic_client.py` — Claude API wrapper с caching + mock mode
- `backend/app/services/prompts.py` — prompt templates с compliance officer persona
- `backend/app/services/explanation.py` — orchestrator (ML + CF + Anon + Claude)
- `backend/app/api/v1/explanations.py` — 3 endpoints (POST, GET stream, GET anonymization)

### Изменённые файлы
- `backend/app/schemas/__init__.py` — добавлены explanation exports
- `backend/app/api/v1/__init__.py` — подключен explanations router

### Не трогать
- `backend/.env` — твой Anthropic API key (если уже добавлен)
- `backend/.venv/`
- `.git/`
- `backend/data/models/` — сохранённая модель

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -q ~/Downloads/swisshacks-2026-day5.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
git status
```

## Шаг 2: Обнови зависимости

```bash
cd backend
source .venv/bin/activate

# anthropic уже в pyproject.toml, на всякий случай:
uv pip install -r pyproject.toml
```

## Шаг 3: Запусти сервер

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Что должен увидеть в логах:
```
store_seeded                client_count=10 case_count=6
ml_models_loaded            loaded_count=1
jurisdictions_loaded        count=4
application_ready
```

При первом запросе к `/explanations`:
- Если ANTHROPIC_API_KEY не задан в `.env`:
  ```
  anthropic_client_mock_mode    hint='Set ANTHROPIC_API_KEY in backend/.env'
  ```
- Если задан:
  ```
  anthropic_client_initialized   mode=real
  ```

**Mock mode — это feature, не bug**. Возвращает realistic placeholder responses. Полезно для:
- Разработки без burn'а tokens
- CI/CD pipelines  
- Демо если интернет упал на хакатоне

## Шаг 4: Опционально — настрой ANTHROPIC_API_KEY

Получи key на https://console.anthropic.com/, затем:

```bash
nano backend/.env
```

Добавь:
```
ANTHROPIC_API_KEY=sk-ant-api03-XXXXXXXXXXXX
```

Перезапусти сервер. Теперь ответы будут от **реального Claude**.

**Когда нужно?** Не сейчас. Mock mode работает для всех Шагов 5-7. Реальный API понадобится на demo и когда покажешь команде на хакатоне.

## Шаг 5: Проверь endpoints в Swagger UI

Открой **http://localhost:8000/docs**. Появилась секция **explanations** с 3 endpoints.

### 5.1: Full explanation

1. Раскрой `POST /api/v1/explanations/{case_id}`
2. case_id: `22222222-2222-2222-2222-222222222204` (extreme suspicious case)
3. Execute

Получишь structured response:
```json
{
  "case_id": "...",
  "executive_summary": "This case exhibits multiple risk indicators...",
  "risk_factors": "Three primary risk factors drove the elevated score...",
  "alternative_outcomes": "The model identified scenarios...",
  "recommended_action_rationale": "Given the combination of behavioral anomalies...",
  "jurisdiction_notes": "Under FINMA AMLA, suspicious transactions must be reported to MROS...",
  "metadata": {
    "model": "mock",  // или "claude-sonnet-4-5" если API key set
    "anonymization_applied": true,
    "fields_redacted_count": 5,
    "fields_bucketed_count": 1,
    "cached": false
  }
}
```

**Это финальное output** для compliance officer'а. Каждый раздел можно отдельно рендерить в UI.

### 5.2: Anonymization preview

1. Раскрой `GET /api/v1/explanations/{case_id}/anonymization`
2. case_id: `22222222-2222-2222-2222-222222222201` (Hans Müller)
3. Execute

Получишь:
```json
{
  "fields_kept_local": ["client_name", "destination_wallet", "voice_sample_id", "transcript_excerpt", "rm_name"],
  "fields_sent_to_ai": {
    "client_pseudonym": "CLIENT_AAF7",
    "channel": "phone_call",
    "requested_amount_chf": "CHF 1M-5M",
    "destination_wallet": "0xNE****e7f8",
    "destination_country": "SG",
    "voice_sample_id": "[REDACTED]",
    "transcript_redacted": "[CONTENT REDACTED]",
    "rm_name": "RM_9CCC"
  },
  "fields_redacted": ["client_name", "destination_wallet", "voice_sample_id", "transcript_excerpt", "rm_name"],
  "fields_bucketed": ["requested_amount_chf"]
}
```

**Это и есть наш FINMA compliance signal**. UI покажет это side-by-side в "Privacy" панели:
- Left: "What stays local" (полные данные)
- Right: "What goes to AI" (anonymized)

Жюри AMINA сразу увидит — данные клиента **не покидают банк**.

### 5.3: SSE streaming (через curl, не Swagger)

Swagger не показывает SSE правильно. Открой отдельный терминал:

```bash
curl -N -H "Accept: text/event-stream" \
  http://localhost:8000/api/v1/explanations/22222222-2222-2222-2222-222222222204/stream
```

Увидишь как слова приходят прогрессивно:
```
event: message
data: This 

event: message
data: case 

event: message
data: exhibits 

event: message
data: multiple 

event: message
data: risk 

event: message
data: indicators 
...
event: done
data: 
```

**В mock mode** искусственно задержка 25ms между словами — симулирует streaming experience.

**В real mode** chunks приходят по мере того как Claude генерирует — реально fast typing effect.

## Шаг 6: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 5: Claude API integration + streaming explanations

- Added AnthropicClient wrapper with caching + mock fallback
- Added prompt templates with compliance officer persona
- Added ExplanationService orchestrating full pipeline
- Added 3 explanations endpoints (POST, SSE stream, anonymization)
- Anonymizer applied automatically before every LLM call
- 15 endpoints total, backend feature-complete for MVP
"
```

## Чек-лист завершения дня

- [ ] Сервер запускается с `application_ready`
- [ ] `POST /api/v1/explanations/{case_id}` возвращает 4 narrative sections
- [ ] Mock mode warning отображается в логах (или real mode если key задан)
- [ ] `GET .../anonymization` показывает pseudonymized данные
- [ ] SSE streaming через curl показывает progressive chunks
- [ ] Metadata содержит anonymization_applied: true
- [ ] Если real mode: tokens usage логируется
- [ ] Git commit сделан

---

## Что узнал сегодня (теория для джуна)

### Server-Sent Events (SSE) vs WebSockets

**SSE**: server → client, one-way, через HTTP
- Простой код (one endpoint, `event:` lines)
- Auto-reconnect в браузере
- Подходит для streaming ответов (ChatGPT, Claude.ai)
- Это что мы используем

**WebSockets**: bi-directional, persistent connection
- Сложнее в коде (handshake, ping/pong)
- Подходит для chat, multiplayer games

Для нашего случая (Claude → frontend) SSE — правильный выбор. WebSocket мы будем использовать на День 19 для real-time alerts (новый case появился в queue).

### Async generators в Python

```python
async def stream_summary(self, case_id) -> AsyncIterator[str]:
    async for chunk in self.llm.stream(prompt):
        yield chunk
```

`yield` в async function = **async generator**. FastAPI обрабатывает это и отправляет каждый chunk как SSE event.

Это **lazy evaluation**: следующий chunk вычисляется только когда client готов его принять. Если client закрыл connection — generator останавливается, не тратит compute.

### Caching pattern

```python
cache_key = hash(prompt + model + max_tokens)
if cache_key in self._cache and not expired:
    return cached_value, was_cached=True
```

В разработке мы делаем одинаковые запросы тысячи раз. Без кэша — burn tokens. Простой in-memory dict с TTL = idiomatic для MVP.

В production это будет Redis или Memcached. Но pattern такой же — **content-addressed caching**: ключ = hash содержимого, value = ответ.

### Graceful degradation pattern

Каждый external call **должен** иметь fallback:

```python
try:
    return self._client.messages.create(...)
except anthropic.APIError as e:
    logger.error("anthropic_api_error", error=str(e))
    return self._mock_response(prompt)  # ← graceful fallback
```

Если Claude API упал — мы **не падаем**, мы возвращаем mock response. Demo продолжается. Это критично на хакатоне.

### Prompt engineering basics

```python
COMPLIANCE_OFFICER_PERSONA = """You are a senior compliance analyst at a Swiss private bank..."""
```

Хороший prompt имеет:
1. **Role/persona** — кто Claude в этом разговоре
2. **Constraints** — что писать, что не писать
3. **Context** — данные с которыми работать
4. **Format** — как структурировать ответ
5. **Tone** — какой voice использовать

Наши prompts — production-quality. Они **не "хакатонные"** ("be helpful and write a summary"), а **specific**: "60-90 words, prose only, no bullets, reference FINMA, never invent facts".

### Orchestrator pattern

ExplanationService — **orchestrator**. Он не делает ML, не делает LLM, не делает anonymization. Он **координирует**:

```python
ml_result = self.risk_engine.score_case(case_id)
anon_report = self.anonymizer.anonymize(case_data)
prompt = executive_summary_prompt(...)
text = self.llm.complete(prompt)
```

Каждый component **делает одну вещь хорошо** (Single Responsibility Principle). Orchestrator склеивает их в business flow.

Это **сильнейший pattern** для микросервисной архитектуры. На хакатоне когда challenge окажется новым (например "score this XRPL transaction") — мы напишем новый orchestrator или адаптируем существующий **не трогая базовые сервисы**.

### Privacy by design

Anonymizer вызывается **прежде чем prompt уйдёт в Claude**:

```python
anon_report = self.anonymizer.anonymize_case_data(raw_data, client_name=...)
# ↓
prompt = executive_summary_prompt(anonymized_context=anon_report.anonymized)
# ↓
text = self.llm.complete(prompt)  # ← only anonymized data leaves the building
```

Compliance officer может пройти audit:
1. Открыть `/anonymization` endpoint
2. Увидеть точный список — что отправляется в Claude
3. Confirmed — реальные имена клиентов **никогда** не уходят

Это **архитектурное** решение, не "feature". На pitch'е жюри AMINA сразу увидит это в demo: "вот эти данные остаются у вас, вот эти уходят".

---

## Архитектурные решения объяснённые

**Почему mock mode встроен, а не отдельный test framework?**

Реальный production code должен gracefully degrade. Если завтра Anthropic ушёл на 30 минут — наш банк не остановит работу. Mock mode это **architectural feature**, не testing helper.

**Почему prompts в Python коде, а не в YAML?**

Прим тут типобезопасность важнее redactability. Если завтра меняем feature names — IDE сразу покажет где надо обновить prompts. YAML files это compliance rules (которые меняет compliance team), prompts это code (который меняет dev team).

**Почему два endpoint'а — POST и GET stream?**

- POST = synchronous flow (batch processing, audit log export, integration tests)
- GET SSE = UI streaming

Frontend будет использовать **streaming для UI** (визуальный wow), но и POST для **сохранения** explanation в audit log. Два use case = два endpoint.

**Почему мы не используем `function calling` Claude API?**

Function calling добавляет complexity (4-5x больше кода) ради малой пользы для нашего case. Простой text-in / text-out быстрее, дешевле, проще debug'ить. Если на хакатоне challenge потребует tool use — добавим, но не сейчас.

---

## Дальше: День 6 — Database + Audit Log

Завтра делаем:
- **SQLite + SQLModel** (заменим in-memory store)
- **Async database operations**
- **Audit log table** — каждое AI decision сохраняется immutably
- **Migration setup** через Alembic (для production-grade schema evolution)

После Дня 6 backend будет полностью persistent. Это критично для demo — мы сможем показать **history of decisions** и **audit trail**.

Дни 7-14 — это AMINA-specific фичи (voice analysis, behavioral baselines) и подготовка к frontend. После этого начнём React.
