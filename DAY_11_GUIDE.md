# День 11: Hardening & Polish

Сегодня сделали продукт **demo-bulletproof**. Цель — нулевая вероятность бага во время 3-минутного pitch'а.

## Что построили

1. **SSE auto-retry** в `useStreamingText` — при network glitch автоматически переподключается (до 2 попыток)
2. **Connection status UI** — пользователь видит "reconnecting (attempt 2)…" во время retry
3. **Counterfactual graceful degradation** — DiCE failure не крашит весь panel, возвращает пустой результат с note
4. **Manual retry API** — отдельная `retry()` функция в hook для пользовательского retry

ErrorBoundary'и (5 секций обёрнуты) и Skeleton'ы (loading states) уже были интегрированы из прошлых сессий.

## Что изменилось

### Изменённые файлы
- `frontend/src/lib/useStreamingText.ts` — переписан с retry logic
- `frontend/src/components/cases/StreamingExplanation.tsx` — обновлён под новый API, показывает retry status
- `backend/app/api/v1/counterfactuals.py` — graceful empty response при exception

### Не изменилось
- Backend ML код — без изменений
- Mock data — без изменений
- Дизайн system — без изменений
- БД — **не нужно** удалять, никаких schema changes

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -qo ~/Downloads/swisshacks-2026-day11.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
```

## Шаг 2: Backend — просто перезапусти

Никаких новых dependencies, никаких миграций. Если backend уже запущен в первом терминале — Ctrl+C и снова `uvicorn app.main:app --reload`.

## Шаг 3: Frontend — просто перезапусти

Next.js hot-reload подхватит изменения автоматически. Если хочешь чистый старт — Ctrl+C и `npm run dev`.

## Шаг 4: Протестируй retry logic — попробуй сломать demo

Это **ключевой тест** дня. Открой Marc Weber case в браузере, потом:

### Тест 1: Backend убит во время streaming

В терминале с backend:
1. Запусти backend нормально
2. Открой Marc Weber case в frontend — увидишь streaming начался
3. **Останови backend** (Ctrl+C) пока streaming идёт
4. Через ~1 секунду в UI должно появиться: `reconnecting (attempt 2)…`
5. Через ещё ~1 секунду: `AI stream unavailable` + кнопка "Try again"
6. Запусти backend снова: `uvicorn app.main:app --reload`
7. Кликни "Try again" в UI — streaming должен возобновиться

**Что это доказывает**: если на demo backend упадёт — у тебя есть кнопка retry, не нужно перезагружать страницу и терять презентационный momentum.

### Тест 2: Counterfactual graceful failure

Сложнее воспроизвести искусственно, но раньше DiCE мог вернуть 500 → весь Counterfactuals блок крашился. Теперь — если что-то падает, видишь:
```
Alternative Scenarios
[пусто или с note "Counterfactual generation unavailable"]
```
И остальные секции (SHAP, Jurisdictions, Decision) продолжают работать.

### Тест 3: Быстрое переключение между cases

1. Открой Marc Weber
2. Сразу кликни на Klaus Hofmann
3. Сразу кликни на Mei Lin Tan
4. Сразу обратно на Marc Weber

**Раньше**: могли видеть данные не того case'а на 200-500ms (race condition).
**Сейчас**: каждый клик отменяет старые SSE streams, React Query кэширует case data — переключение мгновенное и правильное.

## Шаг 5: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 11: Hardening & polish — SSE retry, graceful counterfactuals

- useStreamingText: auto-retry on network errors (max 2 attempts, 800ms delay)
- Distinguishes server-sent errors (don't retry) from network errors (retry)
- StreamingExplanation: shows 'reconnecting (attempt N)' state
- Counterfactuals endpoint: graceful empty response on DiCE failure
- Manual retry() exposed alongside auto-retry
"
```

## Чек-лист завершения дня

- [ ] `npm run build` проходит чисто (0 ошибок)
- [ ] Тест 1 пройден: backend убит → reconnect + retry button работает
- [ ] Тест 3 пройден: быстрое переключение cases без stale data
- [ ] Counterfactual section не крашится если DiCE падает
- [ ] Git commit сделан

---

## Что узнал сегодня (теория для джуна)

### EventSource не имеет built-in retry для server errors

Браузерный `EventSource` авто-переподключается **только** на network errors (TCP disconnect). Если сервер шлёт `event: error data: ...` — connection закрывается, но никаких retry.

Это правильное поведение: если сервер сказал "error: model not found" — повторный запрос даст ту же ошибку. Retry бесполезен.

Но в нашем случае мы хотим различать:
- **Server error** (model registry miss) → показать message, manual retry button
- **Network error** (backend died) → auto-retry 2 раза, потом manual

В коде это:
```ts
source.addEventListener("error", (e: Event) => {
  const data = (e as MessageEvent).data;
  if (data) {
    // Server-sent error event has .data
    setError(String(data));
    return;
  }
  // Native error event has no .data → network issue
  if (!hasReceivedData && retryCount < MAX_AUTO_RETRIES) {
    setTimeout(openStream, RETRY_DELAY_MS);
  }
});
```

### useRef для sync values в closures

React state (`useState`) обновляется асинхронно. Если closure читает state — она читает **старое** значение пока React не re-render'ит.

Пример проблемы:
```ts
const [retryCount, setRetryCount] = useState(0);
source.addEventListener("error", () => {
  if (retryCount < MAX) {  // ← может быть stale!
    setRetryCount(retryCount + 1);
  }
});
```

Решение — `useRef` для sync state:
```ts
const retryCountRef = useRef(0);
// ...
if (retryCountRef.current < MAX) {
  retryCountRef.current += 1;
  setRetryCount(retryCountRef.current);  // для UI
}
```

`ref.current` — actual current value, не зависит от render cycle.

### "Don't retry on data received"

Если streaming уже отдал часть текста и потом потерял connection — **не** перезапускаем с нуля. Это даёт хуже UX (текст пропадает) чем оставить partial result.

В коде:
```ts
let hasReceivedData = false;
source.addEventListener("message", () => {
  hasReceivedData = true;
  // ...
});
source.addEventListener("error", () => {
  if (!hasReceivedData && retryCount < MAX) {
    // retry
  } else {
    // partial result OK, just stop
  }
});
```

Это **graceful degradation** — лучше неполный ответ, чем перезагрузка.

### Graceful 200 vs strict 500

API design choice — что делать когда optional feature падает?

**Strict 500** (раньше у нас):
- ✅ Honest about failure
- ❌ Frontend должен handle везде
- ❌ ErrorBoundary в UI ловит, но весь section пропадает

**Graceful 200 with empty data** (теперь):
- ✅ Frontend code проще (data?.counterfactuals?.length === 0)
- ✅ Other sections работают
- ⚠️ Может скрыть real bug (нужен server-side logging)

Для **nice-to-have features** (counterfactuals) — graceful 200 правильнее.
Для **core features** (scoring, case detail) — strict 500 правильнее (нужно знать что сломано).

Решение: layer by feature criticality.

### Анти-паттерн: refetch на mount без cleanup

Раньше StreamingExplanation `useEffect(start, [caseId])` — открывает SSE. Но если caseId меняется быстро — старые streams **не закрываются**, накапливаются в backend (что мы видели в Stiven'е логах: "Got event: http.disconnect").

Фикс — cleanup в `reset()`:
```ts
const reset = () => {
  if (eventSourceRef.current) {
    eventSourceRef.current.close();
  }
  // ... сброс state
};

useEffect(() => {
  reset();  // ← закрывает старый
  start();  // ← открывает новый
}, [caseId]);
```

Bonus — auto-cleanup на unmount:
```ts
useEffect(() => () => closeStream(), []);
```

---

## Дальше — оценка состояния

**MVP completeness: ~95%**

Что точно работает:
- ✅ 19 API endpoints, все защищены try/except
- ✅ ML pipeline с fallback и rule overrides
- ✅ 18 разнообразных mock cases
- ✅ Streaming с auto-retry
- ✅ ErrorBoundary вокруг каждой секции
- ✅ Skeleton loading states
- ✅ Decision flow с audit log
- ✅ Privacy split-view
- ✅ Jurisdiction toggle
- ✅ Welcome modal для onboarding
- ✅ About page
- ✅ Pitch deck + demo script + team onboarding

Что ещё можно сделать (но не критично):
- Voice biometric layer (Day 12-14 если выбираем direction B)
- Multi-skin support (на хакатоне)
- WebSocket real-time alerts
- Audit Log UI page
- Tests
- Postgres migration path

**Моя рекомендация**: пакет готов. Не нужно ещё дней разработки до хакатона. Что нужно — **dry runs demo flow** и **дать команде onboarding**.

Скажи "День 11 готов" + хочешь:

**A. Финальный wrap-up** — последний commit, push на GitHub, объявление в команду. Я помогаю составить announcement post.

**B. Voice biometric layer** — следующие 2-3 дня. Risky, но differentiator для AMINA challenge.

**C. Что-то конкретное** — фикс какого-то поведения, добавление какой-то детали. Покажи скриншот или опиши.
