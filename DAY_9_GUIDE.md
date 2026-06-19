# День 9: Rich Mock Data + Welcome Experience

Сегодня превратили "функциональный prototype" в **demo-ready продукт**. У тебя теперь 18 разнообразных кейсов, welcome modal для первого визита, и top-level README уровня "это продукт".

## Что построили

1. **18 разнообразных mock cases** (было 6) — все 4 jurisdictions, все 3 типа, все 4 risk levels
2. **Welcome modal** — автоматически показывается при первом визите, объясняет продукт + предлагает demo flow
3. **About page** на `/about` — для GitHub showcase и нового team member
4. **Top-level README** обновлённый — что мы строим, для кого, как запустить

## Распределение новых mock cases

| Категория | Количество | Детали |
|---|---|---|
| Social Engineering (AMINA) | 8 | 2 critical, 2 high, 2 medium, 2 low |
| Investment Recommendation (JB) | 4 | разные allocations, EU/CH/AE |
| XRPL Transaction (Ripple) | 6 | включая OFAC sanctions hit, mixer proximity |
| **Total** | **18** | |

| Jurisdiction | Cases |
|---|---|
| CH (FINMA) | 9 |
| EU (MiCA) | 3 |
| HK (SFC) | 4 |
| AE (FSRA) | 2 |

| Status | Cases |
|---|---|
| pending | 13 |
| in_review | 2 |
| resolved | 3 |

## Список изменений

### Новые файлы
- `frontend/src/components/WelcomeModal.tsx` — onboarding modal
- `frontend/src/app/about/page.tsx` — about/showcase page

### Изменённые файлы
- `backend/app/services/mock_data.py` — переписан, 18 cases вместо 6
- `frontend/src/app/page.tsx` — подключён WelcomeModal
- `README.md` — top-level showcase для GitHub

### Не трогать
- `backend/.env`, `backend/.venv/`, `.git/`
- `backend/data/models/social_engineering_v1.joblib` — модель остаётся
- **`backend/data/risk_platform.db`** — **ВАЖНО**: нужно удалить чтобы новые cases заселились

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -qo ~/Downloads/swisshacks-2026-day9.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
```

## Шаг 2: КРИТИЧНО — удали старую БД

Чтобы новые cases засеялись:

```bash
rm backend/data/risk_platform.db
```

Без этого ты увидишь старые 6 cases — backend пропускает seed если БД уже заполнена.

## Шаг 3: Запусти backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

В логах должен увидеть:
```
seed_completed     client_count=10  case_count=18
```

## Шаг 4: Запусти frontend (другой терминал)

```bash
cd ~/Documents/Projects/swisshacks-2026/frontend
npm run dev
```

## Шаг 5: Очисти localStorage и открой dashboard

Welcome modal показывается только при **первом визите** (через localStorage flag).
Чтобы увидеть его сейчас, открой http://localhost:3000 и:

1. Открой DevTools (F12 / Cmd+Opt+I)
2. Console → введи:
   ```js
   localStorage.removeItem('sentinel.welcome-seen')
   ```
3. Перезагрузи страницу (Cmd+R)

Welcome modal должен появиться через ~400ms после загрузки.

## Шаг 6: Проверь Case Queue

В средней колонке теперь должно быть **18 cases** (а не 6). Прокрути список:
- Сверху — 2 critical cases (Marc Weber, Klaus Hofmann)
- Затем high (Hans Müller, Mei Lin Tan, Ahmed Al-Rashid)
- Затем medium и low
- Внизу — resolved cases

Кейсы покрывают **все 3 типа** (Social Engineering, Investment Recommendation, XRPL) и **все 4 jurisdictions**.

## Шаг 7: Попробуй разнообразные кейсы

Раньше demo был "click Marc Weber → wow". Теперь у тебя **много вариантов**:

- **OFAC sanctions hit** (XRPL case Mei Lin) — critical из-за sanctions match
- **PEP client** (Klaus Hofmann) — EU jurisdiction, MiCA rules
- **Tokenized RWA** (Ahmed Al-Rashid) — AE/FSRA, инвестиционная рекомендация
- **Internal transfer** (Wei Chen) — XRP между его кошельками, low risk

Каждый показывает разный аспект платформы.

## Шаг 8: Открой /about

http://localhost:3000/about — отдельная страница для GitHub showcase. Это что увидит:
- Жюри если откроет твой GitHub
- Новый team member когда зайдёт первый раз
- Hiring manager если поделишься ссылкой

## Шаг 9: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 9: Rich mock data + welcome experience

- 18 diverse mock cases across all jurisdictions and case types
- Welcome modal with onboarding flow for first-time visitors
- About page for GitHub showcase
- Top-level README updated as product showcase
- Backend seeds 18 cases on fresh DB
"
```

## Чек-лист завершения дня

- [ ] Старая БД удалена (`rm backend/data/risk_platform.db`)
- [ ] Backend запускается с `seed_completed case_count=18`
- [ ] Case Queue показывает 18 cases
- [ ] Welcome modal появляется при первом визите (после очистки localStorage)
- [ ] `/about` страница открывается
- [ ] README на корневом уровне обновлён
- [ ] Git commit сделан

---

## Что узнал сегодня (теория для джуна)

### Mock data quality matters for demo

Раньше 6 однообразных cases → жюри видело 2-3 и думало "понял идею".
Теперь 18 разнообразных → каждый клик открывает что-то новое. Это **критично** для 3-минутного pitch'а: тебе нужно показать **широту**, не только один сценарий.

Принцип: **mock data is part of the product**. Не "временные данные", а демонстрация что платформа реально универсальная.

### Welcome modal с localStorage

```ts
useEffect(() => {
  const seen = localStorage.getItem(STORAGE_KEY);
  if (!seen) {
    setTimeout(() => setOpen(true), 400);
  }
}, []);
```

Показываем только **один раз**. Compliance officer не должен видеть onboarding каждый день. Но **первый раз** — обязательно: что это, как работать, куда смотреть.

400ms задержка — чтобы main UI прогрузился. Иначе welcome modal появится поверх пустого экрана = unprofessional.

### Top-level README уровня "продукт", не "код"

Сравни:
- ❌ "This repo contains the source code for..."
- ✅ "Sentinel — Explainable AI for compliance officers"

Первое — для разработчиков. Второе — для **всех**: жюри, hiring managers, team members. README — это **обложка** твоего продукта.

Структура продуктового README:
1. Что это (одно предложение)
2. Что делает (3-5 пунктов)
3. Почему это different
4. Architecture overview (диаграмма)
5. Quick start (3 команды)
6. Demo flow
7. Tech stack

### Idempotent seed pattern

```python
async def seed_if_empty(session):
    result = await session.execute(select(ClientDB).limit(1))
    if result.scalar_one_or_none() is not None:
        return False  # already seeded
    # ... seed ...
    return True
```

Seed запускается **каждый раз** при старте, но реально работает только если БД пустая. Это безопасно: не дублирует данные, не падает на повторных запусках.

Чтобы пересеять — нужно явно удалить `.db` файл. Это **намеренное** unfriendly UX: предотвращает случайный data loss.

---

## Дальше: День 10 — Pitch & Demo materials

Завтра делаем:
- **Pitch deck draft** в Markdown (8-10 slides)
- **Demo script** — 3-минутный walkthrough с конкретными timings
- **Team onboarding guide** — "что делать когда подключился к проекту"
- **Screenshots** для Slack команды (через ваш Mac, не у меня)

После Дня 10 у тебя будет **полный набор материалов** для команды и pitch'а. Можно приходить на хакатон.

Скажи "День 9 готов" + хочешь ли что-то отдельно подсветить или поправить в mock cases.
