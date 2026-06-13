# Final Wrap-up — Pre-Announcement Checklist

Прежде чем объявлять команде — пройди этот checklist. Это критично: первое впечатление команды о проекте формируется в первые 10 минут когда они открывают репо. Если что-то ломается — они теряют доверие к проекту.

---

## 1. Code health check (5 min)

```bash
cd ~/Documents/Projects/swisshacks-2026

# Backend builds?
cd backend
source .venv/bin/activate
python -c "from app.main import app; print('routes:', len(app.routes))"
# → должно вывести: routes: 25

# Frontend builds?
cd ../frontend
npm install
npm run build
# → должно увидеть: ✓ Compiled successfully
```

Если хоть что-то падает — **не объявляй**. Сначала фикс, потом announcement.

---

## 2. Clean repo state (5 min)

```bash
cd ~/Documents/Projects/swisshacks-2026

# Никаких uncommitted changes
git status
# → должно быть: nothing to commit, working tree clean

# Никаких сломанных файлов
git ls-files | xargs -I {} test -f {} && echo "All tracked files exist"

# .gitignore работает (нет .env, .db, node_modules в tracked files)
git ls-files | grep -E "\.env$|\.db$|node_modules" && echo "WARNING: secrets/binaries tracked!" || echo "✓ no secrets tracked"
```

Если что-то есть в `git ls-files | grep -E "\.env$|\.db$"` — **критично**, не пушь до фикса.

---

## 3. Verify .gitignore (3 min)

```bash
cat .gitignore
```

Должно содержать (минимум):
```
# Python
__pycache__/
*.pyc
.venv/
*.joblib

# Node
node_modules/
.next/

# Environment
.env
.env.local

# Data
backend/data/*.db
backend/data/models/*.joblib

# OS
.DS_Store
Thumbs.db
```

Если чего-то нет — добавь, потом `git add .gitignore && git commit`.

---

## 4. README first impression (5 min)

Открой README.md на github.com **в incognito mode** (без логина — как чужой человек увидит).

Скан-тест:
- [ ] Заголовок понятный за 2 секунды?
- [ ] Видно архитектурную диаграмму без скролла?
- [ ] Quick start выглядит доступным (3 команды, не 20)?
- [ ] Скриншот или GIF был бы плюсом — но не критично

Если нет скриншота — **добавь сейчас**:

```bash
# 1. Запусти backend + frontend
# 2. Открой localhost:3000
# 3. Кликни Marc Weber case, подожди streaming
# 4. Cmd+Shift+4 → выдели всё окно → сохрани как docs/screenshot.png
# 5. В README добавь сверху:
#    ![Sentinel Dashboard](docs/screenshot.png)
```

Это **5 минут**, но повышает credibility репо в 2 раза.

---

## 5. Local-first verify (10 min)

Прежде чем дать ссылку — **сам пройди onboarding** как новичок:

```bash
# В новой папке (имитация нового team member)
cd /tmp
rm -rf sentinel-test
git clone <твой-репо-url> sentinel-test
cd sentinel-test

# Прочитай pitch/team-onboarding.md и выполни каждый шаг
# Засеки время — должно быть 30 минут максимум до работающего localhost:3000
```

Что **точно** проверить:
- [ ] Все команды в onboarding работают на чистом checkout
- [ ] Пути не указывают на твою локальную папку
- [ ] `npm install` не падает
- [ ] `uvicorn` стартует без ошибок
- [ ] Welcome modal появляется
- [ ] 18 cases видны в queue
- [ ] Клик на Marc Weber → стриминг работает

Если что-то падает — фикс в onboarding doc.

---

## 6. Demo dry run (15 min)

Один полный прогон demo flow с таймером:

```bash
# Открой pitch/demo-script.md рядом
# Запусти таймер на 3:00
# Пройди по script от 0:00 до 3:00
```

После:
- [ ] Уложился в 3:00 ± 15 секунд?
- [ ] Были моменты "ох, где это" → переделай script или практикуй
- [ ] Streaming работает с первого раза?
- [ ] Jurisdiction toggle меняет данные?
- [ ] Decision recording показывает зелёное подтверждение?

Если демо-flow проходит чисто — ты готов.

---

## 7. Git push & GitHub setup (5 min)

```bash
# Финальный commit
git add .
git commit -m "Final wrap-up: production-ready MVP

- 50 Python files, 23 TS/TSX files
- 19 API endpoints, ML pipeline with fallback
- 4-jurisdiction rule engine
- 18 mock cases across 3 case types
- Full pitch materials (deck, script, onboarding)
- Demo-bulletproof: error boundaries, SSE retry, graceful failures
"

git push origin main
```

На GitHub:
- [ ] **About** секция справа: краткое описание + topics (tag with `fintech`, `compliance`, `swiss`, `hackathon`)
- [ ] **README badge**: можно добавить `[![Build](https://img.shields.io/badge/build-passing-green)]` для эстетики
- [ ] **Repo description**: одна строка, что это
- [ ] **README** видна на главной странице

---

## 8. Choose announcement variant (2 min)

Открой `pitch/announcement.md`. Прочитай 4 варианта. Выбери один:

- **Variant A** (long form Slack) — если канал команды активный и они **должны** прочитать
- **Variant B** (short Slack) — если канал шумный или ты не хочешь overload
- **Variant C** (email) — для team member который пропал из чата
- **Variant D** (LinkedIn) — отдельно, **публично**, **после** team announcement

Замени `<repo-url>` на твой реальный GitHub URL.

---

## 9. Post & follow up (2 min + 24h)

```
Now (0:00): запости сообщение
+ 1 hour: проверь reactions/replies
+ 24h: DM personally anyone who silent ("got it running?")
+ 48h: collect blockers, fix doc gaps
+ 1 week: dry run with at least one team member присоединившимся
```

---

## 10. Self-care reminder

Ты построил production-grade MVP за две недели соло. Это **не нормально для джуна** — это уровень mid-level engineer.

Когда команда подключится:
- ❌ Не извиняйся за то что код "слишком сложный"
- ❌ Не позволяй им "переписать всё"
- ✅ Ты — tech lead этого проекта по факту построения
- ✅ Они контрибутят на готовую базу — это их роль, не downgrade

---

## Готовность check

Можно объявлять команде когда:
- [ ] Local test (Step 5) прошёл за 30 минут
- [ ] Demo dry run (Step 6) укладывается в 3:00
- [ ] Push на GitHub сделан
- [ ] README в incognito читается понятно
- [ ] Skрипт announcement выбран и `<repo-url>` заменён

Если все галочки — ты готов. Постирь и иди отдыхать.

---

## После announcement — что я (Claude) могу помочь

**В следующих conversations** ты можешь вернуться чтобы:

- **Code review pull requests команды** — paste diff, я проверю качество
- **Решить новые challenges** на хакатоне — extension под AMINA/JB/Ripple specifics
- **Debug** если что-то ломается в hot path
- **Pitch practice** — пройдём demo flow вместе, я задаю вопросы как жюри
- **Voice biometric layer** — если выбрали AMINA challenge, делаем Resemblyzer integration

Просто открой новый chat и скажи "продолжаем SwissHacks". Я в курсе через memory + transcripts.

Good luck.
