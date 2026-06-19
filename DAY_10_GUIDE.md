# День 10: Pitch & Demo Materials

Сегодня превратили готовый продукт в **готовый к показу пакет**. Теперь у тебя на руках всё для хакатона: pitch deck, demo script, и материалы для команды.

## Что построили

5 документов в `pitch/`:

| Файл | Назначение | Аудитория |
|---|---|---|
| `deck.md` | 10-slide pitch deck | Жюри |
| `demo-script.md` | Посекундный demo flow | Ты, презентующий |
| `team-onboarding.md` | First 30 minutes для team member | Команда |
| `code-walkthrough.md` | Architecture tour | Команда / жюри / интервьюеры |
| `README.md` | Index по pitch материалам | Все |

## Список изменений

### Новые файлы
- `pitch/README.md` — index
- `pitch/deck.md` — Marp slides
- `pitch/demo-script.md` — demo script с таймингами
- `pitch/team-onboarding.md` — onboarding для команды
- `pitch/code-walkthrough.md` — code review

### Что не изменилось
- Backend и frontend код — без изменений сегодня. Только документация.
- БД не трогаем — старые данные ОК

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -qo ~/Downloads/swisshacks-2026-day10.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update
ls pitch/
```

Должен увидеть 5 файлов в `pitch/`.

## Шаг 2: Установи Marp CLI (для конверсии в PDF)

```bash
npm install -g @marp-team/marp-cli
```

(Если не хочешь global install — можешь использовать VS Code расширение "Marp for VS Code".)

## Шаг 3: Сконвертируй deck в PDF

```bash
cd ~/Documents/Projects/swisshacks-2026
marp pitch/deck.md --pdf --allow-local-files -o pitch/deck.pdf
```

После — открой `pitch/deck.pdf` в Preview. Должно быть **10 slides**:

1. Title — Sentinel
2. The problem
3. What we built
4. Live demo: Marc Weber case
5. Four things we did differently
6. Architecture
7. Privacy by design
8. Cross-jurisdictional reasoning
9. What's next
10. Thank you

## Шаг 4: Прочитай demo-script.md полностью

Открой `pitch/demo-script.md`. Прочитай **весь** документ. Самые важные секции:

- **Pre-demo checklist** — что проверить за 5 минут до выступления
- **The script** — посекундный план: 0:00-0:15, 0:15-0:45, etc.
- **What jurors might ask** — 5 типичных вопросов и готовые ответы
- **Recovery plans** — что делать если что-то ломается

## Шаг 5: Первый dry run

Засеки 3 минуты. Открой dashboard, выбери Marc Weber, проходишь по script. Не торопись, не спеши. Если попал в 3:30 — переписывай contractions, убирай filler words ("так вот", "в общем", "ну").

## Шаг 6: Тест team-onboarding

Прочитай `pitch/team-onboarding.md` как **новый team member**. Найди места которые непонятны:
- Все ли команды работают на свежем checkout?
- Все ли пути правильные?
- Понятно ли где контрибутить?

Если что-то не работает — поправь. **Это документ который реально проверится** когда команда подключится.

## Шаг 7: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 10: Pitch materials — deck, demo script, team onboarding

- 10-slide Marp pitch deck (deck.md)
- Second-by-second demo script with recovery plans
- Team onboarding guide for new members (30-min first session)
- Code walkthrough for architecture tours
- Pitch directory index
"
```

## Чек-лист завершения дня

- [ ] `pitch/` папка существует с 5 файлами
- [ ] `marp pitch/deck.md --pdf` работает (или VS Code Marp extension)
- [ ] `deck.pdf` открывается, 10 slides, читаемо
- [ ] `demo-script.md` прочитан целиком
- [ ] Сделан хотя бы один dry run по script (3 минуты)
- [ ] `team-onboarding.md` прочитан критически
- [ ] Git commit сделан

---

## Что узнал сегодня (теория для джуна)

### Зачем посекундный demo script

Хакатон pitch — это **3 минуты**, и жюри устало. У тебя нет времени на:
- Думать "что говорить дальше"
- Искать кейс в queue
- Прокручивать страницу искать нужную секцию

Каждое из этих "пауз" — 5-10 секунд. Три паузы = 25% твоего времени потеряно.

**Решение**: всё расписано. Что говоришь, что делаешь на экране, где смотрит жюри.

Принцип: **mental load на минимум**. Ты не сочиняешь — ты исполняешь.

### Pitch deck не должен заменять speaker

Slides = **визуальная поддержка**, не сценарий. Распространённые ошибки команд:
- ❌ 200 слов на slide → жюри читает, а не слушает тебя
- ❌ Бесчисленные bullet points → пятно текста, никто не дочитает
- ❌ Код на slides → нечитаемо с 5 метров
- ❌ Слишком много slides → 12+ slides за 3 мин = по 15 секунд каждая, ни одна не запоминается

**Лучше**: 10 slides максимум, каждая — одна мысль, jurors могут "пройти deck" за 30 секунд после твоего pitch'а и **вспомнить** что ты говорил.

### Marp = git-friendly slides

Обычные slides:
- PowerPoint binary — невозможно merge
- Keynote — Mac only
- Google Slides — нужен интернет на demo

**Marp**: pure Markdown. Diff читаемый. Branch + merge работают. Конверсия в PDF/PPTX одной командой.

Trade-off: меньше "wow" эффектов чем в Keynote. Для технического pitch'а — это плюс. Substance over flash.

### Team onboarding как software

Когда команда подключится в субботу утром — у тебя **нет** свободного часа их объяснять. Документ должен **сам** это делать.

Принципы:
1. **First 30 minutes flow** — что именно делать, в каком порядке
2. **Verify points** — "после этого ты должен увидеть X". Если нет — есть проблема.
3. **Contribute list** — конкретные задачи, не "помоги где можешь"
4. **Conventions** — Python/TS/git practices в одном месте

Это инвестиция времени — но даёт **8x возвращение** на хакатоне.

### Code walkthrough — позиционирование

Когда показываешь код жюри / hiring manager / новой команде — это не про "вот мой код". Это про **"я думал об этом"**.

Структура:
1. **Mental model** (одна диаграмма)
2. **Key decisions** (5 штук, каждое с обоснованием)
3. **Anti-patterns avoided** (что мы намеренно не делали)
4. **Honest gaps** (что не построили и почему)

Последний пункт критичен. Если ты признаёшь gaps **до** того как кто-то спросит — выглядит как зрелый инженер, а не student с CV.

---

## Дальше — что хочешь?

Поскольку у нас сейчас:
- ✅ Backend (19 endpoints, ML pipeline, jurisdictions, anonymizer, audit)
- ✅ Frontend (Next.js dashboard, streaming AI, SHAP, counterfactuals, decisions)
- ✅ Mock data (18 разнообразных кейсов)
- ✅ Onboarding для команды
- ✅ Pitch materials

Три направления:

**A. Hardening & polish** — добавить error boundaries, лучшие loading states, fix edge cases в UI. Снижает риск багов на demo.

**B. Voice biometric layer** — Resemblyzer + deepfake detection для AMINA challenge. **Risky**: сложная зависимость от audio libs, может не завестись.

**C. Wait for team** — пакет готов. Можешь сейчас выложить на GitHub, написать команде "вот что мы строим, вот demo, читайте onboarding", и ждать когда подключатся.

Скажи **"День 10 готов"** + выбор направления. Если затрудняешься выбрать — могу обсудить trade-offs.
