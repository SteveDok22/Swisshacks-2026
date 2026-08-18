# Use Cases

The AMINA Challenge 4 brief defines 10 KYC-drift signals. This is the
authoritative map of each to the entity and scenario that proves it in Sentinel —
in both **synthetic** mode (15 deterministic entities) and **live** mode (5 real
companies scored against real public data). It is the single source of truth;
the per-use-case tables elsewhere defer to this page.

The synthetic cast is **15 entities = 12 flagged + 3 stable controls**
(`drift-013` Zürisee Renewables, `drift-014` Toggenburg Family Office, `drift-015`
Vaud AgriTech — clean baselines that must *not* alarm). A bonus dormancy-break
case, `drift-010` Säntis Import-Export AG, demonstrates sleeper-account
reactivation (near-zero baseline → sudden activation burst).

## Summary

| UC | Signal | Detection layer(s) | Synthetic entity | Live entity (real data) |
|----|--------|--------------------|------------------|-------------------------|
| UC1 | Negative-news spike (reputational) | public-intel news + BOCPD | `drift-001` Helvetia Pharma Holding AG | `drift-live-003` Wirecard AG, `drift-live-001` Temenos AG |
| UC2 | Cross-border / corridor anomaly (money-mule) | velocity + corridor risk | `drift-002` Léman FX Trading SA | `drift-live-002` Rosneft Trading S.A. |
| UC3 | Linked entities + sudden flows (structuring) | contagion PageRank + causal | `drift-003` Alpine Logistics, `drift-011` Castor | `drift-live-005` Rosneft Deutschland GmbH |
| UC4 | Legal-entity name change (re-KYC) | name_change + re-KYC floor | `drift-004` Glarnisch Holding AG | `drift-live-004` WW International, Inc. |
| UC5 | New shareholders / UBOs + sanctions | opensanctions + UBO screen + sanctions floor | `drift-008` Bernina, `drift-011` Castor | `drift-live-002` Rosneft, `drift-live-005` Rosneft Deutschland |
| UC6 | Large funding round / expansion (scale) | causal scale-jump + funding signal | `drift-001` (expansion signals) | — |
| UC7 | Jurisdiction / legal-form change (structural) | jurisdiction_change + re-KYC floor | `drift-007` Rhône Capital GmbH | — |
| UC8 | New beneficial owners (ownership drift) | GLEIF ownership_change + UBO screen | `drift-008` Bernina Wealth Partners AG | `drift-live-004` WW, `drift-live-002`/`005` |
| UC9 | Domain / website-content change (business activity) | business-model (Wayback ↔ Firecrawl) | `drift-005` HelvetiaX | `drift-live-001` Temenos AG |
| UC10 | Public business-model pivot (material change) | pivot news + website corroboration | `drift-006` Lattice Labs AG | — |

Detection layers are defined in [drift-engine.md](drift-engine.md); the live
entities in [live-entities.md](live-entities.md); the data sources in
[sources.md](sources.md).

---

## UC1 — Negative-news spike (reputational risk)

Adverse media accumulates for months before a collapse. The public-intel layer
classifies news severity and runs BOCPD over the article-count series to find the
spike; *confirmation lift* amplifies it when it coincides with internal drift.

- **Synthetic:** `drift-001` Helvetia Pharma Holding AG (`news_spike`) — sustained
  adverse coverage from the drift onset.
- **Live:** `drift-live-003` Wirecard AG (real coverage of the €1.9 B collapse)
  and `drift-live-001` Temenos AG (real adverse short-seller coverage), with
  direct article links.
- **Analogue:** Wirecard — red flags piled up in public for ~2 years pre-collapse.

## UC2 — Cross-border / corridor anomaly (money-mule)

Payment corridors drift from low-risk (CH/DE) toward high-risk jurisdictions
(RU/AE) with mule-like velocity. The velocity and corridor-risk metrics catch the
shift before any single transfer crosses a static limit.

- **Synthetic:** `drift-002` Léman FX Trading SA (`corridor_shift`).
- **Live:** `drift-live-002` Rosneft Trading S.A. (real sanctioned counterparty).
- **Analogue:** Deutsche Bank mirror trades ($10 B Russia→UK, 2011–2015).

## UC3 — Multiple linked entities + sudden flows (structuring / contagion)

Risk propagates through ownership topology before the connected customer appears
on any watchlist. Personalized PageRank over the ownership graph elevates entities
1–2 hops from a sanctioned seed; the causal layer separates layering from growth.

- **Synthetic:** `drift-003` Alpine Logistics Group AG and `drift-011` Castor
  Trade Finance AG (`combined`, the contagion seed).
- **Live:** `drift-live-005` Rosneft Deutschland GmbH — real GLEIF ownership chain
  to its sanctioned parent.
- **Analogue:** Danske Estonia — 15 000 shell-company customers, hidden UBO chains.

## UC4 — Legal-entity name change (re-KYC required)

A legal-name change resets the KYC review clock — a known shelf-cycling evasion.
A confirmed `name_change` floors the drift score (re-KYC trigger) regardless of
how clean the transactions look.

- **Synthetic:** `drift-004` Glarnisch Holding AG (`name_cycling`).
- **Live:** `drift-live-004` WW International, Inc. — GLEIF records the real
  `PREVIOUS_LEGAL_NAME` "Weight Watchers International, Inc." → "WW International".
- **Analogue:** Mossack Fonseca — systematic renaming of shelf companies.

## UC5 — New shareholders / UBOs + sanctions screening

A newly-added beneficial owner is screened against OpenSanctions; a definitive
OFAC/EU/SECO hit applies the **sanctions score floor** (mandatory escalation) and
surfaces in the UBO-screening panel with a clickable watchlist link.

- **Synthetic:** `drift-008` Bernina Wealth Partners AG and `drift-011` Castor
  (sanctioned-UBO injection).
- **Live:** `drift-live-002` Rosneft Trading S.A. (direct sanctions hit) and
  `drift-live-005` Rosneft Deutschland GmbH (sanctioned group member).
- **Analogue:** 1MDB — beneficial ownership routed through layered shells.

## UC6 — Large funding round / expansion (scale risk)

A legitimate raise drives volume up *with margin preserved*; the causal layer uses
a scale-jump ratio plus a `funding_event` signal to confirm growth is
acquisition-driven rather than laundering — keeping benign expansion off the radar.

- **Synthetic:** expansion/funding signals on `drift-001` and the benign-growth
  controls (`drift-009` Nimbus Mobility, `drift-013` Zürisee Renewables).
- **Analogue:** FTX — a $900 M raise whose transaction volumes never matched claims.

## UC7 — Jurisdiction / legal-form change (structural risk)

A move offshore (CH → BVI) or a legal-form change (GmbH → Ltd) is a structural
re-KYC trigger. A confirmed `jurisdiction_change` / `legal_form_change` floors the
score at **50** (mandatory re-KYC) however weak the behavioral signal.

- **Synthetic:** `drift-007` Rhône Capital GmbH (`jurisdiction_shift`).
- **Analogue:** Long Blockchain Corp — rebrand to exploit crypto hype.

## UC8 — New beneficial owners (ownership KYC drift)

The GLEIF ownership chain is diffed against the KYC baseline; new
parent/subsidiary links emit `ownership_change` signals, and each resolved UBO
name is screened through OpenSanctions.

- **Synthetic:** `drift-008` Bernina Wealth Partners AG — new sanctioned UBO.
- **Live:** `drift-live-004` WW International (real GLEIF chain) plus
  `drift-live-002` / `drift-live-005` (sanctions on the ownership chain).
- **Analogue:** 1MDB — each UBO change further obscured the principal.

## UC9 — Domain switch / website-content change (business activity)

The business-model layer fetches the company website *as it looked at onboarding*
(Wayback) and *as it looks now* (Firecrawl), embeds both with model2vec, and
flags a cosine distance ≥ 0.35. The UI shows a one-line **LLM summary of what
changed** plus links to the archived snapshot and the live site — not the raw
crawled text.

- **Synthetic:** `drift-005` HelvetiaX (`domain_pivot`) — advisory → crypto
  exchange.
- **Live:** `drift-live-001` Temenos AG — real Wayback 2021 capture vs the current
  temenos.com, with the AI diff summary.
- **Analogue:** N26 / Centra Tech — product/domain proliferation outpacing AML.

## UC10 — Public business-model pivot (material change)

A pivot that surfaces in two independent lenses at once — a news pivot/rebrand
cluster *and* a website cosine shift — is elevated to the critical band by
*corroboration lift*.

- **Synthetic:** `drift-006` Lattice Labs AG (`pivot`) — SaaS → ICO in 90 days.
- **Analogue:** Centra Tech — pivoted from debit-card fintech to ICO; existing AML
  profile captured none of the new business-model risk.
