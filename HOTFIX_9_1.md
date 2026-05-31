# Hotfix 9.1 — Backend fallback + Sidebar disabled items

Быстрый фикс двух багов, замеченных после Day 9:

## Что не работало

1. **404 ошибки** при клике на не-social_engineering кейсы
   - 4 investment_recommendation cases + 6 xrpl_transaction cases выдавали:
     `"No model registered for case_type=xrpl_transaction"`
   - Streaming, scoring, jurisdictions, counterfactuals — все падали с 404

2. **Sidebar nav кнопки** — Live Alerts / Audit Log / Jurisdictions выглядели
   как кликабельные, но не делали ничего (анимация + hover есть, страниц нет)

## Что починили

### Backend

**`app/ml/registry.py`** — graceful fallback в `get_or_raise()`:
- Если модель для запрошенного case_type не зарегистрирована, используем
  `social_engineering` как baseline
- Логируем `model_fallback_to_baseline` warning для трассировки

**`app/ml/extractors/social_engineering.py`** — cross-case-type field resolution:
- Распознаёт XRPL fields (`amount`, `to_address`, `tx_timestamp`)
- Распознаёт `counterparty_whitelisted`, `sanctions_match`, `mixer_proximity_hops`

**`app/services/risk_engine.py`** — новый метод `_apply_critical_overrides()`:
- Rule-based amplification поверх ML score
- Sanctions match → score ≥ 95 (critical)
- Mixer proximity 1-2 hops → score ≥ 75 (high)
- Mixer proximity 3 hops → score ≥ 55 (medium)
- PEP + new counterparty + >CHF 1M → score ≥ 80 (high)

Это **архитектурно правильно**: критичные red flags (OFAC, mixer)
не должны зависеть только от ML model output. Это safety net.

### Frontend

**`components/layout/Sidebar.tsx`** — переписан:
- Case Queue + About Sentinel — реально работают (Link)
- Live Alerts / Audit Log / Jurisdictions / Settings — **disabled**
  с "Soon" badge и tooltip
- Honest disclosure вместо fake-interactive

## Результат scoring после фикса

| Case | Score | Level | Action |
|---|---|---|---|
| Marc Weber CHF 8.7M (social_eng) | 100 | critical | block |
| Klaus PEP EUR 3.2M (social_eng) | 100 | critical | block |
| Elisabeth ESG rebalance | 0 | low | allow |
| Hans add 8% crypto | 0 | low | allow |
| Ahmed mixer 2 hops (XRPL) | 75 | high | escalate |
| **Mei Lin OFAC sanctions (XRPL)** | **95** | **critical** | **block** |
| Wei internal transfer | 0 | low | allow |

OFAC sanctions case теперь правильно поднимается в **critical**, что и должен делать compliance system.

## Что делать

```bash
cd ~/Documents/Projects/swisshacks-2026
cp backend/.env backend/.env.backup 2>/dev/null || true
unzip -qo ~/Downloads/swisshacks-2026-day9_1.zip -d /tmp/swisshacks-update
cp -a /tmp/swisshacks-update/swisshacks-2026/. .
mv backend/.env.backup backend/.env 2>/dev/null || true
rm -rf /tmp/swisshacks-update

# КРИТИЧНО: удали старую БД (изменились score override логика — старые score'ы кэшированы)
rm backend/data/risk_platform.db

# Перезапусти backend
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend перезапускать не нужно — Next.js dev server подхватит изменения.

## Что проверить

1. Открыть **Mei Lin Tan OFAC sanctions case** — должен показать score 95, critical, block
2. Открыть **Hans Müller "add 8% crypto"** (investment recommendation) — должен показать score 0, low
3. Кликнуть на Live Alerts / Audit Log в sidebar — **никакой реакции**, видно "Soon" badge
4. Console (F12) — **0 ошибок** при перелистывании cases
