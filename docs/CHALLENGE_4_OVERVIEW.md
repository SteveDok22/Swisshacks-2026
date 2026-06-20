# AMINA Bank · Challenge 4 — Dynamic Risk Profiling System

> Source: [SwissHacks-2026/Amina-BANK](https://github.com/SwissHacks-2026/Amina-BANK/blob/main/README.md) · hosted by Tenity, Zürich · 19–21 June 2026

---

## Problem Statement

Banks struggle with early detection of unusual financial behavior and risk signals. While internal KYC and AML data exists, critical signals emerge first in public domains — news, registries, funding announcements. The challenge seeks a **predictive AI system merging real-time public intelligence with internal bank data** for early risk detection in a secure, compliant manner.

The system should detect **both**:
- **Immediate fraud signals** — sudden spikes, sanctions hits, adverse media
- **Slow structural drift** — changes that gradually invalidate the original KYC profile, often months before a regulatory action

**Potential users:** Compliance, AML, and KYC teams in regulated banking; risk officers managing customer due diligence and transaction monitoring.

---

## Judging Criteria

| Criterion | Description | Weight |
|---|---|---|
| **AI Intelligence Quality** | Accurate flags, strong reasoning, useful insights | **25%** |
| **Cost Efficiency** | Smart model usage, efficient pipelines, cost per 1,000 analyses | **20%** |
| **UX & Explainability** | Clear alerts, intuitive UI, human-readable reasoning | **20%** |
| **Compliance & Safety** | Guardrails, explainability, auditability | **20%** |
| **Engineering & Architecture** | Scalable design, modular pipelines, robustness | **15%** |

> Cost tracking requirement: teams must **track token usage per workflow**, estimate cost per 1,000 analyses, and demonstrate lightweight vs heavy model usage explicitly.

---

## Use Cases

Specific signal scenarios from the challenge brief — each must be detected, flagged, and produce a recommended action:

| Signal | Expected Flag | Recommended Action |
|---|---|---|
| Sudden spike in negative news about corporate client | High Reputational Risk | Trigger enhanced due diligence; escalate to compliance |
| High-value cross-border transfers inconsistent with history | Behavioural Anomaly – Potential Money Mule | Monitor transactions; flag for AML review |
| Multiple linked entities, low activity, sudden large flows | Structuring / Layering Risk | Trigger AML investigation |
| Legal entity name change | Entity Identity Change – Re-KYC Required | Trigger KYC refresh; re-evaluate risk category |
| Domain switch or significant website content change | Business Activity Change Signal | Re-analyse website content; compare vs onboarding data |
| Public pivot (e.g., SaaS startup → crypto trading) | Material Business Model Change | Update risk classification; escalate for compliance |
| Jurisdiction move or legal form change (GmbH → offshore) | Structural Risk Change | Trigger enhanced due diligence; re-check ownership |
| New shareholders or beneficial owners appear | Ownership Change – KYC Drift | Full ownership verification; re-screen against sanctions / PEP |
| Large funding round or rapid geographic expansion | Scale Risk Change | Reassess transaction thresholds; update activity profile |
| Previously dormant company begins high transaction volume | Dormancy Break – Suspicious Activation | Trigger AML review; validate business legitimacy |

**Coverage in Sentinel Drift Engine:**
- ✅ Covered: reputational news spike, behavioural anomaly, structuring/layering, jurisdiction move, new beneficial owners, funding round / scale change, **dormancy break** (explicit `drift/dormancy.py` detector — near-zero baseline → volume burst; wired into the drift score and surfaced in the API)
- ❌ Missing: legal entity name change signal, domain switch / website content monitoring, public business model pivot detection

---

## Expected Outcome

A working AI system using a **two-layer approach**:

### Layer A — Public Real-Time Intelligence
Capture signals from:
- News and adverse media
- Domain changes and website content shifts
- Funding announcements (Crunchbase, PitchBook)
- Company websites and business model changes
- Government registries and legal updates
- Sanctions lists

### Layer B — Simulated Internal Bank Intelligence
Define a baseline KYC profile (expected business model, activity volumes, risk rating) to **contextualize** public signals. Internal drift detection runs independently and fuses with public signals via Confirmation Lift when they co-occur.

---

## Three-Layer Security & Governance Framework

The challenge explicitly requires all three layers:

### Layer 1 — Data Security
- Separation between public and internal data
- Encryption at rest and in transit
- Secure API calls with key rotation
- Role-based access control (RBAC)
- Data masking before LLM calls
- Immutable audit logs

### Layer 2 — Model Guardrails
- Human-in-the-loop validation for all consequential decisions
- Explainable AI — every score decomposed into named contributions
- Confidence scores on all outputs
- **Source citations** — which news article, sanctions entry, or registry record drove the signal
- Output restrictions (no free-form LLM output without review)
- Bias and hallucination checks

### Layer 3 — Decision Governance
- Risk approval workflows
- Compliance review checkpoints
- Manual validation capability — **implemented**: `DecisionBar` in both the case-review panel and the Drift Engine workspace lets officers record Allow / Step-up / Escalate / Block with an immutable audit trail; override of the AI's recommendation requires a written rationale
- Escalation processes with approval checkpoints

---

## Cost-Aware Pipeline (Challenge Requirement)

The challenge specifies a **staged pipeline** — teams must demonstrate and quantify the cost difference:

| Stage | Method | Scope |
|---|---|---|
| Stage 1 | Rules + embeddings + small models | All customers — cheap filter |
| Stage 2 | LLM reasoning | High-risk borderline cases only |
| Stage 3 | Deep analysis | Escalated alerts only |

**Required deliverables:** token usage per workflow, cost per 1,000 analyses, clear demonstration of Stage 1 vs Stage 2 vs Stage 3 routing.

**Sentinel implementation note:** `POST /drift/scan` reports tier counts and costs, keeps `llm_on_everything_cost` as a counterfactual baseline, and separately reports how many T2 LLM adjudications were actually executed (`actual_t2_llm_calls`, split into real vs mock mode). Mock mode is used automatically in development when no Anthropic API key is configured.

---

## Available Technology Sources

The challenge explicitly provides these integration points. Teams are expected to use them.

### News & Adverse Media
| Tool | Notes |
|---|---|
| Google News RSS | Free, no API key |
| [GDELT Project](https://www.gdeltproject.org/) | Free, near-real-time global news events |
| NewsAPI | Freemium |
| Mediastack API | Freemium |

### Sanctions & Watchlists
| Tool | Notes |
|---|---|
| OFAC SDN List Service | Free REST API |
| EU Financial Sanctions Database | Free XML |
| UN Security Council Sanctions Lists | Free |
| **OpenSanctions** (recommended) | Aggregated free tier — covers OFAC + EU + UN + more |

### Corporate Registry & Ownership Data
| Tool | Notes |
|---|---|
| **GLEIF LEI Database** | Free, global legal entity identifiers |
| UK Companies House API | Free |
| OpenCorporates | Freemium |
| **Swiss ZEFIX Registry** | Free, official Swiss commercial register |

### Funding & Startup Intelligence
| Tool | Notes |
|---|---|
| **Crunchbase** (primary) | Freemium API — funding rounds, investors, pivots |
| Wellfound | Startup-focused |
| PitchBook | Commercial |
| Tracxn | Commercial |

### Website & Domain Monitoring
| Tool | Notes |
|---|---|
| WHOIS Lookup (ICANN) | Free |
| SecurityTrails | Freemium |
| Wayback Machine | Free, historical snapshots |
| Diffbot | Freemium, structured web extraction |
| Firecrawl | OSS, website-to-markdown scraping |

> **Which of these Sentinel actually adopts:** we implement only the free /
> free-tier sources (ZEFIX, GLEIF, OpenSanctions, GDELT, Firecrawl, Wayback,
> WHOIS/RDAP) and skip the paid ones (OpenCorporates, Event Registry,
> Crunchbase). Rationale and the adapter contract are in
> [`sources.md`](sources.md).

---

## Key Terminology

### KYC (Know Your Customer)
The regulatory process of verifying a customer's identity and assessing their risk at onboarding. The bank captures: legal identity, residence and nationality, economic activity and expected transaction patterns, ultimate beneficial ownership (UBO) structure, PEP status, adverse media screening, and source of wealth/funds.

This collected data becomes the **baseline profile** — a frozen snapshot of the parameters of the customer at a point in time. All future drift is measured *relative to this baseline*, not against absolute thresholds. A customer doing €50K/month is unremarkable; the *same customer* doing €50K/month when their profile declared €5–10K is a drift event.

### AML (Anti-Money Laundering)
The set of controls banks use to detect and prevent money laundering and terrorist financing. In practice: transaction monitoring (rules + ML), sanctions screening, Suspicious Activity Reports (SARs), customer due diligence (CDD), and enhanced due diligence (EDD) for high-risk customers.

Traditional AML is **reactive** — it fires alerts when a threshold is crossed. KYC drift makes it **proactive** by detecting the structural change in a customer's profile weeks or months before any threshold is crossed or list is updated.

### KYC Drift
The divergence between the frozen KYC profile and the actual evolving customer. A KYC profile is not a document — it is a snapshot of the parameters of a stochastic process taken at onboarding. The customer *is* the process; the profile is a frozen estimate. Drift is the growing gap between the two.

The key distinction: drift is **relative to the original profile**, not to a population average. A legitimate business growing from €5M to €50M AUM is unremarkable in aggregate; if that same customer's profile declared €500K–1M, the scale change is a KYC event requiring re-verification.

### BOCPD (Bayesian Online Changepoint Detection)
A statistical method (Adams & MacKay, 2007) that maintains a posterior over the **run length** r_t — the number of observations since the last regime change. When the posterior mass shifts sharply toward short run lengths, a regime change has been detected.

The key property: BOCPD catches **gradual drift** that threshold rules structurally miss. A customer raising average monthly volume from €5K to €9K over six months never crosses a €10K alert threshold, but the underlying distribution shift is visible to the run-length posterior. BOCPD is also **online** (processes data left-to-right, never looks ahead), which makes it honest for the Time-Travel Audit.

### Drift Velocity
The time-derivative of KL divergence from the onboarding profile, measured in bits/month.

- **KL Divergence** (accumulated drift) measures *how far* the current profile has moved from the baseline — a lagging indicator.
- **Drift Velocity** measures *how fast* it is moving — a leading indicator.

A customer can show meaningful velocity months before absolute divergence crosses any alert threshold. The combined reading matters: high drift + high velocity = urgent; high drift + flat velocity = investigate but less acute; low drift + rising velocity = early warning.

### Ownership Contagion
Risk that propagates through an ownership graph when an entity in the network is sanctioned or flagged. Implemented via **Personalized PageRank** — the teleport vector is concentrated on the flagged seed entities, so risk flows to nodes close in the ownership topology.

The key compliance insight: a customer two ownership hops from a newly sanctioned entity receives elevated risk *before* any watchlist contains their name. Contagion surfaces this exposure proactively, giving the bank time to act before the regulatory action arrives.

### Confirmation Lift
The amplification applied when a public signal (Layer A) and an internal drift signal (Layer B) independently co-occur within the same time window (~30 days).

Two weak signals that point to the same event from different data sources provide stronger joint evidence than the sum of their parts. The lift factor is gated — it only activates when both signals clear a minimum floor, because two near-zero signals coinciding is the absence of evidence, not its presence.

### Causal Drift vs Benign Drift
Both legitimate business growth and money-laundering activity produce the same statistical signature: rising volume, changing counterparties, shifting corridors. Pure drift detection cannot tell them apart.

The causal layer separates them by comparing **correlation signatures**, not magnitudes:
- **Benign growth:** volume up, margin preserved, counterparties stay clean.
- **Risk transit:** volume up, margin collapses (money flows straight through), counterparties concentrate on high-risk corridors.

A likelihood ratio test (Neyman-Pearson) competes two generative hypotheses — risk-shaped vs benign-shaped — and the verdict modulates the final score. Clearly-benign drift is demoted out of the alert queue; risk-shaped drift is confirmed.

### Suspicious Stability
Every other layer hunts for movement. A sophisticated launderer who knows drift is monitored does the opposite: keeps their profile artificially smooth. But real customers have natural jitter; an anomalously smooth trajectory **while the customer's environment is moving** is itself a signal.

Measured as: `suspicion = stability_anomaly × environmental_movement` — a product, so both factors must be present. A genuinely quiet environment produces neither factor. Only a customer who is too smooth while things around them shift gets flagged.

### Time-Travel Audit
The ability to replay any customer's risk analysis **as-of a past date**, using only data that was available at that time — no information from after the selected date is used.

This is a **regulatory-grade property**: it proves the system would have flagged a customer months before the eventual sanctions listing or regulatory event, without any hindsight bias. BOCPD is online by construction (processes the data stream left-to-right), so truncating to a past date is honest — the algorithm genuinely could not have seen the future data. Regulators (and judges) can verify the lead time is real.

### PEP (Politically Exposed Person)
An individual who holds or has held a prominent public function — heads of state, senior politicians, senior executives of state-owned enterprises, senior military or judicial officials. PEPs are subject to enhanced due diligence because their position creates higher exposure to bribery and corruption risk. Changes to PEP status in a customer's network (e.g., a UBO becomes a government minister) are a primary KYC drift trigger.

### UBO (Ultimate Beneficial Owner)
The natural person who ultimately owns or controls a customer entity — typically defined as owning ≥25% of shares or voting rights, or exercising control by other means. Identifying UBOs is a core KYC requirement under FATF guidance and FINMA rules.

Changes in UBO structure are a primary drift signal. If a UBO is later sanctioned, the entire customer entity becomes retrospectively higher-risk. Ownership contagion (PageRank from the sanctioned UBO) is the mechanism that surfaces this before the bank receives a formal notification.

### SAR (Suspicious Activity Report)
A mandatory filing made by a bank to a financial intelligence unit (in Switzerland: MROS — Money Reporting Office Switzerland) when there is suspicion of money laundering or terrorist financing. Filing a SAR is an internal compliance action; the bank cannot disclose it to the customer ("tipping-off" prohibition). KYC drift scoring helps prioritise which customers warrant SAR consideration before a threshold event occurs.

### EDD (Enhanced Due Diligence)
A deeper level of customer scrutiny applied to high-risk relationships — PEPs, customers from high-risk jurisdictions, complex ownership structures, unusual transaction patterns. EDD requires more frequent reviews, senior management sign-off, and documented source-of-wealth verification. The Drift Engine's "escalate" action triggers an EDD workflow.

### Cost-Aware Cascade
The three-tier routing architecture that controls LLM usage cost:
- **Tier 0** — deterministic rules + BOCPD (near-free, covers ~95% of customers)
- **Tier 1** — ML scoring via XGBoost (~$0.0002 per customer)
- **Tier 2** — LLM reasoning via Claude (~$0.05 per customer, borderline high-risk only)

A customer escalates to the next tier only when the expected information gain justifies the cost. On 1,000 customers this yields ~96% cost reduction versus running every customer through the LLM, at equal high-risk recall.

In the demo backend, Tier 2 is not only a cost estimate: customers routed to `T2_LLM` are adjudicated through the shared Anthropic client. The "LLM on everything" number remains a baseline estimate and is not executed.
