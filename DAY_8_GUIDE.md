# День 8: Case Detail — сердце demo

Сегодня наполнили правую панель тем, что показывают жюри. У тебя теперь **полный demo flow**: от выбора case до принятия решения.

## Что построили

6 новых компонентов в правой панели:

1. **StreamingExplanation** — AI summary с typing effect (SSE из Day 5)
2. **SHAPViewer** — горизонтальные bar charts вкладов features
3. **CounterfactualsViewer** — "что нужно изменить чтобы approve"
4. **PrivacyPanel** — split-view "что остаётся локально / что уходит в AI"
5. **JurisdictionSelector** — CH/EU/HK/AE toggle с live пересчётом
6. **DecisionBar** — sticky bottom: Allow / Step-up / Escalate / Block + rationale modal

`next build` прошёл: 20.2 KB страница, 0 TypeScript ошибок.

## Список изменений в проекте

### Новые файлы (всё в `frontend/src/`)
- `lib/useStreamingText.ts` — хук для SSE streaming
- `components/cases/SHAPViewer.tsx`
- `components/cases/StreamingExplanation.tsx`
- `components/cases/CounterfactualsViewer.tsx`
- `components/cases/PrivacyPanel.tsx`
- `components/cases/JurisdictionSelector.tsx`
- `components/cases/DecisionBar.tsx`

### Изменённые файлы
- `components/cases/CaseDetailPanel.tsx` — переписан, теперь связывает все 6 компонентов

### Не трогать
- `backend/` — без изменений сегодня
- `.env`, `.venv/`, `.git/`

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -qo ~/Downloads/swisshacks-2026-day8.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
```

## Шаг 2: Backend без изменений — просто запусти

В первом терминале:
```bash
cd ~/Documents/Projects/swisshacks-2026/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Шаг 3: Frontend — никаких новых npm пакетов

Я **не добавлял** новые dependencies — использовал только то что уже было после Day 7. Во втором терминале:

```bash
cd ~/Documents/Projects/swisshacks-2026/frontend
npm run dev
```

Открой **http://localhost:3000**

## Шаг 4: Demo flow

Это и есть твой будущий **3-минутный pitch**. Пройди его сам:

### 4.1 — Выбери Marc Weber case (extreme)

В Case Queue (средняя колонка) найди:
> Voice call requesting CHF 8.7M to unknown wallet — Sunday 3am

Кликни на него.

### 4.2 — AI Assessment появляется streaming-ом

Сразу в правой панели начнётся "AI thinking":
- Sparkles иконка пульсирует
- "analyzing…" индикатор
- Текст появляется слово за словом
- Курсор мигает в конце пока идёт generation

Текст что-то вроде: *"This case exhibits multiple risk indicators that warrant elevated scrutiny..."*

**Это и есть наш wow-moment**. Длится 8-12 секунд в mock mode, в real Claude mode — fluid typing.

### 4.3 — SHAP Factors

Под AI Assessment — bar chart top 5 features:
- Красные бары = increase risk
- Зелёные = decrease risk
- Каждая строка с human label ("Amount is 15.4x typical")
- Tabular numbers справа

Анимация: бары появляются с staggered delay.

### 4.4 — Alternative Scenarios (counterfactuals)

Для high/critical case → блок "Alternative Scenarios". 3 карточки типа:
> *Scenario 1: If destination were lower-risk country and fewer pressure markers — this case would be approved.*

Если case low/medium — этот блок не показывается (правильное поведение).

### 4.5 — Jurisdiction Toggle (demo killer)

4 кнопки: CH (FINMA), EU (MiCA), HK (SFC), AE (FSRA). Каждая показывает:
- Adjusted score под этой юрисдикцией
- Recommended action

**Demo moment**: переключи на AE — увидишь что тот же case под FSRA даёт более строгое action из-за strict modifiers. Это прямой ответ на AMINA cross-jurisdictional pain point.

Под кнопками — applicable rules для текущей юрисдикции (Travel Rule threshold, EDD requirements).

### 4.6 — Privacy Panel (FINMA compliance)

Блок "Data Handling". Кликни "Show details →":

**Left column** — Stays Local:
- client_name, voice_sample_id, transcript_excerpt, rm_name, destination_wallet

**Right column** — Goes to AI:
- client_pseudonym: CLIENT_AAF7
- requested_amount_chf: CHF 5M-10M
- destination_wallet: 0xUN****9012
- (8 первых полей anonymized)

**Жюри сразу видит**: команда понимает FINMA data sovereignty.

### 4.7 — Decision Bar (нижний sticky)

4 кнопки: Allow / Step-up Verification / Escalate / Block.

Подсказка над ними: *"AI suggests: Block"* — выделено небольшим ring'ом на соответствующей кнопке.

**Сценарий A — соглашаешься с AI**:
- Кликни Block
- Decision сразу записывается
- Появляется зелёное подтверждение: *"Decision recorded · Immutably logged to audit trail"*

**Сценарий B — override**:
- Кликни Allow (overrides Block)
- Появляется textarea для rationale
- Заголовок: *"AI suggested Block, you're recording Allow"*
- Введи минимум 10 символов rationale
- Кликни "Record decision"
- Подтверждение

После recording — Case Queue обновится (case теперь resolved/in_review).

## Шаг 5: Проверь в Swagger что decision записался

В третьем терминале:
```bash
curl -s "http://localhost:8000/api/v1/audit?event_type=decision_recorded&page_size=5" | python3 -m json.tool
```

Или открой http://localhost:8000/docs → `GET /api/v1/audit`. Увидишь твоё recorded decision с full payload.

## Шаг 6: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 8: Complete case review flow — SHAP + Counterfactuals + Streaming + Decision

- StreamingExplanation: live AI typing via SSE
- SHAPViewer: horizontal bar chart of feature contributions
- CounterfactualsViewer: 'what would change the decision' cards
- PrivacyPanel: split-view of what goes to AI vs stays local
- JurisdictionSelector: CH/EU/HK/AE live recomputation
- DecisionBar: 4-action picker with override rationale flow
- Complete demo flow from queue to immutable decision
"
```

## Чек-лист завершения дня

- [ ] `npm run dev` запускается без ошибок
- [ ] AI Assessment появляется streaming при выборе case
- [ ] SHAP bar chart показывает 5 features с цветами
- [ ] Для high/critical — видны Alternative Scenarios
- [ ] Jurisdiction toggle меняет score при переключении CH→AE
- [ ] Privacy Panel разворачивается и показывает split-view
- [ ] Decision bar: согласие с AI → instant recording
- [ ] Decision bar: override → rationale required
- [ ] После recording — Case Queue refreshes
- [ ] Git commit сделан

---

## Что узнал сегодня (теория для джуна)

### SSE через EventSource

```ts
const source = new EventSource(url);
source.addEventListener("message", (e) => setText(prev => prev + e.data));
source.addEventListener("done", () => source.close());
```

EventSource — встроенный браузерный API для SSE. Авто-reconnect, обработка ошибок, простой interface. **Не нужны библиотеки**.

Альтернатива — WebSocket — для нашего случая overkill (нужен только server→client).

### Custom hooks для side effects

`useStreamingText` инкапсулирует:
- State (text, isStreaming, isDone, error)
- Lifecycle (start, reset, auto-cleanup)
- Event handling

Компонент `StreamingExplanation` использует его без знания деталей SSE:
```ts
const { text, isStreaming, start, reset } = useStreamingText(url);
```

Это **паттерн custom hook** — переиспользуемая логика без классов.

### Optimistic UI с React Query mutations

```ts
const mutation = useMutation({
  mutationFn: decisionsApi.record,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ["cases"] });
    queryClient.invalidateQueries({ queryKey: ["case", caseId] });
  },
});
```

`invalidateQueries` после успеха → автоматический refetch. Cases queue обновится без manual reload. Это **declarative data flow**.

### Conditional rendering как documentation

```tsx
{(effectiveLevel === "high" || effectiveLevel === "critical") && (
  <CounterfactualsViewer caseId={caseId} />
)}
```

Counterfactuals **не имеют смысла** для low-risk cases. Условный рендер вместо показа пустого блока. Это **business logic в UI**.

### CSS variables через Tailwind

```ts
// tailwind.config.ts
risk: { low: "#15803d", "low-bg": "#f0fdf4", ... }
```

Используется как `text-risk-low`, `bg-risk-low-bg`. Меняешь токен → меняется весь UI. **Design tokens** в чистом виде.

### Sticky bottom decision bar — UX detail

```tsx
<div className="flex flex-col h-full">
  <div className="shrink-0 ...">Header</div>
  <div className="flex-1 overflow-y-auto ...">Scrollable content</div>
  <DecisionBar />  {/* shrink-0 implicit, always visible */}
</div>
```

Flex column layout: header sticky top, content scrolls, decision sticky bottom. Officer **никогда не теряет** доступ к решению — даже на длинной странице.

---

## Архитектурные решения объяснённые

**Почему single-page scroll, а не tabs?**

Tabs разрывают narrative flow. Compliance officer должен **проходить** через case как через статью: header → AI summary → почему → альтернативы → юрисдикция → privacy → решение. Это естественный когнитивный поток.

Tabs хороши когда секции независимы (Profile / Settings / Billing). У нас все секции — **части одного решения**.

**Почему scoring auto-runs при выборе?**

Compliance officer не должен думать "а надо ли мне нажать Score". Случай открыт → AI работает. Если уже scored — backend кэширует, повторный запрос мгновенный.

**Почему override rationale в inline textarea, а не модал?**

Модал = прерывание. Inline = continuation. Officer продолжает thinking в том же контексте, не теряет state. Это критично когда decision важное.

**Почему Privacy Panel collapsed по умолчанию?**

Compliance officer уже **знает** что мы FINMA-compliant (видит badge). Детали важны для **аудита и pitch'а**, не для повседневной работы. Expand on demand.

**Почему animation delays staggered, а не одновременные?**

Одновременные = chaos. Staggered (30-80ms между элементами) = controlled reveal. Глаз следит по очереди, ощущается premium. Это **один хорошо срежиссированный page-load** из frontend гайда.

---

## Что НЕ делаем (намеренно)

- ❌ **No dark mode toggle** — добавим если будет время в неделю 4. Сейчас отвлечение.
- ❌ **No search bar в Case Queue** — 6 cases не требуют поиска. Когда будет 100 — добавим.
- ❌ **No history view (past decisions)** — backend готов (`/cases/{id}/history`), но UI без него хорош для demo.
- ❌ **No real-time notifications** — WebSocket для новых cases планировался на Day 19. Сейчас premature.

---

## Дальше: куда двигаемся

Backend и core frontend готовы. Три направления:

1. **Polish & demo prep** (Дни 9-11) — refinement, mock data variety, pitch deck draft
2. **Voice analysis module** (Дни 12-14) — AMINA-specific deepfake detection
3. **Multi-skin support** (Дни 9-11) — добавить Julius Baer skin и Ripple skin как переключатель

Моя рекомендация: **Polish & demo prep**. Сейчас у тебя есть полный продукт, осталось довести до показа: добавить 5-10 разнообразных mock cases (текущие 6 хорошие, но больше = богаче demo), записать первый dry-run, подготовить screenshots для slack команды.

Voice module — это **single-day add** на хакатоне если challenge будет про deepfakes.

Multi-skin — добавим **на хакатоне** в субботу, когда узнаем точные challenges. Сейчас архитектура это поддерживает (case_type → разные feature extractors), но UI вариации лучше делать когда знаем что нужно.

Скажи "День 8 готов" + куда хочешь идти. Если есть конкретные вопросы по demo flow — спрашивай.
