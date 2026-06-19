# Demo Script — Sentinel (3 minutes)

> **Цель**: за 3 минуты показать жюри полный compliance workflow + 4 differentiators.
> **Stakes**: жюри устало, видели 14 команд. Каждые 10 секунд должно происходить что-то новое на экране.

---

## Pre-demo checklist (за 5 минут до выступления)

- [ ] Стек поднят: `docker compose up -d --build` (оба контейнера healthy)
- [ ] Backend отвечает `curl http://localhost:8000/health`, frontend на localhost:3000
- [ ] БД свежая: scoring работает для всех 18 кейсов (тестовый клик на 3 разных типа)
- [ ] Welcome modal **dismissed** (нет всплывашки при показе)
- [ ] Browser zoom: 100% (Cmd+0)
- [ ] DevTools закрыты (F12)
- [ ] Notifications выключены (Do Not Disturb on macOS)
- [ ] Slack/Discord/email скрыты
- [ ] Bookmarks bar спрятан (Cmd+Shift+B)
- [ ] Открыта **только одна** вкладка — localhost:3000
- [ ] Spotlight/clipboard managers выключены
- [ ] Если показ через проектор: проверить external display, разрешение 1920x1080

---

## Setup: what's on screen when you start

**Browser**: localhost:3000, dashboard, Marc Weber case **уже выбран** (открыт справа).

**Не делать**: показывать процесс открытия dashboard, кликов на welcome modal, etc.
Открой Marc Weber заранее — экономишь 15 секунд.

---

## The script

### [0:00 — 0:15] Hook + problem

**Что на экране**: dashboard, Marc Weber case открыт, score 100 critical.

**Что говоришь** (15 секунд, говори чётко):

> "AMINA, Julius Baer, Pictet — каждый день их compliance officers проверяют сотни flagged cases.
> Voice transfers, suspicious trades, on-chain transactions.
>
> Сейчас они работают с black-box AI скорингом — либо доверяют, либо overrideят вслепую.
> Liability на них."

**Action**: пока говоришь — никаких кликов. Дай экрану доказать что у тебя реальный compliance dashboard.

---

### [0:15 — 0:45] The product

**Что на экране**: всё ещё Marc Weber, но теперь делай scroll вниз — показать SHAP, counterfactuals, jurisdictions, privacy panel.

**Что говоришь**:

> "Мы построили Sentinel. Compliance officer видит case, видит **score**,
> видит **почему** — это SHAP. Видит **что нужно изменить** чтобы это approve — counterfactuals.
> Видит **под чью юрисдикцию** это попадает.
> И **что именно** уходит в AI, что остаётся в банке."

**Action**: scroll медленный. Не быстрее чем 1 секция за 5 секунд. Дай камере мобильника жюри захватить.

---

### [0:45 — 1:30] Live demo — Marc Weber

**Что на экране**: вернись наверх к header Marc Weber case. Кликни **Refresh** в браузере (Cmd+R) — это перезагрузит AI streaming.

**Что говоришь** (одновременно со streaming):

> "Marc Weber. Швейцарский клиент, AUM 28 миллионов.
> В воскресенье в 3 утра звонит — 'нужно срочно перевести 8.7 миллионов в Россию,
> мой партнёр ждёт, никому не говорите'.
>
> Sentinel score — **100 из 100, critical**.
>
> Смотрите как AI разворачивает свою оценку." [пауза, дай streaming доехать до конца, ~10 секунд]

**Action**: streaming разворачивается в правом блоке "AI ASSESSMENT". Дай ему доехать. Это **wow moment** — не перебивай.

**Что говоришь дальше** (как только streaming закончился):

> "Ниже — SHAP. Топ-5 рисковых факторов. Amount 15x typical, country risk RU, pressure markers в transcript.
>
> Counterfactuals: 'если бы destination не была Россия и pressure markers были ниже — case бы прошёл'.
>
> Это не black box. Это AI который объясняется."

**Action**: укажи курсором (или ткни мышкой) на конкретные элементы пока говоришь. SHAP bars красные. Counterfactual cards.

---

### [1:30 — 2:00] Jurisdiction killer

**Что на экране**: scroll вниз до **Jurisdiction selector**. Текущий — CH (FINMA).

**Что говоришь**:

> "Теперь главное про AMINA. Они работают в **четырёх юрисдикциях**.
>
> Тот же case — но что если клиент в UAE? Кликаем FSRA..."

**Action**: кликни на **AE** в jurisdiction toggle. Score пересчитывается. Action меняется (или остаётся, но это видно из applicable rules).

> "FSRA — самые строгие правила для virtual assets. Те же данные, другая регуляторная призма.
>
> Compliance team **редактирует YAML файл** — не пишет код."

**Action**: переключи на HK (SFC) ещё раз, чтобы показать что эффект real-time. Не задерживайся.

---

### [2:00 — 2:30] Privacy + architecture

**Что на экране**: scroll до **Data Handling** panel. Кликни "Show details →".

**Что говоришь**:

> "Privacy by design — то что важно FINMA.
>
> **Слева** — что остаётся в банке: имя клиента, точная сумма, voice sample, transcript.
> **Справа** — что уходит в Claude: pseudonym, bucketed amount, masked wallet.
>
> Модель рассуждает о **паттернах**, не о людях.
>
> Compliance officer **аудитит это** перед каждым AI call."

**Action**: укажи на конкретные строки в split-view. "CLIENT_AAF7" вместо "Marc Weber" — это видно.

---

### [2:30 — 3:00] Decision + closing

**Что на экране**: scroll вниз до **Decision Bar**.

**Что говоришь**:

> "Officer принимает решение. AI рекомендует BLOCK.
>
> Соглашаюсь —" [кликни **Block**] "— записано. Immutable audit trail.
>
> Если override — обязателен rationale.
>
> Это compliance system, которой регулятор может **доверять**.
>
> Sentinel. Спасибо."

**Action**: кликни Block. Появится зелёная плашка "Decision recorded".

---

## What jurors might ask

### "Это работает с real Claude API или mock?"

> "Оба. По умолчанию mock — для оффлайн демо. С `ANTHROPIC_API_KEY` в .env — real Claude.
> Streaming, caching, fallback — всё на месте."

### "А что если ваш ML модель ошибётся?"

> "У нас 3 уровня защиты:
> 1. ML score из XGBoost
> 2. Rule-based override для known critical signals (sanctions, mixer proximity)
> 3. Compliance officer с обязательным rationale при override
>
> AI — assistant, не decision maker."

### "Сколько кейсов в день платформа может обработать?"

> "FastAPI async, SQLite сейчас, но архитектура готова к Postgres.
> Conservative estimate — 10K cases/день на single instance. Scale horizontally без изменений."

### "Что вы делали не вы, а кто-то ещё?"

> "ML базовые библиотеки — XGBoost, SHAP, DiCE.
> Frontend framework — Next.js.
> Всё остальное — мы: schema, business logic, jurisdiction engine, anonymizer, UI design system, integrations."

### "А почему не sklearn?"

> "XGBoost дал лучший ROC-AUC на нашем training set (1.0 vs 0.98 для sklearn RandomForest).
> Плюс XGBoost-специфичная интеграция с SHAP TreeExplainer — быстрее, точнее."

### "Что вы сделаете на хакатоне если выиграете challenge?"

> "Зависит от challenge. AMINA — добавим voice biometrics layer.
> Julius Baer — investment recommendation walkthrough с PRIIP/MiFID compliance.
> Ripple — XRPL escrow с RLUSD smart contracts.
>
> Backend готов ко всем трём — нужно только feature extractors + UI skin."

---

## Recovery plans — что делать если что-то ломается

### Backend упал mid-demo

**Что говорить**:
> "Локальный demo issue, продолжу со скриншотами..."

**Что делать**: открой `pitch/screenshots/` — есть PNG'и с каждой стадии. Жюри не заметит разницы.

### Streaming не начался

**Что делать**: refresh страницу (Cmd+R), case останется выбран — streaming перезапустится.

### Score = 0 для Marc Weber

**Причина**: модель не натренирована. **Что сказать**:
> "One second, model wasn't loaded — re-running scoring..."

**Что делать**: кликни на другой case, потом обратно на Marc Weber — auto-score сработает.

### Не работает интернет

**Что сказать**: ничего, не паникуй. Mock mode работает без интернета. Welcome modal не должна об этом упоминать.

### Time остался — что добавить

**Топ-3 кандидата** (по 30 секунд):

1. **Audit trail demo** — `curl http://localhost:8000/api/v1/audit | head` в терминале. Показывает все события.
2. **Different case type** — кликни Mei Lin Tan OFAC sanctions case. Показывает что система работает не только для voice.
3. **GitHub repo** — переключись на github.com/SteveDok22/swisshacks-2026, README выглядит как product page.

---

## Tone guidelines

- **Confident, не arrogant**: "we built" not "we're going to build"
- **Specific numbers**: "100/100", "8.7 million", "4 jurisdictions" — не "high score", "lots of money"
- **Active voice**: "Sentinel scores" not "the case gets scored"
- **No hedging**: убрать "kind of", "sort of", "we tried to"
- **Pauses are powerful**: когда streaming идёт, **молчи**. Дай экрану work.

---

## Practice protocol

### Run 1 — solo (no audience)

- Goal: попасть в 3 минуты
- Засекай. Если 3:30 — режь contractions, убирай filler words
- Если 2:30 — добавь pauses, не торопись

### Run 2 — solo + recording

- Запиши себя через QuickTime / OBS
- Пересмотри через 10 минут
- Найди 3 момента где можно sharper

### Run 3 — с командой

- Один из вас pitches, остальные изображают жюри
- Они задают 3 вопроса из списка выше
- Если ты замялся хоть раз — ещё прогон

### Run 4 — в день перед хакатоном

- Финальный прогон, full setup (laptop + projector)
- Если что-то ломается — fix или recovery plan
