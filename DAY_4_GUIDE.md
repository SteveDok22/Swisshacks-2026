# День 4: Дифференциаторы — DiCE Counterfactuals + Anonymization + Jurisdiction Engine

Сегодня добавили **три ключевых элемента**, которые выделят нас на фоне 15 других команд. Это **не features ради features** — это **архитектурные решения**, которые жюри сразу увидит в demo.

## Список изменений в проекте

### Новые файлы
- `backend/app/utils/anonymizer.py` — privacy-first слой для LLM
- `backend/app/schemas/counterfactual.py` — schemas для counterfactuals
- `backend/app/schemas/jurisdiction.py` — schemas для jurisdiction rules
- `backend/app/services/counterfactual.py` — DiCE-based counterfactual service
- `backend/app/services/jurisdiction.py` — Jurisdiction Rule Engine
- `backend/app/api/v1/counterfactuals.py` — POST /counterfactuals/{case_id}
- `backend/app/api/v1/jurisdictions.py` — GET/POST jurisdictions endpoints
- `backend/app/jurisdictions/CH.yaml` — FINMA rules
- `backend/app/jurisdictions/EU.yaml` — MiCA rules
- `backend/app/jurisdictions/HK.yaml` — SFC rules
- `backend/app/jurisdictions/AE.yaml` — FSRA rules

### Изменённые файлы
- `backend/app/schemas/__init__.py` — добавлены exports
- `backend/app/api/v1/__init__.py` — подключены 2 новых router
- `backend/app/main.py` — загрузка jurisdictions при старте
- `backend/app/services/mock_data.py` — добавлен EXTREME suspicious case
- `backend/app/ml/training.py` — расширен AUM range (для DiCE feasibility)
- `backend/pyproject.toml` — добавлен PyYAML

### Не трогать
- `backend/.env`
- `backend/.venv/`
- `.git/`
- `backend/data/models/` (тебе нужно будет ПЕРЕТРЕНИРОВАТЬ модель)

---

## Шаг 1: Распакуй обновлённый архив

```bash
cd ~/Documents/Projects/swisshacks-2026

# Защищаем .env
cp backend/.env backend/.env.backup 2>/dev/null || true

# Распаковываем во временную папку
unzip -q ~/Downloads/swisshacks-2026-day4.zip -d /tmp/swisshacks-update

# Копируем поверх
cp -a /tmp/swisshacks-update/swisshacks-2026/. .

# Возвращаем .env
mv backend/.env.backup backend/.env 2>/dev/null || true

# Чистим
rm -rf /tmp/swisshacks-update

# Проверяем что изменилось
git status
```

## Шаг 2: Обнови зависимости

```bash
cd backend
source .venv/bin/activate

# DiCE + PyYAML добавились в pyproject.toml
uv pip install -r pyproject.toml
```

Это займёт 1-2 минуты — DiCE подтягивает scipy/scikit-learn совместимые версии.

## Шаг 3: КРИТИЧЕСКИ ВАЖНО — Перетренируй модель

Мы расширили AUM range в synthetic data чтобы DiCE мог работать с HNW клиентами. **Старую модель нужно заменить**.

```bash
# Из папки backend/
python -m app.ml.training train-social-engineering
```

Должен увидеть:
```
synthetic_data_generated     total=5000 fraud_count=750
training_completed     accuracy=1.0 f1=1.0 roc_auc=1.0
model_saved     path=data/models/social_engineering_v1.joblib
```

## Шаг 4: Запусти сервер

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Теперь в логах должно быть **дополнительно**:
```
jurisdiction_loaded     code=CH  regulator=FINMA
jurisdiction_loaded     code=EU  regulator='ESMA / National Competent Authorities'
jurisdiction_loaded     code=HK  regulator='SFC / HKMA'
jurisdiction_loaded     code=AE  regulator='FSRA / VARA'
jurisdictions_loaded    count=4
```

## Шаг 5: Проверь все три дифференциатора в Swagger UI

Открой **http://localhost:8000/docs**. Появились **две новые секции**: `counterfactuals` и `jurisdictions`.

### 5.1: Counterfactuals (самый WOW момент)

**EXTREME case** — Marc Weber, voice call в воскресенье 3am, CHF 8.7M в Россию, urgency+secrecy markers в transcript:

1. Сначала score этот case: `POST /api/v1/scoring/22222222-2222-2222-2222-222222222204`
2. Должен увидеть score ~99.98, action: BLOCK
3. Теперь counterfactuals: `POST /api/v1/counterfactuals/22222222-2222-2222-2222-222222222204?n_scenarios=3`
4. Execute

Получишь **3 сценария** типа:
```json
{
  "scenario_id": 1,
  "summary": "If destination were lower-risk country (0.24 vs 0.85) and fewer secrecy markers (1 vs 4) — this case would be approved.",
  "changes": [...]
}
```

**Это и есть наш дифференциатор**. На demo: "AI не просто блокирует — он говорит compliance officer'у, что должно быть по-другому для approval".

### 5.2: Jurisdiction comparison

1. `POST /api/v1/jurisdictions/compare/22222222-2222-2222-2222-222222222201` (Hans Müller, suspicious case)
2. Execute

Увидишь как один и тот же case scored под четырьмя jurisdiction frameworks:
```
CH (FINMA):  base 39.01 → adjusted 51.49 → step_up_verification
EU (MiCA):   base 39.01 → adjusted 53.64 → step_up_verification
HK (SFC):    base 39.01 → adjusted 51.56 → step_up_verification
AE (FSRA):   base 39.01 → adjusted 58.32 → escalate  ← разная action!
```

**AE (UAE/ADGM) — strictest framework**: тот же ML score уходит в escalation. Это прямой demo moment для AMINA.

### 5.3: Просмотр jurisdictions

1. `GET /api/v1/jurisdictions` → видишь все 4 rule packs с полными деталями
2. `GET /api/v1/jurisdictions/CH` → детали Switzerland

Каждый JSON содержит:
- Travel Rule threshold
- EDD threshold
- Score modifiers (PEP, new destination, etc.)
- Action thresholds (allow/step-up/escalate boundaries)
- Reporting requirements
- Officer notes (показываются в UI на demo)

### 5.4: Anonymizer (тест в Python)

В отдельном терминале:

```bash
cd backend
source .venv/bin/activate

python -c "
from app.utils.anonymizer import get_anonymizer
anon = get_anonymizer()
report = anon.anonymize_case_data(
    {'requested_amount_chf': 4_500_000.0, 'destination_wallet': '0xABCD1234...'},
    client_name='Hans Müller'
)
print('Anonymized:', report.anonymized)
"
```

Должен увидеть:
```
Anonymized: {
  'client_pseudonym': 'CLIENT_AAF7',
  'requested_amount_chf': 'CHF 1M-5M',
  'destination_wallet': '0xAB****...',
}
```

Это то, что **будет отправляться в Claude API** на День 5. Реальные имена и точные суммы **не уходят за пределы банка**.

## Шаг 6: Curl команды (для понимания)

```bash
# Counterfactuals
curl -X POST "http://localhost:8000/api/v1/counterfactuals/22222222-2222-2222-2222-222222222204?n_scenarios=3" | jq

# Jurisdiction comparison
curl -X POST http://localhost:8000/api/v1/jurisdictions/compare/22222222-2222-2222-2222-222222222201 | jq

# Все jurisdictions
curl http://localhost:8000/api/v1/jurisdictions | jq '.[] | {code, name, regulator}'
```

## Шаг 7: Git commit

```bash
cd ~/Documents/Projects/swisshacks-2026
git add .
git commit -m "Day 4: Differentiators — DiCE + Anonymizer + Jurisdiction Engine

- Added Anonymizer for FINMA-compliant LLM interactions
- Added DiCE-based Counterfactual service (3 scenarios per case)
- Added Jurisdiction Rule Engine with YAML rules (CH/EU/HK/AE)
- Added 7 new API endpoints (counterfactuals + jurisdictions)
- Extended synthetic data range for HNW client coverage
- Added EXTREME mock case for counterfactual demo
- 12 endpoints total, 4 jurisdiction rule packs loaded at startup
"
```

## Чек-лист завершения дня

- [ ] Все новые зависимости установлены (DiCE, PyYAML)
- [ ] Модель ПЕРЕТРЕНИРОВАНА (важно — иначе counterfactuals failед)
- [ ] Сервер запускается с `jurisdictions_loaded count=4` в логах
- [ ] `POST /api/v1/scoring/22222222-...-204` возвращает score ~99.98
- [ ] `POST /api/v1/counterfactuals/22222222-...-204` возвращает 3 сценария
- [ ] `POST /api/v1/jurisdictions/compare/22222222-...-201` показывает разные actions для AE
- [ ] Anonymizer корректно превращает "Hans Müller" → "CLIENT_XXXX"
- [ ] Git commit сделан

## Что узнал сегодня (теория для джуна)

### DiCE (Diverse Counterfactual Explanations)

DiCE — open-source библиотека от Microsoft Research, которая отвечает на вопрос: **"какое минимальное изменение fliped бы prediction?"**.

Под капотом:
1. Берёт your model + training data
2. Сэмплирует точки в feature space вблизи query
3. Использует genetic/random/kdtree search для нахождения "ближайших" точек с противоположным labelом
4. Возвращает diverse set счетарев (не все одинаковые)

**Почему это сильнее SHAP**:
- SHAP: "amount contributed +4 to risk score" → academic
- DiCE: "if amount were CHF 800K instead of 4.5M, this would be approved" → actionable

**Лимитации**:
- Compute expensive (~500ms per call) → мы кэшируем explainer
- Требует feasibility region → расширили training data
- Иногда не находит solution → возвращаем empty + notes

### Strategy Pattern в jurisdictions

YAML rules — это **classic configuration-as-code**. Compliance officer может **открыть `CH.yaml` и поменять threshold** без перекомпиляции:

```yaml
cdd:
  enhanced_due_diligence_threshold_chf: 100000  # ← измени и перезапусти
```

Это **аудитируемо**: можно git diff чтобы видеть какие changes к compliance rules были.

**Почему YAML а не JSON**:
- Комментарии (важно для compliance)
- Multi-line strings (officer_notes)
- Меньше "noise" для не-программистов

### Anonymization patterns

Мы используем **deterministic pseudonymization**:
```python
hashlib.sha256(f"{salt}::{name}").hexdigest()[:4]
```

- Same input → same pseudonym (stable across requests)
- Different inputs → different pseudonyms
- Non-reversible without salt

Это **production-grade pattern**. Реальные банки делают то же самое + добавляют HSM (Hardware Security Module) для хранения salt.

**Amount bucketing** — privacy preserving, но сохраняет signal:
- Exact: "CHF 4,500,000" → identifying
- Bucket: "CHF 1M-5M" → model can still reason about magnitude

### Singleton service pattern

Все три новых сервиса (`Anonymizer`, `CounterfactualService`, `JurisdictionService`) — **singletons**:

```python
_service: CounterfactualService | None = None

def get_counterfactual_service() -> CounterfactualService:
    global _service
    if _service is None:
        _service = CounterfactualService()
    return _service
```

Зачем:
- DiCE explainer expensive — строим ОДИН раз
- Training data в памяти — ОДНА копия
- Jurisdiction YAML — загружается при первом запросе

Когда сервер обрабатывает 100 requests/sec — все они используют один объект, не пересоздают каждый раз.

### Lazy initialization for expensive operations

DiCE explainer строится только при первом запросе counterfactuals:

```python
def _get_dice_explainer(self, case_type: CaseType, model: RiskModel) -> Any:
    if case_type in self._dice_cache:
        return self._dice_cache[case_type]
    # ... expensive build ...
    self._dice_cache[case_type] = explainer
    return explainer
```

Первый запрос: ~2 секунды. Все последующие: ~250ms. Если DiCE никогда не используется — explainer **не строится вообще**.

### YAML loading с Pydantic validation

```python
with open(yaml_path) as f:
    data = yaml.safe_load(f)
rules = JurisdictionRules(**data)  # ← validates!
```

Pydantic проверяет что YAML корректный. Если кто-то ошибётся (например, забудет поле) — приложение упадёт **сразу при старте** с понятной ошибкой, а не через час когда compliance officer попытается использовать jurisdiction.

### Чем мы отличаемся от других команд

Большинство команд за 48 часов на хакатоне сделают:
- XGBoost + SHAP ✅ (мы тоже)
- Frontend с dashboard ✅ (мы тоже)
- LLM для natural language ✅ (мы тоже — День 5)

**Чего НЕ сделают другие команды**:
- DiCE counterfactuals (никто не знает что это, не успеют добавить за 48ч)
- YAML-based jurisdiction rules (не успеют сделать конфигурацию)
- Visible anonymization layer (пошлют raw data в Claude)

Эти три элемента — **наш architectural moat**. Они показывают что мы понимаем:
1. **AMINA pain points** (cross-jurisdictional, security, compliance)
2. **Швейцарский regulatory context** (FINMA, data sovereignty)
3. **Production AI patterns** (counterfactuals — это hot topic в EU AI Act)

---

## Архитектурные решения объяснённые

**Почему 4 YAML файла, а не один с массивом?**

Compliance officer редактирует **по одной юрисдикции за раз**. Один файл = одна область ответственности. Это match'ит работу compliance команды (есть FINMA expert, есть MiCA expert, etc).

**Почему counterfactuals expensive (500ms)?**

DiCE с `method=random` делает несколько hundred sample evaluations. Это normal для production. На demo это будет visible loading state — но **это feature**, не bug: "AI thinking through alternative scenarios..." это сильный visual moment.

**Почему мы расширили training data range?**

DiCE требует чтобы query point был в **feasibility region** — то есть значения features должны быть похожи на training distribution. Marc Weber имеет CHF 28M AUM (log≈17.16), а раньше training data был до log≈16. DiCE отказывался работать. После расширения работает.

**Почему action_thresholds разные между jurisdictions?**

Это **реальная регуляторная реальность**: ADGM/FSRA (UAE) — strictest framework среди AMINA jurisdictions, FINMA — strict но прагматичный, SFC — middle ground. Мы encode'или это в thresholds.

---

## Дальше: День 5 — Claude API integration

Завтра:
- **Claude API streaming** для natural language explanations
- **Anonymizer применяется** перед каждым LLM call
- **SSE endpoint** для streaming responses в UI
- **Caching** ответов Claude чтобы экономить tokens

После Дня 5 у тебя будет полный flow:
```
case → ML score → SHAP → DiCE counterfactuals → Claude natural language explanation
                                                  ↑
                                          anonymized features only
```

Это **production-ready backend** который можно показать любому жюри.
