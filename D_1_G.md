# День 1: Запуск проекта

Это пошаговое руководство для первого дня. Делай команды по порядку, после каждой проверяй что вывод правильный.

## Что мы сегодня сделаем

1. Распакуем boilerplate в удобное место
2. Установим Python зависимости через `uv`
3. Запустим FastAPI сервер локально (без Docker)
4. Запустим тот же сервер через Docker
5. Создадим Git репозиторий и сделаем первый commit

Окружение уже готово: Python 3.12.8, Node 25.6.1, Docker 29.4.3, uv 0.11.14, pnpm 11.1.1, git 2.53.0.

---

## Шаг 1: Распаковка архива

```bash
# Создай папку для проектов если ещё нет
mkdir -p ~/Projects
cd ~/Projects

# Распакуй архив (предполагаю что скачал в Downloads)
unzip ~/Downloads/swisshacks-2026.zip -d 

# Перейди в проект
cd swisshacks-2026

# Посмотри структуру
ls -la
```

Должен увидеть: `backend/`, `frontend/`, `docker/`, `scripts/`, `docs/`, `docker-compose.yml`, `README.md`, `.gitignore`, `DAY_1_GUIDE.md`.

---

## Шаг 2: Установка backend зависимостей

```bash
# Заходим в backend
cd backend

# uv создаст virtualenv (виртуальное окружение Python)
uv venv

# Активируем окружение
source .venv/bin/activate
```

Должен увидеть `(.venv)` в начале строки терминала.

**Что такое venv** — изолированная папка с Python и пакетами только для этого проекта. Без неё все зависимости устанавливаются глобально и проекты начинают конфликтовать.

```bash
# Установка зависимостей
uv pip install -r pyproject.toml
```

Это займёт 30-60 секунд. uv в 10-100 раз быстрее pip.

**Если получишь ошибку с `dice-ml`** (известная проблема на Apple Silicon с Python 3.12) — установи всё кроме неё, потом разберёмся:

```bash
uv pip install \
  "fastapi>=0.115.0" \
  "uvicorn[standard]>=0.32.0" \
  "pydantic>=2.9.0" \
  "pydantic-settings>=2.5.0" \
  "sse-starlette>=2.1.0" \
  "sqlmodel>=0.0.22" \
  "aiosqlite>=0.20.0" \
  "xgboost>=2.1.0" \
  "scikit-learn>=1.5.0" \
  "shap>=0.46.0" \
  "numpy>=1.26.0" \
  "pandas>=2.2.0" \
  "joblib>=1.4.0" \
  "anthropic>=0.39.0" \
  "structlog>=24.4.0" \
  "python-multipart>=0.0.12" \
  "httpx>=0.27.0"
```

---

## Шаг 3: Настройка .env

```bash
# Скопируй шаблон
cp .env.example .env
```

ANTHROPIC_API_KEY пока **не нужен** — используем на День 5. Оставь как есть.

Если хочешь получить ключ заранее: https://console.anthropic.com → Settings → API Keys → Create Key.

---

## Шаг 4: Запуск локально

```bash
# Убедись что ты в backend/ и .venv активирован
# Должен видеть (.venv) в строке терминала

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Должен увидеть:
```
INFO: Uvicorn running on http://0.0.0.0:8000
[info] application_starting   app_name='SwissHacks Risk Intelligence Platform'
[info] application_ready
INFO: Application startup complete.
```

**Что значит `--reload`** — если ты меняешь код, сервер автоматически перезапускается. Очень удобно при разработке.

---

## Шаг 5: Проверка endpoints

**НЕ закрывай терминал с сервером**. Открой **новое окно терминала** (Cmd+T) и попробуй:

```bash
curl http://localhost:8000/health
```

Ожидаемый вывод:
```json
{"status":"healthy","app":"SwissHacks Risk Intelligence Platform"}
```

```bash
curl http://localhost:8000/
```

Ожидаемый вывод:
```json
{"app":"SwissHacks Risk Intelligence Platform","version":"0.1.0","docs":"/docs"}
```

**Самое важное** — открой в браузере:
- **http://localhost:8000/docs**

Это автоматически сгенерированная Swagger документация — интерактивный UI где можно прямо в браузере вызывать API endpoints. Это один из killer features FastAPI.

Останови сервер в первом терминале (Ctrl+C).

---

## Шаг 6: Запуск через Docker

Убедись что **Docker Desktop запущен** — иконка кита 🐳 в верхней панели Mac.

```bash
# Деактивируй venv (не нужен внутри Docker)
deactivate

# Перейди в корень проекта
cd ..

# Запусти через Docker Compose
docker compose up backend
```

**Что произойдёт**:
1. Docker начнёт собирать образ (первый раз ~3-5 минут)
2. Будет много логов сборки — нормально
3. В конце увидишь логи запуска (те же что в Шаге 4)

**Проверь**: Открой http://localhost:8000/docs в браузере — должен увидеть тот же Swagger UI.

Останови (Ctrl+C).

**В чём разница между Шагом 4 и 6**:
- Шаг 4 — запуск напрямую на Mac. Быстро, удобно для разработки.
- Шаг 6 — запуск в контейнере Docker. Изолированно, повторяемо, точно так же запустится у любого члена команды.

На хакатоне используем Шаг 4 для разработки, Docker — для финального тестирования и демо.

---

## Шаг 7: Git репозиторий

```bash
git init
```

Настрой Git если ещё не делал:
```bash
git config --global user.name "Stiven Ntoktorov"
git config --global user.email "твой@email.com"
```

```bash
git add .
git status
```

Должен увидеть зелёным список файлов (без `.env`, `__pycache__`, `.venv/` — `.gitignore` их исключает).

```bash
git commit -m "Day 1: Initial boilerplate with FastAPI + Docker"
```

### Опционально: создать репо на GitHub

1. https://github.com/new
2. Name: `swisshacks-2026`
3. Выбери **Private** (важно, чтобы другие команды не увидели подготовку)
4. **НЕ ставь** галочки на «Add README», «.gitignore», «license» — у нас уже есть
5. Create repository

```bash
git remote add origin https://github.com/ТВОЙ_USERNAME/swisshacks-2026.git
git branch -M main
git push -u origin main
```

Если стоит 2FA — нужен **Personal Access Token**:
Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token → scope `repo`.

---

## Чек-лист завершения дня

- [ ] Архив распакован в `~/Projects/swisshacks-2026/`
- [ ] `uv venv` создан в `backend/.venv/`
- [ ] Зависимости установлены
- [ ] FastAPI запускается локально через `uvicorn`
- [ ] `http://localhost:8000/docs` открывается и показывает Swagger UI
- [ ] FastAPI запускается через `docker compose up backend`
- [ ] Git репо инициализирован, первый commit сделан

---

## Если что-то не работает

Расскажи мне:
1. Какую команду запустил
2. Какой вывод получил (полностью)
3. На каком шаге

Не пытайся «пофиксить наугад» — это сломает структуру.

---

## Что узнал сегодня (теория для джуна)

**FastAPI** — современный async web framework для Python. Пишешь функцию с типами → получаешь автоматическую валидацию + документацию.

**Pydantic Settings** — типобезопасная конфигурация. Все настройки в одном месте, валидируются на старте.

**structlog** — структурированное логирование. Вместо `print("error: something")` пишешь `logger.error("payment_failed", user_id=123, amount=50)`. В деве — цветной вывод, в проде — JSON.

**uv** — новый Python package manager. В 10-100x быстрее pip.

**Docker Compose** — оркестратор контейнеров. `docker compose up` поднимает весь стек одной командой.

**Multi-stage Dockerfile** — образ строится в 2 этапа: builder (с компилятором, ~1GB) и runtime (только бинарники, ~300MB).

**Lifespan handler** — FastAPI вызывает наш `lifespan()` при старте/остановке. Здесь грузим ML модели в память, коннектимся к БД, закрываем соединения.

**virtual environment (venv)** — изолированная папка с Python пакетами для одного проекта.

---

## Дальше: День 2

Завтра делаем:
- Pydantic schemas для cases, scoring, audit
- Первый API router (`/api/v1/cases`)
- In-memory mock data
- Первые работающие endpoint'ы с примерами AMINA cases

Когда День 1 завершён — напиши «День 1 готов», получишь архив с продолжением.
