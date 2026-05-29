# День 7: Frontend Foundation — Next.js + Design System

Сегодня построили фундамент frontend'а: рабочий dashboard, который читает реальные данные из backend. К концу дня у тебя есть **скриншот-готовый продукт** для команды.

## Что построили

1. ✅ Next.js 15 + TypeScript + Tailwind проект
2. ✅ Swiss Institutional design system (design tokens, fonts, цвета)
3. ✅ Typed API client (подключён ко всем 19 backend endpoints)
4. ✅ Sidebar навигация с wordmark "Sentinel"
5. ✅ Case Queue — список cases, отсортированный по риску
6. ✅ Case Detail panel — базовая (SHAP/counterfactuals будут в Day 8)
7. ✅ TanStack Query для data fetching

`next build` проходит успешно — у тебя точно соберётся.

## Список изменений в проекте

### Новые файлы (всё в `frontend/`)
- `package.json`, `tsconfig.json`, `next.config.mjs`, `postcss.config.mjs`, `tailwind.config.ts`
- `README.md` — инструкция по запуску
- `src/app/layout.tsx` — root layout
- `src/app/page.tsx` — главная (3-pane workspace)
- `src/app/globals.css` — design tokens + fonts
- `src/components/QueryProvider.tsx`
- `src/components/layout/Sidebar.tsx`
- `src/components/cases/CaseQueue.tsx`
- `src/components/cases/CaseDetailPanel.tsx`
- `src/components/ui/RiskBadge.tsx`
- `src/components/ui/RiskScore.tsx`
- `src/lib/api.ts` — typed API client
- `src/lib/utils.ts` — форматирование + risk colors
- `src/types/api.ts` — типы под backend

### Не трогать
- `backend/` — без изменений сегодня
- `backend/.env`, `backend/.venv/`, `.git/`

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -qo ~/Downloads/swisshacks-2026-day7.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
ls frontend/src/
```

Должен увидеть: `app`, `components`, `lib`, `types`.

## Шаг 2: Запусти backend (в первом терминале)

Frontend без backend покажет ошибку "Failed to load cases". Сначала backend:

```bash
cd ~/Documents/Projects/swisshacks-2026/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Оставь этот терминал работать. Проверь http://localhost:8000/health — должен вернуть `{"status":"healthy"}`.

## Шаг 3: Установи frontend зависимости (во втором терминале)

Открой **новый терминал** (Cmd+T в Terminal):

```bash
cd ~/Documents/Projects/swisshacks-2026/frontend
npm install
```

Это займёт 1-2 минуты — скачиваются Next.js, React, Tailwind и т.д. Около 300MB в node_modules (это нормально для Next.js).

Если `npm` не установлен — поставь Node.js 20+ с https://nodejs.org/ (LTS версия).

## Шаг 4: Запусти frontend

```bash
npm run dev
```

Должен увидеть:
```
▲ Next.js 15.1.6
- Local:        http://localhost:3000
✓ Starting...
✓ Ready in 2.1s
```

## Шаг 5: Открой в браузере

Открой **http://localhost:3000**

Ты увидишь трёхколоночный layout:

**Левая колонка** — Sidebar:
- Wordmark "Sentinel / Risk Intelligence"
- Навигация: Case Queue (активна), Live Alerts, Audit Log, Jurisdictions
- Внизу: Anna Müller, Compliance Officer

**Средняя колонка** — Case Queue:
- 6 cases отсортированных по риску (critical наверху)
- Каждая строка: score (моноширинный), risk badge, summary, jurisdiction, время
- Marc Weber CHF 8.7M будет наверху (critical 99 после scoring) — но сначала покажется "unscored" пока не нажмёшь

**Правая колонка** — Case Detail:
- Пустая с надписью "Select a case to review"
- При клике на case → детали: header со score, case data, placeholder для Day 8

## Шаг 6: Протестируй взаимодействие

1. **Кликни на любой case** в средней колонке → правая панель покажет детали
2. **Обрати внимание на анимацию** — строки появляются с staggered fade-in
3. **Hover на строки** — подсветка
4. **Выбранный case** — подсвечен accent-цветом + левый bar

**Заметка про scores**: некоторые cases покажут score сразу (они были scored в mock data), Marc Weber (extreme case) покажет "—" пока его не проскорят. В Day 8 мы добавим кнопку "Score now" и SHAP визуализацию.

## Шаг 7: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 7: Frontend foundation — Next.js dashboard

- Next.js 15 + TypeScript + Tailwind setup
- Swiss Institutional design system (Geist + IBM Plex Mono)
- Typed API client for all 19 backend endpoints
- Sidebar navigation + Case Queue + Case Detail panel
- TanStack Query data fetching
- Risk-sorted case list reading live from FastAPI
"
```

## Чек-лист завершения дня

- [ ] `npm install` прошёл без критичных ошибок
- [ ] Backend запущен на :8000
- [ ] Frontend запущен на :3000
- [ ] Открывается http://localhost:3000
- [ ] Видишь Sidebar + Case Queue + Detail panel
- [ ] Case Queue показывает 6 cases из backend
- [ ] Клик на case открывает детали справа
- [ ] Анимация строк работает
- [ ] Git commit сделан

## Если "Failed to load cases"

Значит frontend не достучался до backend. Проверь:
1. Backend запущен? `curl http://localhost:8000/health`
2. Backend на порту 8000? (не 8001)
3. В консоли браузера (F12 → Console) есть ошибки?

Proxy настроен в `next.config.mjs`: `/api/backend/*` → `localhost:8000/api/v1/*`. Если backend на другом порту — поправь там.

---

## Что узнал сегодня (теория для джуна)

### Почему НЕ Inter / shadcn/ui as-is

Frontend-design гайд прямо предупреждает против "generic AI aesthetic" — Inter, дефолтный shadcn, фиолетовые градиенты. Это то, что сделают 13 из 15 команд. Мы взяли:
- **Geist** (характерный, технический) вместо Inter
- **IBM Plex Mono** для чисел — банковская точность
- Кастомные компоненты на Radix primitives вместо дефолтного shadcn

Это даёт **запоминающийся** UI, который выглядит как реальный enterprise-продукт, а не хакатон-демо.

### Design tokens в Tailwind config

Все цвета/шрифты/spacing определены **один раз** в `tailwind.config.ts`:
```ts
colors: {
  ink: { DEFAULT, soft, muted, faint },     // монохром текст
  paper: { DEFAULT, raised, sunken, line },  // монохром фон
  risk: { low, medium, high, critical },     // семантика риска
}
```

Меняешь токен → меняется весь UI. Это **single source of truth** для дизайна. Команда не гадает "какой оттенок серого" — берёт `text-ink-muted`.

### API proxy через Next.js rewrites

```js
async rewrites() {
  return [{ source: '/api/backend/:path*',
            destination: 'http://localhost:8000/api/v1/:path*' }];
}
```

Frontend вызывает `/api/backend/cases`, Next.js проксирует на `localhost:8000/api/v1/cases`. Зачем:
- Нет хардкода localhost в коде
- Нет CORS проблем (запрос идёт на тот же origin)
- В проде меняешь только rewrite, код не трогаешь

### TanStack Query

```ts
const { data, isLoading, error } = useQuery({
  queryKey: ["cases"],
  queryFn: () => casesApi.list(),
});
```

Это не просто fetch. TanStack Query даёт:
- Автоматический кэш (повторный заход на страницу — мгновенно)
- Loading/error states из коробки
- Refetch, retry, stale-while-revalidate
- Дедупликация (два компонента запросят cases → один HTTP запрос)

Индустриальный стандарт для data fetching в React.

### Server vs Client Components

Next.js 15 App Router по умолчанию рендерит на сервере. Но компоненты с интерактивностью (`useState`, `useQuery`, `onClick`) должны быть client — отмечаем `"use client"` наверху файла.

- `layout.tsx` — server (статичный)
- `page.tsx` — client (есть useState для selectedCaseId)
- `CaseQueue.tsx` — client (useQuery + onClick)

### Staggered animation

```tsx
style={{ animationDelay: `${index * 30}ms` }}
className="animate-slide-up opacity-0"
```

Каждая строка появляется на 30ms позже предыдущей → волна сверху вниз. Один хорошо срежиссированный page-load эффект (совет из frontend гайда) даёт больше "wow" чем десяток мелких микро-анимаций.

---

## Дальше: День 8 — Case Detail полностью

Завтра наполним правую панель — это **сердце demo**:
- **SHAP Viewer** — горизонтальный bar chart вкладов features (Recharts, кастомный стиль)
- **Counterfactuals** — карточки "что изменить чтобы approve"
- **Streaming AI explanation** — текст появляется прогрессивно (SSE, наш wow-moment)
- **Anonymization split-view** — "что остаётся локально / что уходит в AI"
- **Jurisdiction comparison** — toggle CH/EU/HK/AE, live пересчёт
- **Decision flow** — кнопки Allow/Escalate/Block + rationale modal

После Day 8 у тебя будет **полный demo flow** от queue до решения — то, что показывают жюри.
